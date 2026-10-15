from __future__ import annotations

import asyncio
import logging
import math
import re

import httpx
from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from agent.graph import rebuild_transaction_action
from agent.registry import list_tokens
from database import get_db
from models import Trade
from routers.auth import normalize_wallet, require_wallet
from services.aave import describe_account as describe_aave_v3
from services.aave_v4 import describe_v4_account
from services.feedback import send_feedback
from services.gift import build_gift
from services.morpho import describe_account as describe_morpho
from services.positions import describe_lp, list_withdrawable_positions
from services.rpc import rpc_url

router = APIRouter()
logger = logging.getLogger(__name__)
TX_RE = re.compile(r"^0x[a-fA-F0-9]{64}$")
BALANCE_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
BALANCE_RAW_RE = re.compile(r"^(0|[1-9][0-9]*)$")
NATIVE_ADDRESSES = {
    "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
    "0x0000000000000000000000000000000000000000",
}
MAX_BALANCE_CHECKS = 100
EDITABLE_PROTOCOLS = {
    "aerodrome",
    "slipstream",
    "uniswap",
}


async def _read_wallet_balance(
    client: httpx.AsyncClient,
    wallet: str,
    address: str,
    request_id: int,
) -> str:
    if address.lower() in NATIVE_ADDRESSES:
        method = "eth_getBalance"
        params = [wallet, "latest"]
    else:
        method = "eth_call"
        params = [
            {
                "to": address,
                "data": "0x70a08231" + wallet[2:].lower().rjust(64, "0"),
            },
            "latest",
        ]

    response = await client.post(
        rpc_url(),
        json={
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        },
    )
    response.raise_for_status()
    result = response.json()
    value = result.get("result") if isinstance(result, dict) else None
    if not isinstance(value, str) or not re.fullmatch(r"0x[0-9a-fA-F]+", value):
        raise RuntimeError("Base RPC returned an invalid balance.")
    return str(int(value, 16))


@router.websocket("/ws/balances")
async def websocket_balance_check(websocket: WebSocket):
    await websocket.accept()
    try:
        payload = await websocket.receive_json()
        if not isinstance(payload, dict):
            await websocket.send_json(
                {"type": "error", "status": 400, "error": "Invalid balance check."}
            )
            return

        requested_wallet = payload.get("wallet")
        wallet = (
            normalize_wallet(requested_wallet)
            if isinstance(requested_wallet, str)
            else None
        )
        session_wallet = normalize_wallet(websocket.session.get("wallet"))
        if not wallet or wallet != session_wallet:
            await websocket.send_json(
                {
                    "type": "error",
                    "status": 401,
                    "error": "Sign in with your wallet first.",
                }
            )
            return

        cached_balances = payload.get("balances")
        if (
            not isinstance(cached_balances, list)
            or not cached_balances
            or len(cached_balances) > MAX_BALANCE_CHECKS
        ):
            await websocket.send_json(
                {"type": "error", "status": 400, "error": "Invalid cached balances."}
            )
            return

        checks = []
        seen_addresses = set()
        for item in cached_balances:
            if not isinstance(item, dict):
                await websocket.send_json(
                    {"type": "error", "status": 400, "error": "Invalid cached balance."}
                )
                return
            address = item.get("address")
            cached_raw = item.get("raw")
            if (
                not isinstance(address, str)
                or not BALANCE_ADDRESS_RE.fullmatch(address)
                or not isinstance(cached_raw, str)
                or not BALANCE_RAW_RE.fullmatch(cached_raw)
                or address.lower() in seen_addresses
            ):
                await websocket.send_json(
                    {"type": "error", "status": 400, "error": "Invalid cached balance."}
                )
                return
            seen_addresses.add(address.lower())
            checks.append((address, cached_raw))

        async with httpx.AsyncClient(timeout=20.0) as client:
            values = await asyncio.gather(
                *(
                    _read_wallet_balance(client, wallet, address, index)
                    for index, (address, _) in enumerate(checks, start=1)
                )
            )
        actual_balances = {
            address.lower(): actual
            for (address, _), actual in zip(checks, values, strict=True)
        }
        unchanged = all(
            cached_raw == actual_balances[address.lower()]
            for address, cached_raw in checks
        )
        result = {"type": "result", "unchanged": unchanged}
        if not unchanged:
            result["balances"] = actual_balances
        await websocket.send_json(result)
    except WebSocketDisconnect:
        return
    except (httpx.HTTPError, RuntimeError, ValueError):
        logger.exception("Balance comparison failed")
        try:
            await websocket.send_json(
                {
                    "type": "error",
                    "status": 502,
                    "error": "Could not verify current wallet balances.",
                }
            )
        except WebSocketDisconnect:
            return


@router.get("/api/tokens")
def api_tokens(db: Session = Depends(get_db)):
    fields = ("symbol", "name", "address", "decimals", "kind")
    return {
        "chainId": 8453,
        "tokens": [
            {field: token[field] for field in fields}
            for token in list_tokens(db)
        ],
    }


@router.post("/api/trades")
async def api_record_trade(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    requested_wallet = normalize_wallet(payload.get("wallet"))
    wallet, error = require_wallet(request, requested_wallet)
    if error:
        return error

    tx_hash = payload.get("tx_hash")
    tx_hash = tx_hash.strip() if isinstance(tx_hash, str) else ""
    if not TX_RE.fullmatch(tx_hash):
        return JSONResponse({"error": "valid tx_hash is required"}, status_code=400)

    fields = {
        "wallet": wallet,
        "tx_hash": tx_hash,
        "explorer": (
            payload.get("explorer").strip()
            if isinstance(payload.get("explorer"), str)
            and payload["explorer"].strip()
            else f"https://basescan.org/tx/{tx_hash}"
        ),
        "kind": payload.get("kind"),
        "route": payload.get("route"),
        "from_symbol": payload.get("from_symbol"),
        "to_symbol": payload.get("to_symbol"),
        "from_amount": payload.get("from_amount"),
        "to_amount": payload.get("to_amount"),
    }
    update_fields = {key: value for key, value in fields.items() if key != "tx_hash"}
    statement = insert(Trade).values(**fields).on_conflict_do_update(
        index_elements=[Trade.tx_hash],
        set_=update_fields,
    )
    db.execute(statement)
    db.commit()
    trade = db.scalar(select(Trade).where(Trade.tx_hash == tx_hash))
    return trade.as_dict()


@router.get("/api/trades")
def get_trades(wallet: str | None = None, db: Session = Depends(get_db)):
    normalized = normalize_wallet(wallet)
    if not normalized:
        return JSONResponse({"error": "valid wallet is required"}, status_code=400)
    trades = db.scalars(
        select(Trade)
        .where(Trade.wallet == normalized)
        .order_by(Trade.created_at.desc(), Trade.id.desc())
        .limit(50)
    ).all()
    return {"trades": [trade.as_dict() for trade in trades]}


@router.post("/api/gift/build")
async def api_gift_build(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    wallet, error = require_wallet(request, payload.get("wallet"))
    if error:
        return error
    result = build_gift(
        db,
        wallet=wallet,
        to=payload.get("to"),
        symbol=payload.get("symbol"),
        amount=payload.get("amount"),
        memo=payload.get("memo") or "",
    )
    if result.get("error"):
        return JSONResponse({"error": result["error"]}, status_code=400)
    return result


@router.post("/api/action/rebuild")
async def api_rebuild_action(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    wallet, error = require_wallet(request, payload.get("wallet"))
    if error:
        return error

    kind = payload.get("kind")
    kind = kind.strip() if isinstance(kind, str) else ""
    amount = payload.get("amount", "")
    amount = amount.strip() if isinstance(amount, str) else ""
    if len(amount) > 80:
        return JSONResponse({"error": "Amount is too long."}, status_code=400)

    try:
        fraction = float(payload.get("fraction") or 0)
    except (TypeError, ValueError):
        return JSONResponse({"error": "Invalid amount percentage."}, status_code=400)
    if not math.isfinite(fraction) or fraction < 0 or fraction > 1:
        return JSONResponse({"error": "Amount percentage must be from 0% to 100%."}, status_code=400)

    protocol = payload.get("protocol", "")
    protocol = protocol.strip().lower() if isinstance(protocol, str) else ""
    lp_action = kind in {
        "lp_add", "lp_remove", "slip_lp_add", "slip_lp_remove",
        "uni_lp_add", "uni_lp_remove",
    }
    if lp_action and protocol not in EDITABLE_PROTOCOLS:
        return JSONResponse({"error": "Unsupported transaction venue."}, status_code=400)

    balances = payload.get("balances")
    if not isinstance(balances, list):
        balances = []
    legs = payload.get("legs")
    if not isinstance(legs, list):
        legs = []

    result = await run_in_threadpool(
        lambda: rebuild_transaction_action(
            db=db,
            wallet=wallet,
            balances=balances,
            kind=kind,
            from_symbol=str(payload.get("from_symbol") or "")[:80],
            to_symbol=str(payload.get("to_symbol") or "")[:80],
            amount=amount,
            fraction=fraction,
            collateral_symbol=str(payload.get("collateral_symbol") or "")[:80],
            protocol=protocol,
            position_id=str(payload.get("position_id") or "")[:128],
            legs=legs,
        )
    )
    if result.get("error"):
        return JSONResponse({"error": result["error"]}, status_code=400)
    return result


@router.get("/api/withdrawable-positions")
async def get_withdrawable_positions(wallet: str | None = None, protocol: str = ""):
    normalized = normalize_wallet(wallet)
    if not normalized:
        return JSONResponse({"error": "valid wallet is required"}, status_code=400)
    protocol = protocol.strip().lower()
    if protocol not in {"aerodrome", "slipstream", "uniswap", "aave", "aave_v4", "morpho"}:
        return JSONResponse({"error": "unsupported position protocol"}, status_code=400)
    positions = await run_in_threadpool(
        list_withdrawable_positions, normalized, protocol
    )
    return {"positions": positions}


@router.get("/api/positions")
async def get_positions(wallet: str | None = None):
    normalized = normalize_wallet(wallet)
    if not normalized:
        return JSONResponse({"error": "valid wallet is required"}, status_code=400)
    try:
        positions = await run_in_threadpool(
            lambda: "\n\n".join(
                (
                    describe_aave_v3(normalized),
                    describe_v4_account(normalized),
                    describe_morpho(normalized),
                    describe_lp(normalized),
                )
            )
        )
    except Exception:
        return JSONResponse({"error": "positions unavailable"}, status_code=502)
    return {"positions": positions}


@router.post("/api/feedback")
async def api_feedback(request: Request):
    payload = await request.json()
    forwarded_for = request.headers.get("X-Forwarded-For")
    remote_ip = (
        forwarded_for.split(",", 1)[0].strip()
        if forwarded_for
        else request.client.host if request.client else "127.0.0.1"
    )
    response_body, status_code = await run_in_threadpool(
        send_feedback, payload, remote_ip
    )
    return JSONResponse(response_body, status_code=status_code)
