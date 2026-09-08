"""Morpho Blue on Base: supply collateral, borrow, repay, withdraw.

Isolated markets only. Default book is WETH/USDC 86% LLTV.
Tokenized stocks are not wired — there is no official B20 Morpho market in this adapter.
"""

from __future__ import annotations

from services.quotes import from_wei, to_wei
from services.rpc import _eth_call

MORPHO = "0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb"
IRM = "0x46415998764C29aB2a25CbeA6254146D50D22687"

USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
WETH = "0x4200000000000000000000000000000000000006"

# Official liquid Base markets (params loaded via idToMarketParams).
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

ID_TO_PARAMS = "0x2c3ad262"
POSITION = "0x93c52062"
SUPPLY_COLLATERAL = "0x238d6579"
WITHDRAW_COLLATERAL = "0x8720316d"
BORROW = "0x50d8cd4b"
REPAY = "0x20b76e81"

_STOCKS = (
    "Morpho on Stocktalk is WETH and USDC only (isolated Blue markets). "
    "Tokenized stocks are not listed on these Morpho markets."
)


def _pad_uint(value: int) -> str:
    return hex(int(value))[2:].rjust(64, "0")


def _addr(value: str) -> str:
    return value.lower().replace("0x", "").rjust(64, "0")


def _word(hexdata: str, i: int) -> str:
    return hexdata[i * 64:(i + 1) * 64]


def _norm(symbol: str | None) -> str:
    s = (symbol or "").upper().replace(" ", "")
    return {"ETH": "WETH", "ETHER": "WETH", "AWETH": "WETH", "AUSDC": "USDC", "USD": "USDC"}.get(s, s)


def listed(symbol: str | None) -> dict | None:
    return TOKENS.get(_norm(symbol))


def _held_raw(token_addr: str, balances) -> int:
    for item in balances or []:
        if (item.get("address") or "").lower() == token_addr.lower():
            return int(item.get("raw") or 0)
    return 0


def market_params(market_id: str) -> dict | None:
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
    c = _norm(collateral) if collateral else None
    l = _norm(loan) if loan else None
    for key, meta in MARKETS.items():
        if c and meta["collateral"] != c:
            continue
        if l and meta["loan"] != l:
            continue
        params = market_params(meta["id"])
        if not params:
            continue
        return {**meta, "key": key, "params": params}
    return None


def position(market_id: str, wallet: str) -> dict | None:
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
    lines = ["Morpho Blue on Base (isolated markets):"]
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
        lines.append("No Morpho WETH/USDC position.")
    lines.append("Stocks cannot be used on these Morpho markets.")
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
    if not asset:
        return {"error": _STOCKS}
    market = pick_market(collateral=asset["symbol"])
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
        + _encode_bytes_tail(7)
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
        return {"error": _STOCKS}
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


def build_morpho_borrow(*, token: dict, amount: str | None, fraction, wallet, balances) -> dict:
    if not wallet:
        return {"error": "Connect a Base wallet to borrow on Morpho."}
    asset = listed((token or {}).get("symbol"))
    if not asset:
        return {"error": _STOCKS}
    if not amount:
        return {"error": "How much should I borrow on Morpho? Example: borrow 5 USDC from Morpho."}
    market = pick_market(loan=asset["symbol"])
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


def build_morpho_repay(*, token: dict, amount: str | None, fraction, wallet, balances) -> dict:
    if not wallet:
        return {"error": "Connect a Base wallet to repay Morpho."}
    asset = listed((token or {}).get("symbol"))
    if not asset:
        return {"error": _STOCKS}
    market = pick_market(loan=asset["symbol"])
    if not market:
        return {"error": f"No Morpho market on Base lends {asset['symbol']}."}
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
        + _encode_bytes_tail(8)
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