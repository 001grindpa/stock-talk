"""Build an unsigned B20 stock gift (ERC-20 transfer). Wallet signs on the client."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from agent.registry import resolve_ticker
from services.quotes import to_wei


ADDR_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
TRANSFER_SELECTOR = "a9059cbb"
TRANSFER_WITH_MEMO_SELECTOR = "95777d59"  # fallback unused; real selector below
# B20: transferWithMemo(address,uint256,bytes32)
TRANSFER_WITH_MEMO_SELECTOR = "0b0234ea"
MAX_MEMO = 32


def _norm_addr(value: str | None) -> str | None:
    text = (value or "").strip()
    if not ADDR_RE.match(text):
        return None
    return text.lower()


def _pad_addr(addr: str) -> str:
    return addr.lower().replace("0x", "").rjust(64, "0")


def _pad_uint(amount_wei: int) -> str:
    return format(amount_wei, "x").rjust(64, "0")


def _pad_memo(memo: str) -> str:
    raw = (memo or "").strip().encode("utf-8")[:MAX_MEMO]
    return raw.hex().ljust(64, "0")


def _encode_transfer(to_addr: str, amount_wei: int) -> str:
    return "0x" + TRANSFER_SELECTOR + _pad_addr(to_addr) + _pad_uint(amount_wei)


def _encode_transfer_with_memo(to_addr: str, amount_wei: int, memo: str) -> str:
    return (
        "0x"
        + TRANSFER_WITH_MEMO_SELECTOR
        + _pad_addr(to_addr)
        + _pad_uint(amount_wei)
        + _pad_memo(memo)
    )


def build_gift(
    db,
    *,
    wallet: str | None,
    to: str | None,
    symbol: str | None,
    amount: str | None,
    memo: str = "",
) -> dict:
    sender = _norm_addr(wallet)
    if not sender:
        return {"error": "Connect a Base wallet to gift a stock."}

    recipient = _norm_addr(to)
    if not recipient:
        return {"error": "Recipient must be a 0x address. Resolve Basename in the card first."}
    if recipient == sender:
        return {"error": "Sender and recipient are the same address."}

    token = resolve_ticker(db, symbol)
    if not token or token.get("kind") != "stock":
        return {"error": "Pick an official Coinbase Tokenized Stock."}

    try:
        qty = Decimal(str(amount or "").strip())
    except (InvalidOperation, TypeError):
        return {"error": "Enter a valid amount."}
    if qty <= 0:
        return {"error": "Amount must be greater than zero."}

    amount_wei = int(to_wei(str(qty), token["decimals"]))
    if amount_wei < 1:
        return {"error": "Amount is too small to transfer."}

    note = (memo or "").strip()
    if len(note.encode("utf-8")) > MAX_MEMO:
        return {"error": f"Memo must be {MAX_MEMO} bytes or less."}

    if note:
        data = _encode_transfer_with_memo(recipient, amount_wei, note)
    else:
        data = _encode_transfer(recipient, amount_wei)

    human = format(qty, "f")
    return {
        "type": "gift",
        "kind": "gift_transfer",
        "from": {
            "symbol": token["symbol"],
            "name": token.get("name"),
            "address": token["address"],
            "decimals": token["decimals"],
            "amount": human,
            "amountWei": str(amount_wei),
        },
        "to": {
            "address": recipient,
            "symbol": token["symbol"],
            "amount": human,
        },
        "tx": {
            "to": token["address"],
            "data": data,
            "value": "0",
        },
        "spender": None,
        "mock": False,
        "memo": note,
        "summary": f"Send {human} {token['symbol']} to {recipient[:6]}…{recipient[-4:]}",
    }