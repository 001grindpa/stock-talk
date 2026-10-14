"""Read-only DeFi and LP account summaries for the sidebar."""

import re

from agent.registry import OFFICIAL_TOKENS
from services.aave import LISTED as AAVE_V3
from services.aave_v4 import COLLATERAL as AAVE_V4, _user_position, reserve_id
from services.morpho import MARKETS as MORPHO_MARKETS, _load_stock_markets, position as morpho_position
from services.rpc import token_balance
from services.slipstream_lp import list_slip_positions
from services.uniswap_lp import list_uni_positions

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


def list_withdrawable_positions(wallet: str, protocol: str) -> list[dict]:
    if not wallet:
        return []
    tokens_by_address = {t["address"].lower(): t for t in OFFICIAL_TOKENS if t.get("address")}
    positions = []

    if protocol == "aerodrome":
        for token0, token1, pool, stable in _KNOWN_AERO_POOLS:
            raw = int(token_balance(pool, wallet) or 0)
            if raw <= 0:
                continue
            first = tokens_by_address.get(token0.lower())
            second = tokens_by_address.get(token1.lower())
            if not first or not second:
                continue
            amount = raw / 10**18
            balance = f"{amount:.8f} LP"
            positions.append({
                "id": pool,
                "protocol": protocol,
                "from_symbol": first["symbol"],
                "to_symbol": second["symbol"],
                "stable": stable,
                "label": f"{first['symbol']}/{second['symbol']} ({'stable' if stable else 'volatile'})",
                "balance": balance,
                "amount_raw": str(raw),
                "amount_decimals": 18,
                "amount_symbol": "LP",
            })
    elif protocol in {"uniswap", "slipstream"}:
        reader = list_uni_positions if protocol == "uniswap" else list_slip_positions
        try:
            found = reader(wallet, None)
        except Exception:
            found = []
        for pos in found:
            first = tokens_by_address.get((pos.get("token0") or "").lower())
            second = tokens_by_address.get((pos.get("token1") or "").lower())
            if not first or not second:
                continue
            token_id = str(pos["tokenId"])
            detail = f"NFT #{token_id} · liquidity {pos['liquidity']}"
            if protocol == "uniswap" and "fee" in pos:
                detail += f" · {pos['fee'] / 10000:.2f}% fee"
            elif protocol == "slipstream" and "tickSpacing" in pos:
                detail += f" · tick {pos['tickSpacing']}"
            positions.append({
                "id": token_id,
                "protocol": protocol,
                "from_symbol": first["symbol"],
                "to_symbol": second["symbol"],
                "label": f"{first['symbol']}/{second['symbol']} · {detail}",
                "balance": detail,
                "amount_raw": str(pos["liquidity"]),
                "amount_decimals": 0,
                "amount_symbol": "liquidity units",
            })
    elif protocol == "aave":
        for asset in AAVE_V3.values():
            raw = int(token_balance(asset["a_token"], wallet) or 0)
            if raw <= 0:
                continue
            amount = raw / 10**asset["decimals"]
            positions.append({
                "id": asset["symbol"],
                "protocol": protocol,
                "from_symbol": asset["symbol"],
                "to_symbol": asset["symbol"],
                "label": f"{amount:.8f} {asset['symbol']} supplied",
                "balance": f"{amount:.8f} {asset['symbol']} supplied",
                "amount_raw": str(raw),
                "amount_decimals": asset["decimals"],
                "amount_symbol": asset["symbol"],
            })
    elif protocol == "aave_v4":
        for asset in AAVE_V4.values():
            rid = reserve_id(asset["address"])
            if rid is None:
                continue
            _, supplied = _user_position(rid, wallet)
            if supplied <= 0:
                continue
            amount = supplied / 10**asset["decimals"]
            positions.append({
                "id": asset["symbol"],
                "protocol": protocol,
                "from_symbol": asset["symbol"],
                "to_symbol": asset["symbol"],
                "label": f"{amount:.8f} {asset['symbol']} supplied",
                "balance": f"{amount:.8f} {asset['symbol']} supplied",
                "amount_raw": str(supplied),
                "amount_decimals": asset["decimals"],
                "amount_symbol": asset["symbol"],
            })
    elif protocol == "morpho":
        _load_stock_markets()
        for market in MORPHO_MARKETS.values():
            current = morpho_position(market.get("id"), wallet) or {}
            raw = int(current.get("collateral") or 0)
            if raw <= 0:
                continue
            amount = raw / 10**market["collateral_decimals"]
            symbol = market["collateral"]
            positions.append({
                "id": market["id"],
                "protocol": protocol,
                "from_symbol": symbol,
                "to_symbol": symbol,
                "label": f"{amount:.8f} {symbol} · {market['label']}",
                "balance": f"{amount:.8f} {symbol} collateral",
                "amount_raw": str(raw),
                "amount_decimals": market["collateral_decimals"],
                "amount_symbol": symbol,
            })

    return positions
