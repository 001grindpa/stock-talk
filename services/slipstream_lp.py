"""Aerodrome Slipstream CL mint / list / remove on Base."""

from __future__ import annotations

import time

from services.quotes import from_wei, to_wei
from services.rpc import _decode_uint, _eth_call
from services.slipstream import TICKS, find_cl_pool

NPMS = [
    "0x827922686190790b37229fd06084350E74485b72",
    "0xa990C6a764b73BF43cee5Bb40339c3322FB9D55F",
    "0xe1f8cd9AC4e4A65F54f38a5CdAfCA44f6dD68b53",
]
MINT = "0xb5007d1f"
BALANCE_OF = "0x70a08231"
TOKEN_OF_OWNER = "0x2f745c59"
POSITIONS = "0x99fbab88"
DECREASE = "0x0c49ccbe"
COLLECT = "0xfc6f7865"
MULTICALL = "0xac9650d8"
BURN_NFT = "0x42966c68"
MAX_U128 = (1 << 128) - 1
MIN_TICK = -887272
MAX_TICK = 887272
FACTORY_NPM = {
    "0x5e7bb104d84c7cb9b682aac2f3d509f5f406809a": "0x827922686190790b37229fd06084350E74485b72",
    "0xade65c38cd4849adba595a4323a8c7ddfe89716a": "0xa990C6a764b73BF43cee5Bb40339c3322FB9D55F",
    "0xf8f2eb4940cfe7d13603dddd87f123820fc061ef": "0xe1f8cd9AC4e4A65F54f38a5CdAfCA44f6dD68b53",
}


def _pad_uint(value: int) -> str:
    if value < 0:
        value = (1 << 256) + value
    return hex(int(value))[2:].rjust(64, "0")


def _addr(value: str) -> str:
    return value.lower().replace("0x", "").rjust(64, "0")


def _sort(a: dict, b: dict) -> tuple[dict, dict]:
    if a["address"].lower() < b["address"].lower():
        return a, b
    return b, a


def _align_lower(tick: int, spacing: int) -> int:
    t = (tick // spacing) * spacing
    if t < MIN_TICK:
        t += spacing
    return t


def _align_upper(tick: int, spacing: int) -> int:
    t = (tick // spacing) * spacing
    if t > MAX_TICK:
        t -= spacing
    return t


def _held(token: dict, balances) -> int:
    addr = token["address"].lower()
    for item in balances or []:
        if (item.get("address") or "").lower() == addr:
            return int(item.get("raw") or 0)
    return 0


def list_slip_positions(wallet: str, token_a: dict | None = None) -> list[dict]:
    if not wallet:
        return []
    want = (token_a or {}).get("address", "").lower()
    usdc = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
    out = []
    for npm in NPMS:
        raw_n = _eth_call(npm, BALANCE_OF + _addr(wallet))
        n = int(_decode_uint(raw_n) or 0)
        for i in range(min(n, 20)):
            tid = int(_decode_uint(_eth_call(npm, TOKEN_OF_OWNER + _addr(wallet) + _pad_uint(i))) or 0)
            raw = _eth_call(npm, POSITIONS + _pad_uint(tid)) or "0x"
            hexdata = raw[2:]
            if len(hexdata) < 64 * 8:
                continue
            words = [hexdata[j * 64:(j + 1) * 64] for j in range(8)]
            token0 = "0x" + words[2][-40:]
            token1 = "0x" + words[3][-40:]
            tick_spacing = int(words[4], 16)
            if tick_spacing > 1 << 31:
                tick_spacing -= 1 << 256
            liquidity = int(words[7], 16)
            if liquidity <= 0:
                continue
            pair = {token0.lower(), token1.lower()}
            if want and want not in pair:
                continue
            # if usdc not in pair and not want:
            #     continue
            out.append({
                "npm": npm,
                "tokenId": str(tid),
                "token0": token0,
                "token1": token1,
                "tickSpacing": tick_spacing,
                "liquidity": str(liquidity),
            })
    return out


def build_slip_add(*, token_a, token_b, amount_a, amount_b, fraction, wallet, balances) -> dict:
    if not wallet:
        return {"error": "Connect a Base wallet to mint Slipstream LP."}
    if token_a is None or token_b is None:
        return {"error": "Need a stock and a quote token."}
    pool, tick, factory = find_cl_pool(token_a["address"], token_b["address"])
    print("[slip add] find_cl_pool", pool, tick, factory, flush=True)
    if not pool:
        return {"error": f"No Slipstream pool for {token_a['symbol']}/{token_b['symbol']}."}
    token0, token1 = _sort(token_a, token_b)
    frac = float(fraction) if fraction else 1.0
    held_a = _held(token_a, balances)
    held_b = _held(token_b, balances)
    wei_a = int(held_a * frac) if (fraction or not amount_a) else int(to_wei(amount_a, token_a["decimals"]))
    wei_b = int(held_b * frac) if (fraction or not amount_b) else int(to_wei(amount_b, token_b["decimals"]))
    if wei_a <= 0 or wei_b <= 0:
        return {"error": f"Need both {token_a['symbol']} and {token_b['symbol']} to add Slipstream LP."}
    amt0 = wei_a if token0["address"].lower() == token_a["address"].lower() else wei_b
    amt1 = wei_b if token0["address"].lower() == token_a["address"].lower() else wei_a

    slot = _eth_call(pool, "0x3850c7bd") or "0x"
    if slot != "0x" and len(slot) >= 66:
        sqrt_p = int(slot[2:66], 16)
        if sqrt_p > 0:
            q = (sqrt_p * sqrt_p) / float(1 << 192)
            need1 = int(amt0 * q)
            need0 = int(amt1 / q) if q else amt0
            if need1 <= amt1:
                amt1 = need1
            else:
                amt0 = need0

    if token0["address"].lower() == token_a["address"].lower():
        wei_a, wei_b = amt0, amt1
    else:
        wei_a, wei_b = amt1, amt0

    npm = FACTORY_NPM.get((factory or "").lower()) or NPMS[0]
    tick_l = _align_lower(MIN_TICK, tick)
    tick_u = _align_upper(MAX_TICK, tick)
    if tick_l >= tick_u:
        return {"error": f"Bad Slipstream ticks for spacing {tick}."}
    deadline = int(time.time()) + 1200
    data = "0x" + "".join([
        MINT[2:],
        _pad_uint(0x20),
        _addr(token0["address"]),
        _addr(token1["address"]),
        _pad_uint(tick),
        _pad_uint(tick_l),
        _pad_uint(tick_u),
        _pad_uint(amt0),
        _pad_uint(amt1),
        _pad_uint(0),
        _pad_uint(0),
        _addr(wallet),
        _pad_uint(deadline),
        _pad_uint(0),
    ])
    return {
        "type": "tx",
        "kind": "slip_lp_add",
        "protocol": "slipstream",
        "mock": False,
        "summary": (
            f"Mint Slipstream LP: {from_wei(wei_a, token_a['decimals'], 8)} {token_a['symbol']} + "
            f"{from_wei(wei_b, token_b['decimals'], 6)} {token_b['symbol']}"
        ),
        "spender": npm,
        "approvals": [
            {"symbol": token_a["symbol"], "address": token_a["address"], "amountWei": str(wei_a)},
            {"symbol": token_b["symbol"], "address": token_b["address"], "amountWei": str(wei_b)},
        ],
        "from": {
            "symbol": token_a["symbol"], "address": token_a["address"],
            "decimals": token_a["decimals"],
            "amount": from_wei(wei_a, token_a["decimals"], 8), "amountWei": str(wei_a),
        },
        "to": {
            "symbol": token_b["symbol"], "address": token_b["address"],
            "decimals": token_b["decimals"],
            "amount": from_wei(wei_b, token_b["decimals"], 6), "amountWei": str(wei_b),
        },
        "tx": {"to": npm, "data": data, "value": "0"},
        "raw": {
            "pool": pool,
            "tickSpacing": tick,
            "tickLower": tick_l,
            "tickUpper": tick_u,
            "npm": npm,
            "factory": factory,
            "token0": token0["address"],
            "token1": token1["address"],
            "amount0Desired": str(amt0),
            "amount1Desired": str(amt1),
        },
    }

def build_slip_remove(*, token_a, token_b, fraction, wallet, balances, token_id=None) -> dict:
    if not wallet:
        return {"error": "Connect a Base wallet to remove Slipstream LP."}
    positions = list_slip_positions(wallet, token_a)
    if token_id:
        positions = [p for p in positions if p["tokenId"] == str(token_id)]
    if not positions:
        return {"error": f"No Slipstream NFT found for {token_a['symbol']}."}
    pos = positions[0]
    liq = int(pos["liquidity"])
    frac = float(fraction or 1)
    burn_liq = max(int(liq * frac), 1) if frac < 1 else liq
    deadline = int(time.time()) + 1200
    dec = (
        DECREASE[2:]
        + _pad_uint(int(pos["tokenId"]))
        + _pad_uint(burn_liq)
        + _pad_uint(0)
        + _pad_uint(0)
        + _pad_uint(deadline)
    )
    col = (
        COLLECT[2:]
        + _pad_uint(int(pos["tokenId"]))
        + _addr(wallet)
        + _pad_uint(MAX_U128)
        + _pad_uint(MAX_U128)
    )
    parts = [dec, col]
    if frac >= 1:
        parts.append(BURN_NFT[2:] + _pad_uint(int(pos["tokenId"])))
    n = len(parts)
    head = MULTICALL[2:] + _pad_uint(0x20) + _pad_uint(n)
    offsets, payload, start = [], "", 32 * n
    for p in parts:
        offsets.append(_pad_uint(start))
        chunk = _pad_uint(len(p) // 2) + p
        pad = (32 - (len(chunk) // 2) % 32) % 32
        chunk = chunk + ("00" * pad)
        payload += chunk
        start += len(chunk) // 2
    return {
        "type": "tx",
        "kind": "slip_lp_remove",
        "protocol": "slipstream",
        "mock": False,
        "summary": f"Remove Slipstream LP NFT #{pos['tokenId']} ({int(frac*100)}%)",
        "spender": pos["npm"],
        "approvals": [],
        "from": {
            "symbol": token_a["symbol"], "address": token_a["address"],
            "decimals": token_a["decimals"], "amount": "LP", "amountWei": str(burn_liq),
        },
        "to": {
            "symbol": (token_b or {}).get("symbol") or "USDC",
            "address": (token_b or {}).get("address") or "",
            "decimals": (token_b or {}).get("decimals") or 6,
            "amount": "pool", "amountWei": "0",
        },
        "tx": {"to": pos["npm"], "data": "0x" + head + "".join(offsets) + payload, "value": "0"},
        "raw": pos,
    }