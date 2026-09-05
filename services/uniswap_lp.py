"""Uniswap V3 full-range mint on Base if a pool already exists."""

from __future__ import annotations

import time

from services.quotes import from_wei, to_wei
from services.rpc import _eth_call

FACTORY = "0x33128a8fC17869897dcE68Ed026d694621f6FDfD"
NPM = "0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1"
GET_POOL = "0x1698ee82"
MINT = "0x88316456"
SLOT0 = "0x3850c7bd"
FEES = (3000, 500, 10000)


def _pad_uint(value: int) -> str:
    if value < 0:
        value = (1 << 256) + value
    return hex(int(value))[2:].rjust(64, "0")


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
    return (-887220 // spacing) * spacing, (887220 // spacing) * spacing


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
    if token_a is None or token_b is None:
        return {"error": "Need two tokens, e.g. AAPL and USDC."}

    token0, token1 = _sort(token_a, token_b)
    pool, fee = find_v3_pool(token0["address"], token1["address"])
    if not pool:
        return {
            "error": (
                f"No Uniswap V3 pool on Base for {token_a['symbol']}/{token_b['symbol']}. "
                "Use Aerodrome for tokenized stocks."
            )
        }

    frac = float(fraction) if fraction else 1.0
    held_a = _held(token_a, balances)
    held_b = _held(token_b, balances)
    wei_a = int(held_a * frac) if (fraction or not amount_a) else int(to_wei(amount_a, token_a["decimals"]))
    wei_b = int(held_b * frac) if (fraction or not amount_b) else int(to_wei(amount_b, token_b["decimals"]))
    if wei_a <= 0:
        wei_a = held_a
    if wei_b <= 0:
        wei_b = held_b

    min_a = 10 ** max(int(token_a["decimals"]) - 6, 0)
    if wei_a < min_a:
        return {
            "error": (
                f"Your {token_a['symbol']} balance is dust "
                f"({from_wei(held_a, token_a['decimals'], places=8)}). "
                "Swap a real amount of USDC for AAPL first, then add LP. "
                "Do not confirm a 0.000000 mint."
            )
        }
    if wei_b <= 0:
        return {"error": f"Need some {token_b['symbol']} to match the pool."}

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
        min0=0,
        min1=0,
        recipient=wallet,
    )
    return {
        "type": "tx",
        "kind": "uni_lp_add",
        "protocol": "uniswap",
        "mock": False,
        "summary": (
            f"Mint Uniswap V3 full-range LP: "
            f"{from_wei(wei_a, token_a['decimals'], places=8)} {token_a['symbol']} + "
            f"{from_wei(wei_b, token_b['decimals'], places=6)} {token_b['symbol']} "
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
            "amount": from_wei(wei_a, token_a["decimals"], places=8),
            "amountWei": str(wei_a),
        },
        "to": {
            "symbol": token_b["symbol"],
            "address": token_b["address"],
            "decimals": token_b["decimals"],
            "amount": from_wei(wei_b, token_b["decimals"], places=6),
            "amountWei": str(wei_b),
        },
        "tx": {"to": NPM, "data": data, "value": "0"},
        "raw": {"pool": pool, "fee": fee, "npm": NPM},
    }