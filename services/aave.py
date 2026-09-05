"""Aave V3 Base supply/withdraw. Not AMM LP. Stocks are usually not listed."""

from __future__ import annotations

from services.quotes import from_wei, to_wei
from services.rpc import _decode_uint, _eth_call

POOL = "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5"
SUPPLY = "0x617ba037"     # supply(address,uint256,address,uint16)
WITHDRAW = "0x69328dec"   # withdraw(address,uint256,address)
GET_RESERVE = "0x35ea6a75"

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


def _pad_uint(value: int) -> str:
    return hex(int(value))[2:].rjust(64, "0")


def _addr(value: str) -> str:
    return value.lower().replace("0x", "").rjust(64, "0")


def listed_asset(token: dict) -> dict | None:
    for item in LISTED.values():
        if item["address"].lower() == token["address"].lower():
            return item
        if item["symbol"].upper() == (token.get("symbol") or "").upper():
            return item
    return None


def _held_raw(token_addr: str, balances) -> int:
    for item in balances or []:
        if (item.get("address") or "").lower() == token_addr.lower():
            return int(item.get("raw") or 0)
    return 0


def build_aave_supply(*, token: dict, amount: str | None, fraction, wallet, balances) -> dict:
    if not wallet:
        return {"error": "Connect a Base wallet to supply on Aave."}
    asset = listed_asset(token)
    if not asset:
        return {
            "error": (
                f"{token.get('symbol')} is not a listed Aave V3 Base reserve. "
                "On Base, supply USDC or WETH — not tokenized stocks."
            )
        }
    wei = int(to_wei(amount, asset["decimals"])) if amount else 0
    if wei <= 0 and fraction:
        wei = int(_held_raw(asset["address"], balances) * float(fraction))
    if wei <= 0:
        wei = _held_raw(asset["address"], balances)
    if wei <= 0:
        return {"error": f"No {asset['symbol']} to supply."}
    data = (
        SUPPLY
        + _addr(asset["address"])
        + _pad_uint(wei)
        + _addr(wallet)
        + _pad_uint(0)
    )
    human = from_wei(wei, asset["decimals"])
    return {
        "type": "tx",
        "kind": "aave_supply",
        "protocol": "aave",
        "mock": False,
        "summary": f"Supply {human} {asset['symbol']} to Aave V3 on Base",
        "spender": POOL,
        "approvals": [{"symbol": asset["symbol"], "address": asset["address"], "amountWei": str(wei)}],
        "from": {
            "symbol": asset["symbol"],
            "address": asset["address"],
            "decimals": asset["decimals"],
            "amount": human,
            "amountWei": str(wei),
        },
        "to": {
            "symbol": f"a{asset['symbol']}",
            "address": asset["a_token"],
            "decimals": asset["decimals"],
            "amount": human,
            "amountWei": str(wei),
        },
        "tx": {"to": POOL, "data": data, "value": "0"},
        "raw": {"pool": POOL, "aToken": asset["a_token"]},
    }


def build_aave_withdraw(*, token: dict, amount: str | None, fraction, wallet, balances) -> dict:
    if not wallet:
        return {"error": "Connect a Base wallet to withdraw from Aave."}
    asset = listed_asset(token)
    if not asset:
        return {"error": f"{token.get('symbol')} is not listed on Aave V3 Base."}
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
    return {
        "type": "tx",
        "kind": "aave_withdraw",
        "protocol": "aave",
        "mock": False,
        "summary": f"Withdraw {label} {asset['symbol']} from Aave V3 on Base",
        "spender": POOL,
        "approvals": [],
        "from": {
            "symbol": f"a{asset['symbol']}",
            "address": asset["a_token"],
            "decimals": asset["decimals"],
            "amount": label,
            "amountWei": str(wei if wei != 2**256 - 1 else a_bal),
        },
        "to": {
            "symbol": asset["symbol"],
            "address": asset["address"],
            "decimals": asset["decimals"],
            "amount": label,
            "amountWei": str(wei if wei != 2**256 - 1 else a_bal),
        },
        "tx": {"to": POOL, "data": data, "value": "0"},
        "raw": {"pool": POOL, "aToken": asset["a_token"]},
    }