"""Swap quotes on Base: Aerodrome first, then 0x, then 1inch, then MOCK."""

from __future__ import annotations

import os
from decimal import Decimal, ROUND_DOWN

import httpx
from dotenv import load_dotenv

from services.aerodrome import quote_aerodrome

load_dotenv()

BASE_CHAIN_ID = 8453
ZEROX_QUOTE_URL = "https://api.0x.org/swap/allowance-holder/quote"
ZEROX_PRICE_URL = "https://api.0x.org/swap/allowance-holder/price"
ONEINCH_SWAP_URL = f"https://api.1inch.dev/swap/v6.0/{BASE_CHAIN_ID}/swap"

ONEINCH_SWAP_URLS = [
    f"https://api.1inch.com/swap/v6.1/{BASE_CHAIN_ID}/swap",
    f"https://api.1inch.dev/swap/v6.1/{BASE_CHAIN_ID}/swap",
    f"https://api.1inch.dev/swap/v6.0/{BASE_CHAIN_ID}/swap",
]


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip().strip('"').strip("'")


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
    return {
        "0x-version": "v2",
        "0x-api-key": _env("ZEROX_API_KEY"),
        "accept": "application/json",
    }


def _parse_0x(data: dict, route: str) -> dict | None:
    if not isinstance(data, dict):
        return None
    tx = data.get("transaction") or {}
    issues = data.get("issues") or {}
    allowance = issues.get("allowance") or {}
    spender = (
        allowance.get("spender")
        or data.get("allowanceTarget")
        or tx.get("to")
        or "0x0000000000001fF3684f28c67538d4D072C22734"
    )
    buy_amount = str(data.get("buyAmount") or "0")
    if buy_amount == "0" and not tx.get("data"):
        return None
    impact = data.get("estimatedPriceImpact")
    try:
        price_impact_bps = int(Decimal(str(impact)) * 100) if impact is not None else 0
    except Exception:
        price_impact_bps = 0
    return {
        "route": route,
        "mock": False,
        "buyAmount": buy_amount,
        "priceImpactBps": price_impact_bps,
        "spender": spender,
        "tx": {
            "to": tx.get("to") or spender,
            "data": tx.get("data") or "0x",
            "value": str(tx.get("value") or "0"),
        },
        "raw": data,
    }


def _0x_get(url: str, params: dict) -> tuple[int, dict | str]:
    try:
        response = httpx.get(url, params=params, headers=_headers_0x(), timeout=25.0)
        try:
            body = response.json()
        except Exception:
            body = response.text
        return response.status_code, body
    except Exception as exc:
        return 0, str(exc)


def fetch_0x_quote(
    *,
    sell_token: str,
    buy_token: str,
    sell_amount_wei: str,
    taker: str | None,
) -> dict | None:
    if not _env("ZEROX_API_KEY"):
        print("[0x] ZEROX_API_KEY missing")
        return None

    base_params = {
        "chainId": str(BASE_CHAIN_ID),
        "sellToken": sell_token,
        "buyToken": buy_token,
        "sellAmount": sell_amount_wei,
        "slippageBps": "100",
    }
    attempts = []
    if taker:
        attempts.append((ZEROX_QUOTE_URL, {**base_params, "taker": taker}))
    attempts.append((ZEROX_QUOTE_URL, dict(base_params)))
    if taker:
        attempts.append((ZEROX_PRICE_URL, {**base_params, "taker": taker}))
    attempts.append((ZEROX_PRICE_URL, dict(base_params)))

    last_error = None
    for url, params in attempts:
        status, body = _0x_get(url, params)
        print(f"[0x] {status} {url} params={params}")
        print(f"[0x] body={body}")
        if status >= 400 or status == 0:
            last_error = body
            continue
        if isinstance(body, dict):
            parsed = _parse_0x(body, "0x")
            if parsed:
                return parsed
            last_error = body
        else:
            last_error = body
    if last_error is not None:
        print("[0x] giving up:", last_error)
    return None


def mock_quote(
    *,
    sell_token: dict,
    buy_token: dict,
    sell_amount: str,
    sell_amount_wei: str,
    reason: str = "",
) -> dict:
    sell = Decimal(str(sell_amount) or "0")
    if buy_token.get("kind") == "stock" and sell_token.get("symbol") == "USDC":
        buy_human = (sell / Decimal("330")).quantize(Decimal("0.0001"), rounding=ROUND_DOWN)
    elif sell_token.get("kind") == "stock" and buy_token.get("symbol") == "USDC":
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
            "reason": reason or "No live Aerodrome/0x/1inch quote",
            "sellAmount": sell_amount_wei,
            "buyAmount": buy_wei,
        },
    }


def fetch_1inch_quote(
    *,
    sell_token: str,
    buy_token: str,
    sell_amount_wei: str,
    taker: str | None,
) -> dict | None:
    key = _env("ONEINCH_API_KEY")
    if not key or not taker:
        if key and not taker:
            print("[1inch] key present but no taker wallet")
        return None
    params = {
        "src": sell_token,
        "dst": buy_token,
        "amount": sell_amount_wei,
        "from": taker,
        "slippage": 1,
        "disableEstimate": "true",
    }
    headers = {"Authorization": f"Bearer {key}", "accept": "application/json"}
    for url in ONEINCH_SWAP_URLS:
        try:
            print(f"[1inch] GET {url}")
            response = httpx.get(url, params=params, headers=headers, timeout=25.0)
            print(f"[1inch] {response.status_code} {response.text[:400]}")
            if response.status_code >= 400:
                continue
            data = response.json()
            tx = data.get("tx") or {}
            if not tx.get("to") or not tx.get("data"):
                continue
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
        except Exception as exc:
            print("[1inch]", url, exc)
    return None


def get_quote(*, from_token: dict, to_token: dict, amount: str, wallet: str | None) -> dict:
    sell_amount_wei = to_wei(amount, from_token["decimals"])
    live = None
    if _env("ONEINCH_API_KEY"):
        live = fetch_1inch_quote(
            sell_token=from_token["address"],
            buy_token=to_token["address"],
            sell_amount_wei=sell_amount_wei,
            taker=wallet,
        )
    if live is None:
        live = quote_aerodrome(
            from_token=from_token,
            to_token=to_token,
            amount_wei=sell_amount_wei,
            wallet=wallet,
        )
    if live is None:
        live = fetch_0x_quote(
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
            reason="No 1inch/Aerodrome/0x quote",
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