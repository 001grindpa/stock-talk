"""Aerodrome V2 add/remove liquidity. Backend never signs."""

from __future__ import annotations

import time

from services.aerodrome import FACTORY, GET_AMOUNT_OUT, ROUTER, find_pool
from services.quotes import from_wei, to_wei
from services.rpc import _decode_uint, _eth_call

ADD_LIQUIDITY = "0x5a47ddc3"
REMOVE_LIQUIDITY = "0x0dede6c4"
GET_RESERVES = "0x0902f1ac"
TOKEN0 = "0x0dfe1681"


def _pad_uint(value: int) -> str:
    return hex(int(value))[2:].rjust(64, "0")


def _addr(value: str) -> str:
    return value.lower().replace("0x", "").rjust(64, "0")


def _call_address(to: str, selector: str) -> str | None:
    raw = _eth_call(to, selector)
    if not raw or raw == "0x":
        return None
    return "0x" + raw[-40:]


def pool_reserves(pool: str) -> tuple[str, int, int] | None:
    token0 = _call_address(pool, TOKEN0)
    raw = _eth_call(pool, GET_RESERVES)
    if not token0 or not raw or raw == "0x" or len(raw) < 2 + 64 * 2:
        return None
    body = raw[2:]
    r0 = int(body[0:64], 16)
    r1 = int(body[64:128], 16)
    return token0.lower(), r0, r1


def match_amounts(pool: str, token_a: dict, token_b: dict, wei_a: int | None, wei_b: int | None) -> tuple[int, int] | None:
    wei_a = int(wei_a or 0)
    wei_b = int(wei_b or 0)
    if wei_a <= 0 and wei_b <= 0:
        return None
    info = pool_reserves(pool)
    if not info:
        if wei_a > 0 and wei_b > 0:
            return wei_a, wei_b
        return None
    token0, r0, r1 = info
    a_is_0 = token_a["address"].lower() == token0
    res_a, res_b = (r0, r1) if a_is_0 else (r1, r0)
    if res_a <= 0 or res_b <= 0:
        if wei_a > 0 and wei_b > 0:
            return wei_a, wei_b
        return None
    if wei_a > 0 and wei_b <= 0:
        return wei_a, wei_a * res_b // res_a
    if wei_b > 0 and wei_a <= 0:
        return wei_b * res_a // res_b, wei_b
    opt_b = wei_a * res_b // res_a
    if opt_b <= wei_b:
        return wei_a, opt_b
    return wei_b * res_a // res_b, wei_b


def encode_add(*, token_a, token_b, stable, amount_a, amount_b, min_a, min_b, recipient) -> str:
    deadline = int(time.time()) + 1200
    return "0x" + "".join(
        [
            ADD_LIQUIDITY[2:],
            _addr(token_a),
            _addr(token_b),
            _pad_uint(1 if stable else 0),
            _pad_uint(amount_a),
            _pad_uint(amount_b),
            _pad_uint(min_a),
            _pad_uint(min_b),
            _addr(recipient),
            _pad_uint(deadline),
        ]
    )


def encode_remove(*, token_a, token_b, stable, liquidity, min_a, min_b, recipient) -> str:
    deadline = int(time.time()) + 1200
    return "0x" + "".join(
        [
            REMOVE_LIQUIDITY[2:],
            _addr(token_a),
            _addr(token_b),
            _pad_uint(1 if stable else 0),
            _pad_uint(liquidity),
            _pad_uint(min_a),
            _pad_uint(min_b),
            _addr(recipient),
            _pad_uint(deadline),
        ]
    )


def build_add_lp(*, token_a, token_b, amount_a, amount_b, wallet, balances) -> dict:
    if not wallet:
        return {"error": "Connect a Base wallet to add Aerodrome liquidity."}
    pool, stable = find_pool(token_a["address"], token_b["address"])
    if not pool:
        return {"error": f"No Aerodrome V2 pool for {token_a['symbol']}/{token_b['symbol']}."}

    def held(token):
        addr = token["address"].lower()
        for item in balances or []:
            if (item.get("address") or "").lower() == addr:
                return item
        for item in balances or []:
            if (item.get("symbol") or "").upper() == token["symbol"].upper():
                return item
        return None

    row_a = held(token_a)
    row_b = held(token_b)
    wei_a = int(to_wei(amount_a, token_a["decimals"])) if amount_a else 0
    wei_b = int(to_wei(amount_b, token_b["decimals"])) if amount_b else 0
    if wei_a <= 0 and row_a:
        wei_a = int(row_a.get("raw") or 0)
    if wei_a <= 0:
        have = (row_a or {}).get("formatted") or "0"
        return {
            "error": (
                f"You have {have} {token_a['symbol']}, which is too small to add LP. "
                f"Swap some USDC for {token_a['symbol']} first, then ask again."
            )
        }

    matched = match_amounts(pool, token_a, token_b, wei_a, wei_b or None)
    if not matched:
        return {"error": f"Could not size a matching {token_b['symbol']} amount from the pool reserves."}
    use_a, use_b = matched
    if row_b and use_b > int(row_b.get("raw") or 0):
        return {
            "error": (
                f"Need {from_wei(use_b, token_b['decimals'])} {token_b['symbol']} to match "
                f"{from_wei(use_a, token_a['decimals'])} {token_a['symbol']}, "
                f"but you only have {(row_b or {}).get('formatted')}. Swap or use a smaller %."
            )
        }
    min_a, min_b = use_a * 99 // 100, use_b * 99 // 100
    return {
        "type": "tx",
        "kind": "lp_add",
        "protocol": "aerodrome",
        "mock": False,
        "summary": (
            f"Add {from_wei(use_a, token_a['decimals'])} {token_a['symbol']} + "
            f"{from_wei(use_b, token_b['decimals'])} {token_b['symbol']} "
            f"to Aerodrome V2 ({'stable' if stable else 'volatile'})"
        ),
        "spender": ROUTER,
        "approvals": [
            {"symbol": token_a["symbol"], "address": token_a["address"], "amountWei": str(use_a)},
            {"symbol": token_b["symbol"], "address": token_b["address"], "amountWei": str(use_b)},
        ],
        "from": {
            "symbol": token_a["symbol"],
            "address": token_a["address"],
            "decimals": token_a["decimals"],
            "amount": from_wei(use_a, token_a["decimals"]),
            "amountWei": str(use_a),
        },
        "to": {
            "symbol": token_b["symbol"],
            "address": token_b["address"],
            "decimals": token_b["decimals"],
            "amount": from_wei(use_b, token_b["decimals"]),
            "amountWei": str(use_b),
        },
        "tx": {
            "to": ROUTER,
            "data": encode_add(
                token_a=token_a["address"],
                token_b=token_b["address"],
                stable=stable,
                amount_a=use_a,
                amount_b=use_b,
                min_a=min_a,
                min_b=min_b,
                recipient=wallet,
            ),
            "value": "0",
        },
        "raw": {"pool": pool, "stable": stable},
    }


def build_remove_lp(*, token_a, token_b, fraction, wallet, balances) -> dict:
    if not wallet:
        return {"error": "Connect a Base wallet to remove Aerodrome liquidity."}
    pool, stable = find_pool(token_a["address"], token_b["address"])
    if not pool:
        return {"error": f"No Aerodrome V2 pool for {token_a['symbol']}/{token_b['symbol']}."}
    lp_row = None
    for item in balances or []:
        if (item.get("address") or "").lower() == pool.lower():
            lp_row = item
            break
    raw_lp = int((lp_row or {}).get("raw") or 0)
    if raw_lp <= 0:
        return {
            "error": (
                f"I don't see Aerodrome LP for {token_a['symbol']}/{token_b['symbol']} in this wallet. "
                "The frontend must include the pool token in balances."
            )
        }
    frac = 1.0 if fraction is None else float(fraction)
    liquidity = int(raw_lp * frac)
    if liquidity <= 0:
        return {"error": "LP amount is zero."}
    return {
        "type": "tx",
        "kind": "lp_remove",
        "protocol": "aerodrome",
        "mock": False,
        "summary": f"Remove {int(frac * 100)}% Aerodrome LP {token_a['symbol']}/{token_b['symbol']}",
        "spender": ROUTER,
        "approvals": [
            {"symbol": "AERO-LP", "address": pool, "amountWei": str(liquidity)},
        ],
        "from": {
            "symbol": "AERO-LP",
            "address": pool,
            "decimals": 18,
            "amount": from_wei(liquidity, 18),
            "amountWei": str(liquidity),
        },
        "to": {
            "symbol": f"{token_a['symbol']}+{token_b['symbol']}",
            "address": pool,
            "decimals": 18,
            "amount": "pool tokens",
            "amountWei": "0",
        },
        "tx": {
            "to": ROUTER,
            "data": encode_remove(
                token_a=token_a["address"],
                token_b=token_b["address"],
                stable=stable,
                liquidity=liquidity,
                min_a=0,
                min_b=0,
                recipient=wallet,
            ),
            "value": "0",
        },
        "raw": {"pool": pool, "stable": stable, "liquidity": str(liquidity)},
    }