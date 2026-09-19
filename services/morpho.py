"""Morpho Blue on Base: supply collateral, borrow, repay, withdraw.

WETH/USDC isolated markets plus curator stock/USDC Blue markets
(AAPLc, GOOGLc, NVDAc, METAc, SPCXc). Midnight fixed-rate is not wired.
"""

from __future__ import annotations

import httpx

from services.quotes import from_wei, to_wei
from services.rpc import _eth_call

MORPHO = "0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb"
IRM = "0x46415998764C29aB2a25CbeA6254146D50D22687"

USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
WETH = "0x4200000000000000000000000000000000000006"

MARKETS = {
    "weth_usdc": {
        "id": "0x8793cf302b8ffd655ab97bd1c695dbd967807e8367a65cb2f4edaf1380ba1bda",
        "label": "WETH/USDC 86%",
        "collateral": "WETH",
        "loan": "USDC",
        "collateral_address": WETH,
        "loan_address": USDC,
        "collateral_decimals": 18,
        "loan_decimals": 6,
    },
    "usdc_weth": {
        "id": "0x3b3769cfca57be2eaed03fcc5299c25691b77781a1e124e7a8d520eb9a7eabb5",
        "label": "USDC/WETH 86%",
        "collateral": "USDC",
        "loan": "WETH",
        "collateral_address": USDC,
        "loan_address": WETH,
        "collateral_decimals": 6,
        "loan_decimals": 18,
    },
}

TOKENS = {
    "USDC": {"symbol": "USDC", "address": USDC, "decimals": 6},
    "WETH": {"symbol": "WETH", "address": WETH, "decimals": 18},
    "ETH": {"symbol": "WETH", "address": WETH, "decimals": 18},
}

STOCK_COLLATERALS = {
    "AAPL": ("0xb200000000000000000000C2e324d24d7eEcd1fb", 8, "AAPLC"),
    "AAPLC": ("0xb200000000000000000000C2e324d24d7eEcd1fb", 8, "AAPLC"),
    "GOOGL": ("0xb2000000000000000000002D0BA3164cc74f58B7", 8, "GOOGLC"),
    "GOOGLC": ("0xb2000000000000000000002D0BA3164cc74f58B7", 8, "GOOGLC"),
    "NVDA": ("0xb20000000000000000000078ee7ce2fE4908108C", 8, "NVDAC"),
    "NVDAC": ("0xb20000000000000000000078ee7ce2fE4908108C", 8, "NVDAC"),
    "META": ("0xb2000000000000000000008bC8786B856E61707C", 8, "METAC"),
    "METAC": ("0xb2000000000000000000008bC8786B856E61707C", 8, "METAC"),
    "SPCX": ("0xb2000000000000000000007b9fcbd005511aCBd5", 8, "SPCXC"),
    "SPCXC": ("0xb2000000000000000000007b9fcbd005511aCBd5", 8, "SPCXC"),
}

ID_TO_PARAMS = "0x2c3c9157"
POSITION = "0x93c52062"
SUPPLY_COLLATERAL = "0x238d6579"
WITHDRAW_COLLATERAL = "0x8720316d"
BORROW = "0x50d8cd4b"
REPAY = "0x20b76e81"

_ITEMS_FIELDS = """
                marketId
                lltv
                irmAddress
                oracleAddress
                collateralAsset { address symbol decimals }
                loanAsset { address symbol decimals }
"""

_STOCK_MARKETS_LOADED = False


def _pad_uint(value: int) -> str:
    return hex(int(value))[2:].rjust(64, "0")


def _addr(value: str) -> str:
    return value.lower().replace("0x", "").rjust(64, "0")


def _word(hexdata: str, i: int) -> str:
    return hexdata[i * 64:(i + 1) * 64]


def _norm(symbol: str | None) -> str:
    s = (symbol or "").upper().replace(" ", "").replace(".", "")
    s = {"ETH": "WETH", "ETHER": "WETH", "AWETH": "WETH", "AUSDC": "USDC", "USD": "USDC"}.get(s, s)
    if s in STOCK_COLLATERALS:
        return STOCK_COLLATERALS[s][2]
    return s


def listed(symbol: str | None) -> dict | None:
    key = _norm(symbol)
    if key in TOKENS:
        return TOKENS[key]
    if key in STOCK_COLLATERALS:
        addr, dec, canon = STOCK_COLLATERALS[key]
        return {"symbol": canon, "address": addr, "decimals": dec}
    return None


def _held_raw(token_addr: str, balances) -> int:
    for item in balances or []:
        if (item.get("address") or "").lower() == token_addr.lower():
            return int(item.get("raw") or 0)
    return 0


def _oracle_of(item: dict) -> str:
    raw = item.get("oracleAddress") or ""
    if isinstance(item.get("oracle"), dict):
        raw = raw or (item["oracle"].get("address") or "")
    return raw


def _params_from_meta(meta: dict) -> dict | None:
    if meta.get("id"):
        onchain = market_params(meta["id"])
        if onchain:
            return onchain
    oracle = meta.get("oracle") or ""
    lltv = int(meta.get("lltv") or 0)
    if not oracle or lltv <= 0:
        return None
    return {
        "loanToken": meta["loan_address"],
        "collateralToken": meta["collateral_address"],
        "oracle": oracle,
        "irm": meta.get("irm") or IRM,
        "lltv": lltv,
    }


def _load_stock_markets() -> None:
    global _STOCK_MARKETS_LOADED
    if _STOCK_MARKETS_LOADED:
        return
    _STOCK_MARKETS_LOADED = True
    addrs = list({row[0] for row in STOCK_COLLATERALS.values()})
    want = {a.lower() for a in addrs}
    query = {
        "query": f"""
        query ($addrs: [String!]) {{
          markets(
            first: 100
            where: {{ chainId_in: [8453], collateralAssetAddress_in: $addrs }}
          ) {{
            items {{
{_ITEMS_FIELDS}
            }}
          }}
        }}
        """,
        "variables": {"addrs": addrs},
    }
    items = []
    try:
        body = httpx.post("https://api.morpho.org/graphql", json=query, timeout=20.0).json()
        print("[morpho] gql errors", body.get("errors"), flush=True)
        items = (((body.get("data") or {}).get("markets") or {}).get("items") or [])
    except Exception as exc:
        print("[morpho] stock market lookup failed", exc, flush=True)

    if not items:
        fallback = {
            "query": f"""
            query {{
              markets(first: 1000, where: {{ chainId_in: [8453] }}) {{
                items {{
{_ITEMS_FIELDS}
                }}
              }}
            }}
            """
        }
        try:
            body = httpx.post("https://api.morpho.org/graphql", json=fallback, timeout=30.0).json()
            print("[morpho] fallback errors", body.get("errors"), flush=True)
            items = [
                it for it in (((body.get("data") or {}).get("markets") or {}).get("items") or [])
                if (it.get("collateralAsset") or {}).get("address", "").lower() in want
            ]
        except Exception as exc:
            print("[morpho] fallback failed", exc, flush=True)

    print("[morpho] stock markets found", len(items), flush=True)
    for item in items:
        loan = item.get("loanAsset") or {}
        coll = item.get("collateralAsset") or {}
        if (loan.get("address") or "").lower() != USDC.lower():
            continue
        addr = (coll.get("address") or "").lower()
        raw_sym = next((v[2] for v in STOCK_COLLATERALS.values() if v[0].lower() == addr), "")
        if not raw_sym:
            continue
        oracle = _oracle_of(item)
        irm = item.get("irmAddress") or IRM
        lltv = int(item.get("lltv") or 0)
        key = raw_sym.lower() + "_usdc"
        prev = MARKETS.get(key)
        if prev and (prev.get("irm") or "").lower() == IRM.lower() and irm.lower() != IRM.lower():
            continue
        MARKETS[key] = {
            "id": item.get("marketId") or item.get("uniqueKey"),
            "label": f"{raw_sym}/USDC {lltv / 10**16:.1f}%",
            "collateral": raw_sym,
            "loan": "USDC",
            "collateral_address": coll.get("address") or STOCK_COLLATERALS[raw_sym][0],
            "loan_address": USDC,
            "collateral_decimals": int(coll.get("decimals") or 8),
            "loan_decimals": 6,
            "oracle": oracle,
            "irm": irm,
            "lltv": lltv,
        }
        print("[morpho] loaded", key, MARKETS[key]["id"], "oracle", oracle, "irm", irm, flush=True)


def market_params(market_id: str) -> dict | None:
    if not market_id:
        return None
    raw = _eth_call(MORPHO, ID_TO_PARAMS + market_id[2:].rjust(64, "0"))
    if not raw or raw == "0x" or len(raw) < 2 + 64 * 5:
        return None
    h = raw[2:]

    def addr(i):
        return "0x" + _word(h, i)[24:]

    loan = addr(0)
    coll = addr(1)
    if int(loan, 16) == 0 or int(coll, 16) == 0:
        return None
    return {
        "loanToken": loan,
        "collateralToken": coll,
        "oracle": addr(2),
        "irm": addr(3),
        "lltv": int(_word(h, 4), 16),
    }


def _encode_market(p: dict) -> str:
    return (
        _addr(p["loanToken"])
        + _addr(p["collateralToken"])
        + _addr(p["oracle"])
        + _addr(p["irm"])
        + _pad_uint(p["lltv"])
    )


def _encode_bytes_tail(static_words: int) -> str:
    offset = static_words * 32
    return _pad_uint(offset) + _pad_uint(0)


def pick_market(*, collateral: str | None = None, loan: str | None = None) -> dict | None:
    _load_stock_markets()
    c = _norm(collateral) if collateral else None
    l = _norm(loan) if loan else None
    if l == "USDC" and not c:
        return None
    for key, meta in MARKETS.items():
        if c and _norm(meta["collateral"]) != c:
            continue
        if l and _norm(meta["loan"]) != l:
            continue
        params = _params_from_meta(meta)
        if not params:
            continue
        return {**meta, "key": key, "params": params}
    return None


def _market_with_debt(*, loan: str, collateral: str | None, wallet: str) -> dict | None:
    _load_stock_markets()
    l = _norm(loan)
    c = _norm(collateral) if collateral else None
    if c:
        return pick_market(collateral=c, loan=l)
    for key, meta in MARKETS.items():
        if _norm(meta["loan"]) != l:
            continue
        params = _params_from_meta(meta)
        if not params:
            continue
        pos = position(meta["id"], wallet) or {}
        if int(pos.get("borrowShares") or 0) <= 0:
            continue
        return {**meta, "key": key, "params": params}
    return pick_market(loan=l) if l != "USDC" else None


def position(market_id: str, wallet: str) -> dict | None:
    if not market_id:
        return None
    raw = _eth_call(MORPHO, POSITION + market_id[2:].rjust(64, "0") + _addr(wallet))
    if not raw or raw == "0x" or len(raw) < 2 + 64 * 3:
        return None
    h = raw[2:]
    return {
        "supplyShares": int(_word(h, 0), 16),
        "borrowShares": int(_word(h, 1), 16),
        "collateral": int(_word(h, 2), 16),
    }


def describe_account(wallet: str) -> str:
    if not wallet:
        return "Connect a Base wallet to read Morpho."
    _load_stock_markets()
    lines = ["Morpho Blue on Base (WETH/USDC and stock/USDC variable markets):"]
    any_pos = False
    for meta in MARKETS.values():
        pos = position(meta["id"], wallet)
        if not pos:
            continue
        coll = pos["collateral"] / (10 ** meta["collateral_decimals"])
        shares = pos["borrowShares"]
        if coll <= 0 and shares <= 0 and pos["supplyShares"] <= 0:
            continue
        any_pos = True
        lines.append(
            f"{meta['label']}: collateral {coll:.6f} {meta['collateral']}, "
            f"borrowShares {shares}, supplyShares {pos['supplyShares']}"
        )
    if not any_pos:
        lines.append("No Morpho position.")
    lines.append(
        "Stock collateral markets: AAPLc, GOOGLc, NVDAc, METAc, SPCXc → borrow USDC. "
        "Not available to US persons."
    )
    return "\n".join(lines)


def _card(*, kind, summary, approvals, frm, to, data, raw=None):
    return {
        "type": "tx",
        "kind": kind,
        "protocol": "morpho",
        "mock": False,
        "summary": summary,
        "spender": MORPHO,
        "approvals": approvals,
        "from": frm,
        "to": to,
        "tx": {"to": MORPHO, "data": data, "value": "0"},
        "raw": raw or {"pool": MORPHO},
    }


def _token_row(symbol: str, address: str, decimals: int, amount: str, wei: str) -> dict:
    return {
        "symbol": symbol,
        "address": address,
        "decimals": decimals,
        "amount": amount,
        "amountWei": wei,
    }


def build_morpho_supply(*, token: dict, amount: str | None, fraction, wallet, balances) -> dict:
    if not wallet:
        return {"error": "Connect a Base wallet to supply Morpho collateral."}
    asset = listed((token or {}).get("symbol"))
    print("[morpho] supply", (token or {}).get("symbol"), "listed", asset, flush=True)
    if not asset:
        return {"error": "Morpho collateral must be WETH, USDC, AAPL, GOOGL, NVDA, META, or SPCX."}
    market = pick_market(collateral=asset["symbol"])
    print("[morpho] pick", None if not market else market.get("label"), flush=True)
    if not market:
        return {"error": f"No Morpho market on Base uses {asset['symbol']} as collateral."}
    wei = int(to_wei(amount, asset["decimals"])) if amount else 0
    if wei <= 0 and fraction:
        wei = int(_held_raw(asset["address"], balances) * float(fraction))
    if wei <= 0:
        wei = _held_raw(asset["address"], balances)
    if wei <= 0:
        return {"error": f"No {asset['symbol']} to supply as Morpho collateral."}
    human = from_wei(wei, asset["decimals"])
    encoded = _encode_market(market["params"])
    data = (
        SUPPLY_COLLATERAL
        + encoded
        + _pad_uint(wei)
        + _addr(wallet)
        + _encode_bytes_tail(8)
    )
    return _card(
        kind="morpho_supply",
        summary=f"Supply {human} {asset['symbol']} as Morpho collateral ({market['label']})",
        approvals=[{"symbol": asset["symbol"], "address": asset["address"], "amountWei": str(wei)}],
        frm=_token_row(asset["symbol"], asset["address"], asset["decimals"], human, str(wei)),
        to=_token_row(asset["symbol"], asset["address"], asset["decimals"], human, str(wei)),
        data=data,
        raw={"pool": MORPHO, "market": market["id"], "label": market["label"]},
    )


def build_morpho_withdraw(*, token: dict, amount: str | None, fraction, wallet, balances) -> dict:
    if not wallet:
        return {"error": "Connect a Base wallet to withdraw Morpho collateral."}
    asset = listed((token or {}).get("symbol"))
    if not asset:
        return {"error": "Morpho collateral must be WETH, USDC, AAPL, GOOGL, NVDA, META, or SPCX."}
    market = pick_market(collateral=asset["symbol"])
    if not market:
        return {"error": f"No Morpho market on Base uses {asset['symbol']} as collateral."}
    pos = position(market["id"], wallet) or {}
    posted = int(pos.get("collateral") or 0)
    if amount:
        wei = int(to_wei(amount, asset["decimals"]))
    elif fraction:
        wei = int(posted * float(fraction)) if posted else 0
    else:
        wei = posted
    if wei <= 0:
        wei = posted
    if wei <= 0:
        return {"error": f"No {asset['symbol']} Morpho collateral to withdraw."}
    human = from_wei(wei, asset["decimals"])
    data = (
        WITHDRAW_COLLATERAL
        + _encode_market(market["params"])
        + _pad_uint(wei)
        + _addr(wallet)
        + _addr(wallet)
    )
    return _card(
        kind="morpho_withdraw",
        summary=f"Withdraw {human} {asset['symbol']} Morpho collateral ({market['label']})",
        approvals=[],
        frm=_token_row(asset["symbol"], asset["address"], asset["decimals"], human, str(wei)),
        to=_token_row(asset["symbol"], asset["address"], asset["decimals"], human, str(wei)),
        data=data,
        raw={"pool": MORPHO, "market": market["id"], "label": market["label"]},
    )


def build_morpho_borrow(*, token: dict, amount: str | None, fraction, wallet, balances, collateral_symbol: str | None = None) -> dict:
    if not wallet:
        return {"error": "Connect a Base wallet to borrow on Morpho."}
    asset = listed((token or {}).get("symbol"))
    if not asset:
        return {"error": "Morpho borrow asset must be USDC or WETH."}
    if not amount:
        return {"error": "How much should I borrow on Morpho? Example: borrow 5 USDC from Morpho against AAPL."}
    market = (
        pick_market(collateral=collateral_symbol, loan=asset["symbol"])
        if collateral_symbol
        else _market_with_debt(loan=asset["symbol"], collateral=None, wallet=wallet)
    )
    if not market and asset["symbol"] == "USDC":
        return {
            "error": (
                "Say which collateral to borrow USDC against: WETH, AAPL, GOOGL, NVDA, META, or SPCX."
            )
        }
    if not market:
        return {"error": f"No Morpho market on Base lends {asset['symbol']}."}
    pos = position(market["id"], wallet) or {}
    if int(pos.get("collateral") or 0) <= 0:
        return {
            "error": (
                f"No Morpho collateral in {market['label']}. "
                f"Supply {market['collateral']} first, then borrow {market['loan']}."
            )
        }
    wei = int(to_wei(amount, asset["decimals"]))
    if wei <= 0:
        return {"error": "Borrow amount must be greater than 0."}
    human = from_wei(wei, asset["decimals"])
    data = (
        BORROW
        + _encode_market(market["params"])
        + _pad_uint(wei)
        + _pad_uint(0)
        + _addr(wallet)
        + _addr(wallet)
    )
    return _card(
        kind="morpho_borrow",
        summary=f"Borrow {human} {asset['symbol']} from Morpho ({market['label']})",
        approvals=[],
        frm=_token_row(asset["symbol"], asset["address"], asset["decimals"], human, str(wei)),
        to=_token_row(asset["symbol"], asset["address"], asset["decimals"], human, str(wei)),
        data=data,
        raw={"pool": MORPHO, "market": market["id"], "label": market["label"]},
    )


def build_morpho_repay(*, token: dict, amount: str | None, fraction, wallet, balances, collateral_symbol: str | None = None) -> dict:
    if not wallet:
        return {"error": "Connect a Base wallet to repay Morpho."}
    asset = listed((token or {}).get("symbol"))
    if not asset:
        return {"error": "Morpho repay asset must be USDC or WETH."}
    market = _market_with_debt(loan=asset["symbol"], collateral=collateral_symbol, wallet=wallet)
    if not market:
        return {"error": f"No Morpho {asset['symbol']} debt to repay."}
    pos = position(market["id"], wallet) or {}
    if int(pos.get("borrowShares") or 0) <= 0:
        return {"error": f"No Morpho {asset['symbol']} debt to repay."}
    held = _held_raw(asset["address"], balances)
    if amount:
        wei = int(to_wei(amount, asset["decimals"]))
    elif fraction:
        wei = int(held * float(fraction)) if held else 0
    else:
        wei = held
    if wei <= 0:
        return {"error": f"No {asset['symbol']} in the wallet to repay Morpho with."}
    human = from_wei(wei, asset["decimals"])
    data = (
        REPAY
        + _encode_market(market["params"])
        + _pad_uint(wei)
        + _pad_uint(0)
        + _addr(wallet)
        + _encode_bytes_tail(9)
    )
    return _card(
        kind="morpho_repay",
        summary=f"Repay {human} {asset['symbol']} on Morpho ({market['label']})",
        approvals=[{"symbol": asset["symbol"], "address": asset["address"], "amountWei": str(wei)}],
        frm=_token_row(asset["symbol"], asset["address"], asset["decimals"], human, str(wei)),
        to=_token_row(asset["symbol"], asset["address"], asset["decimals"], human, str(wei)),
        data=data,
        raw={"pool": MORPHO, "market": market["id"], "label": market["label"]},
    )