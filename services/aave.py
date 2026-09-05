"""Aave V3 Base: supply, withdraw, borrow, repay. Stocks are not listed."""

from __future__ import annotations

from services.quotes import from_wei, to_wei
from services.rpc import _eth_call

POOL = "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5"
SUPPLY = "0x617ba037"
WITHDRAW = "0x69328dec"
BORROW = "0xa415bcad"
REPAY = "0x573ade81"
SET_COLLATERAL = "0x5a3b74b9"
GET_ACCOUNT = "0xbf92857c"
VARIABLE = 2

LISTED = {
    "USDC": {
        "symbol": "USDC",
        "address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "decimals": 6,
        "a_token": "0x4e65fE4DbA92790696d040ac24Aa414708F5c0AB",
    },
    "WETH": {
        "symbol": "WETH",
        "address": "0x4200000000000000000000000000000000000006",
        "decimals": 18,
        "a_token": "0xD4a0e0b9149BCee3C920d2E00b5dE09138fd8bb7",
    },
}

_AAVE_ONLY = (
    "Aave lending on Base is only for USDC and WETH. "
    "Tokenized stocks cannot be supplied, used as collateral, borrowed, or repaid."
)


def _pad_uint(value: int) -> str:
    return hex(int(value))[2:].rjust(64, "0")


def _addr(value: str) -> str:
    return value.lower().replace("0x", "").rjust(64, "0")


def listed_asset(token: dict) -> dict | None:
    if not token:
        return None
    for item in LISTED.values():
        if item["address"].lower() == (token.get("address") or "").lower():
            return item
        if item["symbol"].upper() == (token.get("symbol") or "").upper().replace("C", "") if False else (token.get("symbol") or "").upper():
            return item
        sym = (token.get("symbol") or "").upper()
        if sym == item["symbol"] or sym.rstrip("C") == item["symbol"]:
            if item["symbol"] in {"USDC", "WETH"} and sym in {"USDC", "WETH"}:
                return item
    for item in LISTED.values():
        if (token.get("symbol") or "").upper() == item["symbol"]:
            return item
    return None


def _held_raw(token_addr: str, balances) -> int:
    for item in balances or []:
        if (item.get("address") or "").lower() == token_addr.lower():
            return int(item.get("raw") or 0)
    return 0


def get_account(wallet: str) -> dict | None:
    if not wallet:
        return None
    raw = _eth_call(POOL, GET_ACCOUNT + _addr(wallet))
    if not raw or raw == "0x" or len(raw) < 2 + 64 * 6:
        return None
    hexdata = raw[2:]

    def u(i):
        return int(hexdata[i * 64:(i + 1) * 64], 16)

    hf = u(5)
    return {
        "collateral_usd": u(0) / 1e8,
        "debt_usd": u(1) / 1e8,
        "available_usd": u(2) / 1e8,
        "ltv": u(4) / 10000,
        "health_factor": None if hf > 2**255 else hf / 1e18,
    }


def describe_account(wallet: str) -> str:
    acct = get_account(wallet)
    if not acct:
        return "Could not read your Aave V3 Base account."
    hf = acct["health_factor"]
    hf_s = "∞" if hf is None else f"{hf:.2f}"
    return (
        "Aave V3 on Base (USD):\n"
        f"Collateral: ${acct['collateral_usd']:.2f}\n"
        f"Debt: ${acct['debt_usd']:.2f}\n"
        f"Available to borrow: ${acct['available_usd']:.2f}\n"
        f"Health factor: {hf_s}\n"
        "Lending is USDC and WETH only."
    )


def _card(*, kind, summary, approvals, frm, to, data):
    return {
        "type": "tx",
        "kind": kind,
        "protocol": "aave",
        "mock": False,
        "summary": summary,
        "spender": POOL,
        "approvals": approvals,
        "from": frm,
        "to": to,
        "tx": {"to": POOL, "data": data, "value": "0"},
        "raw": {"pool": POOL},
    }


def build_aave_supply(*, token: dict, amount: str | None, fraction, wallet, balances) -> dict:
    if not wallet:
        return {"error": "Connect a Base wallet to supply on Aave."}
    asset = listed_asset(token)
    if not asset:
        return {"error": _AAVE_ONLY}
    wei = int(to_wei(amount, asset["decimals"])) if amount else 0
    if wei <= 0 and fraction:
        wei = int(_held_raw(asset["address"], balances) * float(fraction))
    if wei <= 0:
        wei = _held_raw(asset["address"], balances)
    if wei <= 0:
        return {"error": f"No {asset['symbol']} to supply."}
    data = SUPPLY + _addr(asset["address"]) + _pad_uint(wei) + _addr(wallet) + _pad_uint(0)
    human = from_wei(wei, asset["decimals"])
    return _card(
        kind="aave_supply",
        summary=f"Supply {human} {asset['symbol']} to Aave V3 on Base",
        approvals=[{"symbol": asset["symbol"], "address": asset["address"], "amountWei": str(wei)}],
        frm={"symbol": asset["symbol"], "address": asset["address"], "decimals": asset["decimals"], "amount": human, "amountWei": str(wei)},
        to={"symbol": f"a{asset['symbol']}", "address": asset["a_token"], "decimals": asset["decimals"], "amount": human, "amountWei": str(wei)},
        data=data,
    )


def build_aave_withdraw(*, token: dict, amount: str | None, fraction, wallet, balances) -> dict:
    if not wallet:
        return {"error": "Connect a Base wallet to withdraw from Aave."}
    asset = listed_asset(token)
    if not asset:
        return {"error": _AAVE_ONLY}
    a_bal = _held_raw(asset["a_token"], balances)
    if amount:
        wei = int(to_wei(amount, asset["decimals"]))
    elif fraction:
        wei = int(a_bal * float(fraction)) if a_bal else 0
    else:
        wei = a_bal
    if wei <= 0:
        wei = 2**256 - 1
    data = WITHDRAW + _addr(asset["address"]) + _pad_uint(wei) + _addr(wallet)
    label = "max" if wei == 2**256 - 1 else from_wei(wei, asset["decimals"])
    return _card(
        kind="aave_withdraw",
        summary=f"Withdraw {label} {asset['symbol']} from Aave V3 on Base",
        approvals=[],
        frm={"symbol": f"a{asset['symbol']}", "address": asset["a_token"], "decimals": asset["decimals"], "amount": label, "amountWei": str(wei if wei != 2**256 - 1 else a_bal)},
        to={"symbol": asset["symbol"], "address": asset["address"], "decimals": asset["decimals"], "amount": label, "amountWei": str(wei if wei != 2**256 - 1 else a_bal)},
        data=data,
    )


def build_aave_collateral(*, token: dict, wallet, enabled: bool = True) -> dict:
    if not wallet:
        return {"error": "Connect a Base wallet."}
    asset = listed_asset(token)
    if not asset:
        return {"error": _AAVE_ONLY}
    data = SET_COLLATERAL + _addr(asset["address"]) + _pad_uint(1 if enabled else 0)
    return _card(
        kind="aave_collateral",
        summary=f"{'Enable' if enabled else 'Disable'} {asset['symbol']} as Aave collateral",
        approvals=[],
        frm={"symbol": asset["symbol"], "address": asset["address"], "decimals": asset["decimals"], "amount": "0", "amountWei": "0"},
        to={"symbol": asset["symbol"], "address": asset["address"], "decimals": asset["decimals"], "amount": "0", "amountWei": "0"},
        data=data,
    )


def build_aave_borrow(*, token: dict, amount: str | None, fraction, wallet, balances) -> dict:
    if not wallet:
        return {"error": "Connect a Base wallet to borrow on Aave."}
    asset = listed_asset(token)
    if not asset:
        return {"error": _AAVE_ONLY}
    if not amount:
        return {"error": "How much should I borrow? Example: borrow 5 USDC from Aave."}
    wei = int(to_wei(amount, asset["decimals"]))
    if wei <= 0:
        return {"error": "Borrow amount must be greater than 0."}
    acct = get_account(wallet)
    if acct:
        if acct["collateral_usd"] <= 0:
            return {
                "error": (
                    "No Aave collateral. Supply USDC or WETH first, then enable it as collateral. "
                    "Tokenized stocks cannot be used."
                )
            }
        need = float(amount)
        if acct["available_usd"] + 1e-6 < need:
            return {
                "error": (
                    f"Not enough collateral. You can borrow about ${acct['available_usd']:.2f}. "
                    f"Collateral ${acct['collateral_usd']:.2f}, debt ${acct['debt_usd']:.2f}."
                )
            }
    data = BORROW + _addr(asset["address"]) + _pad_uint(wei) + _pad_uint(VARIABLE) + _pad_uint(0) + _addr(wallet)
    human = from_wei(wei, asset["decimals"])
    return _card(
        kind="aave_borrow",
        summary=f"Borrow {human} {asset['symbol']} from Aave V3 (variable rate)",
        approvals=[],
        frm={"symbol": asset["symbol"], "address": asset["address"], "decimals": asset["decimals"], "amount": human, "amountWei": str(wei)},
        to={"symbol": asset["symbol"], "address": asset["address"], "decimals": asset["decimals"], "amount": human, "amountWei": str(wei)},
        data=data,
    )


def build_aave_repay(*, token: dict, amount: str | None, fraction, wallet, balances) -> dict:
    if not wallet:
        return {"error": "Connect a Base wallet to repay Aave debt."}
    asset = listed_asset(token)
    if not asset:
        return {"error": _AAVE_ONLY}
    acct = get_account(wallet)
    if acct and acct["debt_usd"] <= 0:
        return {"error": "You have no Aave debt to repay."}
    held = _held_raw(asset["address"], balances)
    if amount:
        wei = int(to_wei(amount, asset["decimals"]))
    elif fraction:
        wei = int(held * float(fraction)) if held else 0
    else:
        wei = held
    if wei <= 0:
        wei = 2**256 - 1
    if held <= 0:
        return {"error": f"No {asset['symbol']} in the wallet to repay with."}
    data = REPAY + _addr(asset["address"]) + _pad_uint(wei) + _pad_uint(VARIABLE) + _addr(wallet)
    label = "max" if wei == 2**256 - 1 else from_wei(wei, asset["decimals"])
    approve_wei = str(held if wei == 2**256 - 1 else wei)
    return _card(
        kind="aave_repay",
        summary=f"Repay {label} {asset['symbol']} on Aave V3",
        approvals=[{"symbol": asset["symbol"], "address": asset["address"], "amountWei": approve_wei}],
        frm={"symbol": asset["symbol"], "address": asset["address"], "decimals": asset["decimals"], "amount": label, "amountWei": approve_wei},
        to={"symbol": asset["symbol"], "address": asset["address"], "decimals": asset["decimals"], "amount": label, "amountWei": approve_wei},
        data=data,
    )