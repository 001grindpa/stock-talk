from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from agent.registry import list_tokens
from database import get_db
from models import Trade
from routers.auth import normalize_wallet, require_wallet
from services.aave import describe_account as describe_aave_v3
from services.aave_v4 import describe_v4_account
from services.feedback import send_feedback
from services.gift import build_gift
from services.morpho import describe_account as describe_morpho
from services.positions import describe_lp

router = APIRouter()
TX_RE = re.compile(r"^0x[a-fA-F0-9]{64}$")


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
