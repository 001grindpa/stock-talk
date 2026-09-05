"""Swap quotes on Base: 0x first, 1inch fallback, MOCK if keys are missing.

The backend never signs. Quotes return unsigned calldata for the browser wallet.
"""

from __future__ import annotations

import os
from decimal import Decimal, ROUND_DOWN

import httpx

BASE_CHAIN_ID = 8453
ZEROX_QUOTE_URL = "https://api.0x.org/swap/allowance-holder/quote"
ONEINCH_SWAP_URL = f"https://api.1inch.dev/swap/v6.0/{BASE_CHAIN_ID}/swap"


def to_wei(amount: str | float | Decimal, decimals: int) -> str:
    quant = Decimal(10) ** decimals
    value = (Decimal(str(amount)) * quant).quantize(Decimal("1"), rounding=ROUND_DOWN)
    if value < 0:
        value = Decimal(0)
    return str(int(value))


def from_wei(amount_wei: str | int, decimals: int, places: int = 6) -> str:
    quant = Decimal(10) ** decimals
    value = Decimal(str(amount_wei)) / quant
    return format(value.quantize(Decimal(10) ** -places, rounding=ROUND_DOWN), "f")


def _headers_0x() -> dict[str, str]:
    key = (os.getenv("ZEROX_API_KEY") or "").strip()
    headers = {"0x-version": "v2", "accept": "application/json"}
    if key:
        headers["0x-api-key"] = key
        headers["Authorization"] = f"Bearer {key}"
    return headers


def fetch_0x_quote(
    *,
    sell_token: str,
    buy_token: str,
    sell_amount_wei: str,
    taker: str | None,
) -> dict | None:
    key = (os.getenv("ZEROX_API_KEY") or "").strip()
    if not key:
        return None
    params = {
        "chainId": BASE_CHAIN_ID,
        "sellToken": sell_token,
        "buyToken": buy_token,
        "sellAmount": sell_amount_wei,
        "slippageBps": 100,
    }
    if taker:
        params["taker"] = taker
    try:
        response = httpx.get(
            ZEROX_QUOTE_URL,
            params=params,
            headers=_headers_0x(),
            timeout=25.0,
        )
        if response.status_code >= 400:
            return None
        data = response.json()
        tx = data.get("transaction") or {}
        issues = data.get("issues") or {}
        allowance = issues.get("allowance") or {}
        spender = allowance.get("spender") or data.get("allowanceTarget") or tx.get("to")
        buy_amount = str(data.get("buyAmount") or "0")
        impact = data.get("estimatedPriceImpact")
        try:
            price_impact_bps = int(Decimal(str(impact)) * 100) if impact is not None else 0
        except Exception:
            price_impact_bps = 0
        return {
            "route": "0x",
            "mock": False,
            "buyAmount": buy_amount,
            "priceImpactBps": price_impact_bps,
            "spender": spender,
            "tx": {
                "to": tx.get("to"),
                "data": tx.get("data"),
                "value": str(tx.get("value") or "0"),
            },
            "raw": data,
        }
    except Exception:
        return None


def fetch_1inch_quote(
    *,
    sell_token: str,
    buy_token: str,
    sell_amount_wei: str,
    taker: str | None,
) -> dict | None:
    key = (os.getenv("ONEINCH_API_KEY") or "").strip()
    if not key or not taker:
        return None
    params = {
        "src": sell_token,
        "dst": buy_token,
        "amount": sell_amount_wei,
        "from": taker,
        "slippage": 1,
        "disableEstimate": "true",
    }
    try:
        response = httpx.get(
            ONEINCH_SWAP_URL,
            params=params,
            headers={"Authorization": f"Bearer {key}", "accept": "application/json"},
            timeout=25.0,
        )
        if response.status_code >= 400:
            return None
        data = response.json()
        tx = data.get("tx") or {}
        return {
            "route": "1inch",
            "mock": False,
            "buyAmount": str(data.get("dstAmount") or "0"),
            "priceImpactBps": 0,
            "spender": tx.get("to"),
            "tx": {
                "to": tx.get("to"),
                "data": tx.get("data"),
                "value": str(tx.get("value") or "0"),
            },
            "raw": data,
        }
    except Exception:
        return None


def mock_quote(*, sell_token: dict, buy_token: dict, sell_amount: str, sell_amount_wei: str) -> dict:
    """Indicative quote when aggregator keys are missing. Confirm stays disabled."""
    sell = Decimal(str(sell_amount) or "0")
    if buy_token["kind"] == "stock" and sell_token["symbol"] == "USDC":
        # Rough demo fill: ~$330 / share for large-cap names.
        buy_human = (sell / Decimal("330")).quantize(Decimal("0.0001"), rounding=ROUND_DOWN)
    elif sell_token["kind"] == "stock" and buy_token["symbol"] == "USDC":
        buy_human = (sell * Decimal("330")).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    else:
        buy_human = sell
    buy_wei = to_wei(buy_human, buy_token["decimals"])
    return {
        "route": "MOCK",
        "mock": True,
        "buyAmount": buy_wei,
        "priceImpactBps": 12,
        "spender": "0x0000000000001fF3684f28c67538d4D072C22734",
        "tx": {
            "to": "0x0000000000001fF3684f28c67538d4D072C22734",
            "data": "0x",
            "value": "0",
        },
        "raw": {
            "mock": True,
            "note": "Set ZEROX_API_KEY or ONEINCH_API_KEY for a live Base quote.",
            "sellAmount": sell_amount_wei,
            "buyAmount": buy_wei,
        },
    }


def get_quote(
    *,
    from_token: dict,
    to_token: dict,
    amount: str,
    wallet: str | None,
) -> dict:
    sell_amount_wei = to_wei(amount, from_token["decimals"])
    live = fetch_0x_quote(
        sell_token=from_token["address"],
        buy_token=to_token["address"],
        sell_amount_wei=sell_amount_wei,
        taker=wallet,
    )
    if live is None:
        live = fetch_1inch_quote(
            sell_token=from_token["address"],
            buy_token=to_token["address"],
            sell_amount_wei=sell_amount_wei,
            taker=wallet,
        )
    if live is None:
        live = mock_quote(
            sell_token=from_token,
            buy_token=to_token,
            sell_amount=amount,
            sell_amount_wei=sell_amount_wei,
        )
    places = 4 if to_token["decimals"] >= 18 else 6
    buy_human = from_wei(live["buyAmount"], to_token["decimals"], places=places)
    return {
        **live,
        "from": {
            "symbol": from_token["symbol"],
            "address": from_token["address"],
            "decimals": from_token["decimals"],
            "amount": str(amount),
            "amountWei": sell_amount_wei,
        },
        "to": {
            "symbol": to_token["symbol"],
            "address": to_token["address"],
            "decimals": to_token["decimals"],
            "amount": buy_human,
            "amountWei": str(live["buyAmount"]),
        },
    }
