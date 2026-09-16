"""Quote and build Aerodrome V2 swaps on Base. No API key."""

from __future__ import annotations

import time

from services.rpc import _decode_uint, _eth_call

USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
ROUTER = "0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43"
FACTORY = "0x420DD381b31aEf6683db6B902084cB0FFECe40Da"
GET_POOL = "0x79bc57d5"  # getPool(address,address,bool)
GET_AMOUNT_OUT = "0xf140a35a"  # getAmountOut(uint256,address)
# swapExactTokensForTokens(uint256,uint256,(address,address,bool,address)[],address,uint256)
SWAP_EXACT = "0xcac88ea9"
GET_RESERVES = "0x0902f1ac"  # getReserves()
KNOWN_POOLS = {
    frozenset({
        "0xb200000000000000000000c2e324d24d7eecd1fb".lower(),  # AAPLc — keep if this is your registry addr
        "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
    }): "0xA3b1e3f9747065e2073722ff4c9027d3ea4994f0",
}


def _pad_uint(value: int) -> str:
    return hex(int(value))[2:].rjust(64, "0")


def _addr(value: str) -> str:
    return value.lower().replace("0x", "").rjust(64, "0")


def _reserves(pool: str) -> tuple[int, int]:
    raw = _eth_call(pool, GET_RESERVES)
    if not raw or raw == "0x" or len(raw) < 130:
        return 0, 0
    h = raw[2:]
    return int(h[0:64], 16), int(h[64:128], 16)


def find_pool(token_a: str, token_b: str) -> tuple[str | None, bool]:
    key = frozenset({token_a.lower(), token_b.lower()})
    known = KNOWN_POOLS.get(key)
    best = None
    best_liq = -1
    best_stable = False
    for stable in (False, True):
        data = GET_POOL + _addr(token_a) + _addr(token_b) + _pad_uint(1 if stable else 0)
        raw = _eth_call(FACTORY, data)
        if not raw or raw == "0x":
            continue
        pool = "0x" + raw[-40:]
        if int(pool, 16) == 0:
            continue
        r0, r1 = _reserves(pool)
        liq = r0 * r1
        if liq > best_liq:
            best, best_liq, best_stable = pool, liq, stable
    if known and (best is None or best.lower() != known.lower()):
        r0, r1 = _reserves(known)
        if r0 * r1 >= best_liq:
            return known, best_stable
    return (best, best_stable) if best else (None, False)


def amount_out(pool: str, amount_in: int, token_in: str) -> int | None:
    data = GET_AMOUNT_OUT + _pad_uint(amount_in) + _addr(token_in)
    return _decode_uint(_eth_call(pool, data))


def encode_swap(*, amount_in: int, min_out: int, routes: list[tuple[str, str, bool]], recipient: str) -> str:
    deadline = int(time.time()) + 1200
    parts = [
        SWAP_EXACT[2:],
        _pad_uint(amount_in),
        _pad_uint(min_out),
        _pad_uint(0xA0),
        _addr(recipient),
        _pad_uint(deadline),
        _pad_uint(len(routes)),
    ]
    for token_in, token_out, stable in routes:
        parts += [
            _addr(token_in),
            _addr(token_out),
            _pad_uint(1 if stable else 0),
            _addr(FACTORY),
        ]
    return "0x" + "".join(parts)


def _leg(token_in: str, token_out: str, amount_in: int):
    pool, stable = find_pool(token_in, token_out)
    if not pool:
        return None
    out = amount_out(pool, amount_in, token_in)
    if not out:
        return None
    return pool, stable, out


def quote_aerodrome(*, from_token: dict, to_token: dict, amount_wei: str, wallet: str | None) -> dict | None:
    amount_in = int(amount_wei)
    if amount_in <= 0:
        return None
    token_in = from_token["address"]
    token_out = to_token["address"]
    recipient = wallet or "0x0000000000000000000000000000000000000001"

    direct = _leg(token_in, token_out, amount_in)
    routes = None
    out = None
    hops = []
    if direct:
        pool, stable, out = direct
        routes = [(token_in, token_out, stable)]
        hops = [pool]
    else:
        mid = USDC
        if token_in.lower() != mid.lower() and token_out.lower() != mid.lower():
            first = _leg(token_in, mid, amount_in)
            if first:
                pool0, stable0, mid_out = first
                second = _leg(mid, token_out, mid_out)
                if second:
                    pool1, stable1, out = second
                    routes = [(token_in, mid, stable0), (mid, token_out, stable1)]
                    hops = [pool0, pool1]

    if not routes or not out:
        return None
    min_out = out * 99 // 100
    return {
        "route": "aerodrome" if len(routes) == 1 else "aerodrome-hop",
        "mock": False,
        "buyAmount": str(out),
        "priceImpactBps": 0,
        "spender": ROUTER,
        "tx": {
            "to": ROUTER,
            "data": encode_swap(amount_in=amount_in, min_out=min_out, routes=routes, recipient=recipient),
            "value": "0",
        },
        "raw": {"pools": hops, "routes": routes, "amountOut": str(out)},
    }