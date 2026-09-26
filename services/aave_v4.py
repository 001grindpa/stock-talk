"""Aave V4 Equities Hub on Base.

Official addresses: aave-address-book AaveV4Base
https://aave-dao.github.io/aave-address-book/api/v1/modules/AaveV4Base.json

Collateral only: AAPLc AMZNc GOOGLc METAc MSFTc NVDAc TSLAc
Borrow only: USDC
EOA calls Mag-7 Spoke directly (caller == onBehalfOf).
"""

from __future__ import annotations

from services.quotes import to_wei
from services.rpc import _eth_call, token_balance

CHAIN_ID = 8453

HUB = "0xa4d5947Eb727A052bae69C593FfC84247EC9864E"
SPOKE = "0x17905Db0e4A3514467539956c084180616AE7B8D"
CONFIG_PM = "0xe90F830bEe4b190B4910e146908437075b0BDaaF"

# Spoke self-calls: (uint256 reserveId, uint256 amount, address onBehalfOf)
SPOKE_SUPPLY = "0x852a56a5"
SPOKE_BORROW = "0xd6bda0c0"
SPOKE_REPAY = "0xb1e8f8ef"
SPOKE_WITHDRAW = "0x0ad58d2f"
SPOKE_ACCOUNT = "0xbf92857c"  # getUserAccountData(address)
SPOKE_USER_POS = "0x869da9db"  # getUserPosition(uint256,address)
SPOKE_SET_COL = "0x9e35c533"  # setUsingAsCollateral(uint256,bool,address)

HUB_GET_ASSET_ID = "0xd6abe642"
SPOKE_GET_RESERVE_ID = "0x42aef1f1"
CONFIG_COLLATERAL = "0xf0e302b1"

WAD = 10 ** 18
RAY = 10 ** 27
USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

COLLATERAL = {
    "AAPL": {"symbol": "AAPLc", "address": "0xb200000000000000000000C2e324d24d7eEcd1fb", "decimals": 8, "cf": 0.78, "borrowable": False},
    "AMZN": {"symbol": "AMZNc", "address": "0xb200000000000000000000d9192b6B456483C2E8", "decimals": 8, "cf": 0.73, "borrowable": False},
    "GOOGL": {"symbol": "GOOGLc", "address": "0xb2000000000000000000002D0BA3164cc74f58B7", "decimals": 8, "cf": 0.76, "borrowable": False},
    "META": {"symbol": "METAc", "address": "0xb2000000000000000000008bC8786B856E61707C", "decimals": 8, "cf": 0.65, "borrowable": False},
    "MSFT": {"symbol": "MSFTc", "address": "0xB200000000000000000000Ab99cFa739E253872B", "decimals": 8, "cf": None, "borrowable": False},
    "NVDA": {"symbol": "NVDAc", "address": "0xb20000000000000000000078ee7ce2fE4908108C", "decimals": 8, "cf": None, "borrowable": False},
    "TSLA": {"symbol": "TSLAc", "address": "0xb2000000000000000000001e800a7f5189430cD0", "decimals": 8, "cf": None, "borrowable": False},
}

BORROW = {
    "USDC": {"symbol": "USDC", "address": USDC, "decimals": 6, "borrowable": True},
}

_NOT_LISTED = (
    "Aave V4 Equities Hub lists AAPLc, AMZNc, GOOGLc, METAc, MSFTc, NVDAc, TSLAc "
    "as collateral only, and USDC as the only borrowable asset. "
    "SNDK, COIN, CRCL, MSTR, SPCX, INTC are not on this hub."
)


def _addr(value: str) -> str:
    return value.lower().replace("0x", "").rjust(64, "0")


def _u256(value: int) -> str:
    return format(int(value), "x").rjust(64, "0")


def _norm_sym(raw: str | None) -> str:
    s = (raw or "").upper().replace(" ", "")
    if s.endswith("C") and s[:-1] in COLLATERAL:
        s = s[:-1]
    return {
        "AAPL": "AAPL", "APPLE": "AAPL",
        "AMZN": "AMZN", "AMAZON": "AMZN",
        "GOOGL": "GOOGL", "GOOG": "GOOGL", "GOOGLE": "GOOGL", "ALPHABET": "GOOGL",
        "META": "META", "FB": "META",
        "MSFT": "MSFT", "MICROSOFT": "MSFT",
        "NVDA": "NVDA", "NVIDIA": "NVDA",
        "TSLA": "TSLA", "TESLA": "TSLA",
        "USDC": "USDC", "USD": "USDC",
    }.get(s, s)


def listed_collateral(token: dict | None) -> dict | None:
    if not token:
        return None
    addr = (token.get("address") or "").lower()
    if addr:
        for item in COLLATERAL.values():
            if item["address"].lower() == addr:
                return item
    return COLLATERAL.get(_norm_sym(token.get("symbol")))


def listed_borrow(token: dict | None) -> dict | None:
    if not token:
        return None
    addr = (token.get("address") or "").lower()
    if addr == USDC.lower() or _norm_sym(token.get("symbol")) == "USDC":
        return BORROW["USDC"]
    return None


def _need_selectors() -> str | None:
    missing = [n for n, v in [
        ("SPOKE_SUPPLY", SPOKE_SUPPLY),
        ("SPOKE_BORROW", SPOKE_BORROW),
        ("SPOKE_REPAY", SPOKE_REPAY),
        ("SPOKE_WITHDRAW", SPOKE_WITHDRAW),
        ("HUB_GET_ASSET_ID", HUB_GET_ASSET_ID),
        ("SPOKE_GET_RESERVE_ID", SPOKE_GET_RESERVE_ID),
    ] if not v]
    if missing:
        return "Fill Aave V4 selectors: " + ", ".join(missing)
    return None


def reserve_id(token_addr: str) -> int | None:
    if _need_selectors() or not token_addr:
        return None
    raw = _eth_call(HUB, HUB_GET_ASSET_ID + _addr(token_addr))
    if not raw or raw == "0x" or len(raw) < 66:
        return None
    asset_id = int(raw[-64:], 16)
    raw2 = _eth_call(SPOKE, SPOKE_GET_RESERVE_ID + _addr(HUB) + _u256(asset_id))
    if not raw2 or raw2 == "0x" or len(raw2) < 66:
        return None
    return int(raw2[-64:], 16)


def _amount_from_balances(asset: dict, amount, fraction, balances, wallet=None) -> str | None:
    amt = (amount or "").strip()
    if amt:
        return amt
    frac = float(fraction or 0)
    if frac <= 0:
        return None
    want = asset["address"].lower()
    held = 0.0
    for row in balances or []:
        addr = (row.get("address") or "").lower()
        if addr == want or _norm_sym(row.get("symbol")) == _norm_sym(asset["symbol"]):
            try:
                held = float(row.get("formatted") or 0)
            except (TypeError, ValueError):
                held = 0.0
            break
    if held <= 0 and wallet:
        raw = token_balance(asset["address"], wallet) or 0
        held = raw / (10 ** int(asset["decimals"]))
    if held <= 0:
        return ""
    return format(held * frac, "f")


def _card(*, kind, spender, frm, to, data, summary, approvals):
    return {
        "type": "tx",
        "kind": kind,
        "protocol": "aave_v4",
        "mock": False,
        "summary": summary,
        "spender": spender,
        "approvals": approvals,
        "from": frm,
        "to": to or {},
        "tx": {"to": spender, "data": data, "value": "0"},
        "raw": {"hub": HUB, "spoke": SPOKE},
    }


def build_v4_supply(*, token: dict, amount: str | None, fraction, wallet, balances) -> dict:
    if _need_selectors():
        return {"error": _need_selectors()}
    if not wallet:
        return {"error": "Connect a Base wallet to supply on Aave V4."}
    asset = listed_collateral(token) or listed_borrow(token)
    if not asset:
        return {"error": _NOT_LISTED}
    amt = _amount_from_balances(asset, amount, fraction, balances, wallet)
    if amt == "":
        return {"error": f"Balance too low. You have 0 {asset['symbol']} to supply."}
    if not amt:
        return {"error": f"How much {asset['symbol']} to supply?"}

    wei = int(to_wei(amt, asset["decimals"]))
    if wallet:
        on_chain = token_balance(asset["address"], wallet) or 0
        if on_chain <= 0:
            return {"error": f"Balance too low. You have 0 {asset['symbol']} to supply."}
        if wei > on_chain:
            wei = on_chain
            amt = format(wei / (10 ** asset["decimals"]), "f")

    rid = reserve_id(asset["address"])
    if rid is None:
        return {"error": f"Could not read Aave V4 reserve id for {asset['symbol']}."}
    data = SPOKE_SUPPLY + _u256(rid) + _u256(wei) + _addr(wallet)

    card = _card(
        kind="aave_v4_supply",
        spender=SPOKE,
        frm={
            "symbol": asset["symbol"],
            "address": asset["address"],
            "decimals": asset["decimals"],
            "amount": amt,
            "amountWei": str(wei),
        },
        to={"symbol": "a" + asset["symbol"], "amount": amt},
        data=data,
        summary=(
            f"Supply {amt} {asset['symbol']} to Aave V4. "
            "After this confirms, enable it as collateral before borrowing."
        ),
        approvals=[{
            "address": asset["address"],
            "amountWei": str(wei),
            "symbol": asset["symbol"],
        }],
    )
    enable = build_v4_collateral(token=asset, wallet=wallet, enabled=True)
    if not enable.get("error"):
        card["enable_collateral"] = enable
    return card


def build_v4_borrow(*, token: dict, amount: str | None, wallet) -> dict:
    if _need_selectors():
        return {"error": _need_selectors()}
    if not wallet:
        return {"error": "Connect a Base wallet to borrow on Aave V4."}
    asset = listed_borrow(token)
    if not asset:
        return {"error": "Aave V4 Equities Hub only lets you borrow USDC against listed stocks."}
    if not amount:
        return {"error": "How much USDC to borrow?"}
    wei = int(to_wei(amount, asset["decimals"]))
    rid = reserve_id(asset["address"])
    if rid is None:
        return {"error": "Could not read Aave V4 USDC reserve id."}
    data = SPOKE_BORROW + _u256(rid) + _u256(wei) + _addr(wallet)
    return _card(
        kind="aave_v4_borrow",
        spender=SPOKE,
        frm={"symbol": "collateral", "amount": ""},
        to={"symbol": "USDC", "address": USDC, "decimals": 6, "amount": amount, "amountWei": str(wei)},
        data=data,
        summary=f"Borrow {amount} USDC from Aave V4 Equities Hub against Mag-7 collateral.",
        approvals=[],
    )


def build_v4_repay(*, token: dict, amount: str | None, wallet, balances=None, fraction=None) -> dict:
    if _need_selectors():
        return {"error": _need_selectors()}
    asset = listed_borrow(token)
    if not asset:
        return {"error": "Repay USDC on the Equities Hub."}
    if not wallet:
        return {"error": "Connect a wallet to repay Aave V4."}
    amt = _amount_from_balances(asset, amount, fraction, balances) if balances is not None else (amount or "").strip()
    if not amt:
        return {"error": "Name a USDC repay size."}
    wei = int(to_wei(amt, 6))
    rid = reserve_id(USDC)
    if rid is None:
        return {"error": "Could not read Aave V4 USDC reserve id."}
    data = SPOKE_REPAY + _u256(rid) + _u256(wei) + _addr(wallet)
    return _card(
        kind="aave_v4_repay",
        spender=SPOKE,
        frm={"symbol": "USDC", "address": USDC, "decimals": 6, "amount": amt, "amountWei": str(wei)},
        to={"symbol": "debt USDC"},
        data=data,
        summary=f"Repay {amt} USDC on Aave V4 Equities Hub.",
        approvals=[{"address": USDC, "amountWei": str(wei), "symbol": "USDC"}],
    )


def build_v4_withdraw(*, token: dict, amount: str | None, wallet, balances=None, fraction=None) -> dict:
    if _need_selectors():
        return {"error": _need_selectors()}
    asset = listed_collateral(token) or listed_borrow(token)
    if not asset:
        return {"error": _NOT_LISTED}
    if not wallet:
        return {"error": "Connect a wallet to withdraw from Aave V4."}
    amt = (amount or "").strip()
    if not amt:
        return {"error": "Name a withdraw size."}
    wei = int(to_wei(amt, asset["decimals"]))
    rid = reserve_id(asset["address"])
    if rid is None:
        return {"error": f"Could not read Aave V4 reserve id for {asset['symbol']}."}
    data = SPOKE_WITHDRAW + _u256(rid) + _u256(wei) + _addr(wallet)
    return _card(
        kind="aave_v4_withdraw",
        spender=SPOKE,
        frm={"symbol": "a" + asset["symbol"], "amount": amt},
        to={"symbol": asset["symbol"], "address": asset["address"], "amount": amt, "amountWei": str(wei)},
        data=data,
        summary=f"Withdraw {amt} {asset['symbol']} from Aave V4 Equities Hub.",
        approvals=[],
    )


def _user_position(reserve: int, wallet: str) -> tuple[int, int]:
    raw = _eth_call(SPOKE, SPOKE_USER_POS + _u256(reserve) + _addr(wallet))
    if not raw or raw == "0x" or len(raw) < 2 + 64 * 4:
        return 0, 0
    words = [int(raw[2 + i * 64: 2 + (i + 1) * 64], 16) for i in range(5)]
    drawn, supplied = words[0], words[3]
    return drawn, supplied


def describe_v4_account(wallet: str) -> str:
    if not wallet:
        return "Connect a Base wallet to read Aave V4."
    lines = ["Aave V4 Equities Hub (Mag-7 Spoke)"]
    found = False
    active = 0
    raw = _eth_call(SPOKE, SPOKE_ACCOUNT + _addr(wallet))
    words = []
    if raw and len(raw) >= 2 + 64 * 7:
        words = [int(raw[2 + i * 64: 2 + (i + 1) * 64], 16) for i in range(7)]
        active = words[5]

    for item in list(COLLATERAL.values()) + [BORROW["USDC"]]:
        rid = reserve_id(item["address"])
        if rid is None:
            continue
        drawn, supplied = _user_position(rid, wallet)
        if supplied == 0 and drawn == 0:
            continue
        found = True
        dec = item["decimals"]
        if supplied:
            flag = (
                "collateral enabled on this account"
                if active
                else "supplied, not enabled as collateral"
            )
            lines.append(
                f"supplied {item['symbol']}: {supplied / (10 ** dec):.8f} "
                f"(reserve {rid}, {flag})"
            )
        if drawn:
            lines.append(f"borrowed {item['symbol']}: {drawn / (10 ** dec):.8f}")

    if words:
        hf_s = "∞" if words[2] > 10 ** 30 else f"{words[2] / WAD:.3f}"
        lines.append(
            f"account collateral units={words[3]} · debt={words[4]} · "
            f"HF {hf_s} · activeCollateral={words[5]} borrows={words[6]}"
        )
    if not found:
        lines.append("No Mag-7 supply or USDC debt on this Spoke.")
    return "\n".join(lines)


def build_v4_collateral(*, token: dict, wallet: str | None, enabled: bool = True) -> dict:
    if not wallet:
        return {"error": "Connect a Base wallet to set Aave V4 collateral."}
    asset = listed_collateral(token)
    if not asset:
        return {"error": "Aave V4 collateral toggle is only for AAPL AMZN GOOGL META MSFT NVDA TSLA."}
    rid = reserve_id(asset["address"])
    if rid is None:
        return {"error": f"Could not read Aave V4 reserve id for {asset['symbol']}."}
    data = (
        SPOKE_SET_COL
        + _u256(rid)
        + _u256(1 if enabled else 0)
        + _addr(wallet)
    )
    verb = "Enable" if enabled else "Disable"
    return _card(
        kind="aave_v4_collateral",
        spender=SPOKE,
        frm={"symbol": asset["symbol"], "address": asset["address"], "amount": ""},
        to={"symbol": "collateral flag", "amount": "on" if enabled else "off"},
        data=data,
        summary=f"{verb} {asset['symbol']} as collateral on Aave V4 Equities Hub.",
        approvals=[],
    )