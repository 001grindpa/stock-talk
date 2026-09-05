"""Quote and build Aerodrome V2 swaps on Base. No API key."""

from __future__ import annotations

import time

from services.rpc import _decode_uint, _eth_call

ROUTER = "0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43"
FACTORY = "0x420DD381b31aEf6683db6B902084cB0FFECe40Da"
GET_POOL = "0x79bc57d5"  # getPool(address,address,bool)
GET_AMOUNT_OUT = "0xf140a35a"  # getAmountOut(uint256,address)
# swapExactTokensForTokens(uint256,uint256,(address,address,bool,address)[],address,uint256)
SWAP_EXACT = "0xcac88ea9"


def _pad_uint(value: int) -> str:
    return hex(int(value))[2:].rjust(64, "0")


def _addr(value: str) -> str:
    return value.lower().replace("0x", "").rjust(64, "0")


def find_pool(token_a: str, token_b: str) -> tuple[str | None, bool]:
    for stable in (False, True):
        data = GET_POOL + _addr(token_a) + _addr(token_b) + _pad_uint(1 if stable else 0)
        raw = _eth_call(FACTORY, data)
        if not raw or raw == "0x":
            continue
        pool = "0x" + raw[-40:]
        if int(pool, 16) != 0:
            return pool, stable
    return None, False


def amount_out(pool: str, amount_in: int, token_in: str) -> int | None:
    data = GET_AMOUNT_OUT + _pad_uint(amount_in) + _addr(token_in)
    return _decode_uint(_eth_call(pool, data))


def encode_swap(
    *,
    amount_in: int,
    min_out: int,
    token_in: str,
    token_out: str,
    stable: bool,
    recipient: str,
) -> str:
    deadline = int(time.time()) + 1200
    return "0x" + "".join(
        [
            SWAP_EXACT[2:],
            _pad_uint(amount_in),
            _pad_uint(min_out),
            _pad_uint(0xA0),  # offset to routes
            _addr(recipient),
            _pad_uint(deadline),
            _pad_uint(1),  # one route
            _addr(token_in),
            _addr(token_out),
            _pad_uint(1 if stable else 0),
            _addr(FACTORY),
        ]
    )


def quote_aerodrome(
    *,
    from_token: dict,
    to_token: dict,
    amount_wei: str,
    wallet: str | None,
) -> dict | None:
    amount_in = int(amount_wei)
    pool, stable = find_pool(from_token["address"], to_token["address"])
    print(f"[aero] pool={pool} stable={stable} amount_in={amount_in}")
    if not pool:
        return None
    out = amount_out(pool, amount_in, from_token["address"])
    print(f"[aero] amount_out={out}")
    if not out:
        return None
    min_out = out * 99 // 100
    recipient = wallet or "0x0000000000000000000000000000000000000001"
    return {
        "route": "aerodrome",
        "mock": False,
        "buyAmount": str(out),
        "priceImpactBps": 0,
        "spender": ROUTER,
        "tx": {
            "to": ROUTER,
            "data": encode_swap(
                amount_in=amount_in,
                min_out=min_out,
                token_in=from_token["address"],
                token_out=to_token["address"],
                stable=stable,
                recipient=recipient,
            ),
            "value": "0",
        },
        "raw": {"pool": pool, "stable": stable, "amountOut": str(out)},
    }