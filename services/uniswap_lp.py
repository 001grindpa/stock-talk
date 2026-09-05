"""Uniswap V3 full-range mint on Base if a pool already exists."""

from __future__ import annotations

import time

from services.quotes import from_wei, to_wei
from services.rpc import _decode_uint, _eth_call

FACTORY = "0x33128a8fC17869897dcE68Ed026d694621f6FDfD"
NPM = "0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1"
GET_POOL = "0x1698ee82"  # getPool(address,address,uint24)
MINT = "0x88316456"
SLOT0 = "0x3850c7bd"
FEES = (3000, 500, 10000)


def _pad_uint(value: int) -> str:
    if value < 0:
        value = (1 << 256) + value
    return hex(value)[2:].rjust(64, "0")


def _addr(value: str) -> str:
    return value.lower().replace("0x", "").rjust(64, "0")


def _sort(token_a: dict, token_b: dict) -> tuple[dict, dict]:
    if token_a["address"].lower() < token_b["address"].lower():
        return token_a, token_b
    return token_b, token_a


def find_v3_pool(token_a: str, token_b: str) -> tuple[str | None, int]:
    for fee in FEES:
        data = GET_POOL + _addr(token_a) + _addr(token_b) + _pad_uint(fee)
        raw = _eth_call(FACTORY, data)
        if not raw or raw == "0x":
            continue
        pool = "0x" + raw[-40:]
        if int(pool, 16) != 0:
            return pool, fee
    return None, 3000


def ticks_for_fee(fee: int) -> tuple[int, int]:
    spacing = {500: 10, 3000: 60, 10000: 200}.get(fee, 60)
    lo = -887220
    hi = 887220
    lo = lo // spacing * spacing
    hi = hi // spacing * spacing
    return lo, hi


def _held(token: dict, balances) -> int:
    addr = token["address"].lower()
    for item in balances or []:
        if (item.get("address") or "").lower() == addr:
            return int(item.get("raw") or 0)
    return 0


def encode_mint(*, token0, token1, fee, tick_l, tick_u, amt0, amt1, min0, min1, recipient) -> str:
    deadline = int(time.time()) + 1200
    fields = [
        _addr(token0),
        _addr(token1),
        _pad_uint(fee),
        _pad_uint(tick_l),
        _pad_uint(tick_u),
        _pad_uint(amt0),
        _pad_uint(amt1),
        _pad_uint(min0),
        _pad_uint(min1),
        _addr(recipient),
        _pad_uint(deadline),
    ]
    return "0x" + MINT[2:] + _pad_uint(0x20) + "".join(fields)


def build_uni_add(*, token_a, token_b, amount_a, amount_b, fraction, wallet, balances) -> dict:
    if not wallet:
        return {"error": "Connect a Base wallet to mint Uniswap V3 LP."}
    token0, token1 = _sort(token_a, token_b)
    pool, fee = find_v3_pool(token0["address"], token1["address"])
    if not pool:
        return {
            "error": (
                f"No Uniswap V3 pool on Base for {token_a['symbol']}/{token_b['symbol']}. "
                "Use Aerodrome for tokenized stocks."
            )
        }
    wei_a = int(to_wei(amount_a, token_a["decimals"])) if amount_a else 0
    wei_b = int(to_wei(amount_b, token_b["decimals"])) if amount_b else 0
    if fraction:
        if wei_a <= 0:
            wei_a = int(_held(token_a, balances) * float(fraction))
        if wei_b <= 0:
            wei_b = int(_held(token_b, balances) * float(fraction))
    if wei_a <= 0:
        wei_a = _held(token_a, balances)
    if wei_b <= 0:
        wei_b = _held(token_b, balances)
    if wei_a <= 0 or wei_b <= 0:
        return {
            "error": (
                f"Uniswap V3 needs both tokens. You need {token_a['symbol']} and {token_b['symbol']}."
            )
        }
    amt0 = wei_a if token0["address"].lower() == token_a["address"].lower() else wei_b
    amt1 = wei_b if token0["address"].lower() == token_a["address"].lower() else wei_a
    tick_l, tick_u = ticks_for_fee(fee)
    data = encode_mint(
        token0=token0["address"],
        token1=token1["address"],
        fee=fee,
        tick_l=tick_l,
        tick_u=tick_u,
        amt0=amt0,
        amt1=amt1,
        min0=amt0 * 95 // 100,
        min1=amt1 * 95 // 100,
        recipient=wallet,
    )
    return {
        "type": "tx",
        "kind": "uni_lp_add",
        "protocol": "uniswap",
        "mock": False,
        "summary": (
            f"Mint Uniswap V3 full-range LP: "
            f"{from_wei(wei_a, token_a['decimals'])} {token_a['symbol']} + "
            f"{from_wei(wei_b, token_b['decimals'])} {token_b['symbol']} "
            f"(fee {fee / 10000:.2f}%)"
        ),
        "spender": NPM,
        "approvals": [
            {"symbol": token_a["symbol"], "address": token_a["address"], "amountWei": str(wei_a)},
            {"symbol": token_b["symbol"], "address": token_b["address"], "amountWei": str(wei_b)},
        ],
        "from": {
            "symbol": token_a["symbol"],
            "address": token_a["address"],
            "decimals": token_a["decimals"],
            "amount": from_wei(wei_a, token_a["decimals"]),
            "amountWei": str(wei_a),
        },
        "to": {
            "symbol": token_b["symbol"],
            "address": token_b["address"],
            "decimals": token_b["decimals"],
            "amount": from_wei(wei_b, token_b["decimals"]),
            "amountWei": str(wei_b),
        },
        "tx": {"to": NPM, "data": data, "value": "0"},
        "raw": {"pool": pool, "fee": fee, "npm": NPM},
    }