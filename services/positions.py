"""Read-only DeFi and LP account summaries for the sidebar."""

import re

from flask import Blueprint, jsonify, request

from agent.registry import OFFICIAL_TOKENS
from services.aave import describe_account as describe_aave_v3
from services.aave_v4 import describe_v4_account
from services.aerodrome import find_pool
from services.morpho import describe_account as describe_morpho
from services.rpc import token_balance
from services.slipstream_lp import list_slip_positions
from services.uniswap_lp import list_uni_positions

positions_blueprint = Blueprint("positions", __name__)
WALLET_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")

_KNOWN_AERO_POOLS: list[tuple[str, str, str, bool]] = [
    (
        "0xb200000000000000000000c2e324d24d7eecd1fb",  # AAPLc
        "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # USDC
        "0x6b74fc52dd84beb8d2d1be16732749dee70c45e7",
        False,
    ),
    (
        "0xb20000000000000000000078ee7ce2fe4908108c",  # NVDAc
        "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # USDC
        "0x2e39a9018330c8784956998185d23d9db503d1f7",
        False,
    ),
    (
        "0xb20000000000000000000078ee7ce2fe4908108c",  # NVDAc
        "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf",  # cbBTC
        "0x79edcedf384b2a113962584666a47102fe20bec5",
        False,
    ),
    (
        "0x4200000000000000000000000000000000000006",  # WETH
        "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # USDC
        "0xcdac0d6c6c59727a65f871236188350531885c43",
        False,
    ),
]

_POOL_CACHE: dict[tuple[str, str], tuple[str | None, bool]] = {}
for _t0, _t1, _pool, _stable in _KNOWN_AERO_POOLS:
    _POOL_CACHE[(_t0.lower(), _t1.lower())] = (_pool, _stable)
    _POOL_CACHE[(_t1.lower(), _t0.lower())] = (_pool, _stable)


def _get_pool(token_a: str, token_b: str) -> tuple[str | None, bool]:
    key = (token_a.lower(), token_b.lower())
    if key not in _POOL_CACHE:
        res = find_pool(token_a, token_b)
        _POOL_CACHE[key] = res
        _POOL_CACHE[(token_b.lower(), token_a.lower())] = res
    return _POOL_CACHE[key]


def describe_lp(wallet: str) -> str:
    if not wallet:
        return "LP positions:\nNo LP positions"
    tokens = OFFICIAL_TOKENS
    addr_to_sym = {t["address"].lower(): t["symbol"] for t in tokens if "address" in t}
    lines, seen = [], set()

    # Check Aerodrome pools
    for t0_addr, t1_addr, pool_addr, stable in _KNOWN_AERO_POOLS:
        if pool_addr.lower() in seen:
            continue
        seen.add(pool_addr.lower())
        raw = token_balance(pool_addr, wallet) or 0
        if raw <= 0:
            continue
        human = raw / 10**18
        shown = f"{human:.8f}" if raw >= 10**10 else f"{raw} wei ({human:.18f})"
        sym0 = addr_to_sym.get(t0_addr.lower(), "TOKEN0")
        sym1 = addr_to_sym.get(t1_addr.lower(), "TOKEN1")
        lines.append(
            f"Aerodrome {sym0}/{sym1} "
            f"({'stable' if stable else 'volatile'}): {shown} LP ({pool_addr})"
        )

    try:
        uni_positions = list_uni_positions(wallet, None)
    except Exception:
        uni_positions = []
    for pos in uni_positions:
        t0_sym = addr_to_sym.get((pos.get("token0") or "").lower())
        t1_sym = addr_to_sym.get((pos.get("token1") or "").lower())
        pair_label = f"{t0_sym}/{t1_sym}" if (t0_sym and t1_sym) else (t0_sym or t1_sym or "")
        pair_str = f" {pair_label}" if pair_label else ""
        fee_pct = f"{pos['fee'] / 10000:.2f}%" if "fee" in pos else ""
        fee_str = f" fee {fee_pct}" if fee_pct else ""
        lines.append(
            f"Uniswap V3{pair_str} NFT #{pos['tokenId']}{fee_str} liquidity {pos['liquidity']} ({pos.get('token0')}/{pos.get('token1')})"
        )

    try:
        slip_positions = list_slip_positions(wallet, None)
    except Exception:
        slip_positions = []
    for pos in slip_positions:
        t0_sym = addr_to_sym.get((pos.get("token0") or "").lower())
        t1_sym = addr_to_sym.get((pos.get("token1") or "").lower())
        pair_label = f"{t0_sym}/{t1_sym}" if (t0_sym and t1_sym) else (t0_sym or t1_sym or "")
        pair_str = f" {pair_label}" if pair_label else ""
        tick_str = f" tick {pos['tickSpacing']}" if "tickSpacing" in pos else ""
        lines.append(
            f"Slipstream{pair_str} NFT #{pos['tokenId']}{tick_str} liquidity {pos['liquidity']} ({pos.get('token0')}/{pos.get('token1')})"
        )

    if not lines:
        return "LP positions:\nNo LP positions"
    return "LP positions:\n" + "\n".join(lines)


@positions_blueprint.get("/api/positions")
def get_positions():
    wallet = (request.args.get("wallet") or "").strip().lower()
    if not WALLET_RE.match(wallet):
        return jsonify({"error": "valid wallet is required"}), 400

    try:
        positions = "\n\n".join(
            (
                describe_aave_v3(wallet),
                describe_v4_account(wallet),
                describe_morpho(wallet),
                describe_lp(wallet),
            )
        )
    except Exception:
        return jsonify({"error": "positions unavailable"}), 502
    return jsonify({"positions": positions})
