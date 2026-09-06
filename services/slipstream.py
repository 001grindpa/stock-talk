"""Aerodrome Slipstream (CL) quotes on Base. No API key."""

from __future__ import annotations

import time

from services.rpc import _decode_uint, _eth_call

FACTORIES = [
    "0x5e7BB104d84c7CB9B682AaC2F3d509f5F406809A",
    "0xaDe65c38CD4849aDBA595a4323a8C7DdfE89716a",
    "0xf8f2eB4940CFE7d13603DDDD87f123820Fc061Ef",
]
# Router must match the factory generation that owns the pool.
ROUTERS = {
    "0x5e7BB104d84c7CB9B682AaC2F3d509f5F406809A": "0xBE6D8f0d05cC4be24d5167a3eF062215bE6D18a5",
    "0xaDe65c38CD4849aDBA595a4323a8C7DdfE89716a": "0xBE6D8f0d05cC4be24d5167a3eF062215bE6D18a5",
    "0xf8f2eB4940CFE7d13603DDDD87f123820Fc061Ef": "0x698Cb2b6dd822994581fEa6eA4Fc755d1363A92F",
}
QUOTERS = [
    "0x254cF9E1E6e233aa1AC962CB9B05b2cfeAaE15b0",
    "0x3d4C22254F86f64B7eC90ab8F7aeC1FBFD271c6C",
    "0xCd2A7D98e82D6107eac1828ce8DeAA6acB65b555",
]
TICKS = (1, 50, 100, 200, 2000)
GET_POOL = "0x28af8d0b"  # getPool(address,address,int24)
QUOTE_SINGLE = "0x9e7defe6"  # quoteExactInputSingle((address,address,uint256,int24,uint160))
SWAP_SINGLE = "0xa026383e"  # exactInputSingle((address,address,int24,address,uint256,uint256,uint256,uint160))


def _pad_uint(value: int) -> str:
    if value < 0:
        value = (1 << 256) + value
    return hex(int(value))[2:].rjust(64, "0")


def _addr(value: str) -> str:
    return value.lower().replace("0x", "").rjust(64, "0")


def find_cl_pool(token_a: str, token_b: str):
    for factory in FACTORIES:
        for tick in TICKS:
            data = GET_POOL + _addr(token_a) + _addr(token_b) + _pad_uint(tick)
            raw = _eth_call(factory, data)
            if not raw or raw == "0x":
                continue
            pool = "0x" + raw[-40:]
            if int(pool, 16) != 0:
                return pool, tick, factory
    return None, None, None


def _quote_out(token_in: str, token_out: str, tick: int, amount_in: int) -> int | None:
    payload = (
        QUOTE_SINGLE[2:]
        + _pad_uint(0x20)
        + _addr(token_in)
        + _addr(token_out)
        + _pad_uint(amount_in)
        + _pad_uint(tick)
        + _pad_uint(0)
    )
    for quoter in QUOTERS:
        raw = _eth_call(quoter, "0x" + payload)
        out = _decode_uint(raw)
        if out:
            return out
    return None


def encode_exact_input_single(*, token_in, token_out, tick, recipient, amount_in, min_out) -> str:
    deadline = int(time.time()) + 1200
    return "0x" + "".join(
        [
            SWAP_SINGLE[2:],
            _pad_uint(0x20),
            _addr(token_in),
            _addr(token_out),
            _pad_uint(tick),
            _addr(recipient),
            _pad_uint(deadline),
            _pad_uint(amount_in),
            _pad_uint(min_out),
            _pad_uint(0),
        ]
    )


def quote_slipstream(*, from_token: dict, to_token: dict, amount_wei: str, wallet: str | None) -> dict | None:
    amount_in = int(amount_wei)
    if amount_in <= 0:
        return None
    pool, tick, factory = find_cl_pool(from_token["address"], to_token["address"])
    print(f"[slip] pool={pool} tick={tick} factory={factory}", flush=True)
    if not pool:
        return None
    out = _quote_out(from_token["address"], to_token["address"], tick, amount_in)
    print(f"[slip] amount_out={out}", flush=True)
    if not out:
        return None
    router = ROUTERS.get(factory) or "0xBE6D8f0d05cC4be24d5167a3eF062215bE6D18a5"
    recipient = wallet or "0x0000000000000000000000000000000000000001"
    min_out = out * 99 // 100
    return {
        "route": "slipstream",
        "mock": False,
        "buyAmount": str(out),
        "priceImpactBps": 0,
        "spender": router,
        "tx": {
            "to": router,
            "data": encode_exact_input_single(
                token_in=from_token["address"],
                token_out=to_token["address"],
                tick=tick,
                recipient=recipient,
                amount_in=amount_in,
                min_out=min_out,
            ),
            "value": "0",
        },
        "raw": {"pool": pool, "tickSpacing": tick, "factory": factory, "amountOut": str(out)},
    }