"""Swap quotes on Base: 1inch if keyed, then Aerodrome, then 0x. No mock."""

from __future__ import annotations

import os
from decimal import Decimal, ROUND_DOWN

import httpx
from dotenv import load_dotenv

from services.aerodrome import quote_aerodrome
from services.slipstream import quote_slipstream

load_dotenv()

BASE_CHAIN_ID = 8453
ZEROX_QUOTE_URL = "https://api.0x.org/swap/allowance-holder/quote"
ZEROX_PRICE_URL = "https://api.0x.org/swap/allowance-holder/price"
ODOS_QUOTE_URL = "https://api.odos.xyz/sor/quote/v2"
ODOS_ASSEMBLE_URL = "https://api.odos.xyz/sor/assemble"
KYBER_ROUTE = "https://aggregator-api.kyberswap.com/base/api/v1/routes"
KYBER_BUILD = "https://aggregator-api.kyberswap.com/base/api/v1/route/build"

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


def fetch_odos_quote(
    *,
    sell_token: str,
    buy_token: str,
    sell_amount_wei: str,
    taker: str | None,
) -> dict | None:
    # print("[odos] enter", sell_token, buy_token, sell_amount_wei, taker, flush=True)
    if not taker:
        print("[odos] no taker wallet")
        return None
    quote_body = {
        "chainId": BASE_CHAIN_ID,
        "inputTokens": [{"tokenAddress": sell_token, "amount": str(sell_amount_wei)}],
        "outputTokens": [{"tokenAddress": buy_token, "proportion": 1}],
        "userAddr": taker,
        "slippageLimitPercent": 1,
        "referralCode": 0,
        "disableRFQs": True,
        "compact": True,
    }
    try:
        quoted = httpx.post(
            ODOS_QUOTE_URL,
            json=quote_body,
            headers={"Content-Type": "application/json", "accept": "application/json"},
            timeout=25.0,
        )
        print(f"[odos] quote {quoted.status_code} {quoted.text[:400]}")
        if quoted.status_code >= 400:
            return None
        data = quoted.json()
        path_id = data.get("pathId")
        out_amounts = data.get("outAmounts") or []
        print("[odos] pathId=", path_id, "outAmounts=", out_amounts, "keys=", list(data.keys()))
        if not path_id or not out_amounts:
            print("[odos] no path:", str(data)[:500])
            return None
    
        assembled = httpx.post(
            ODOS_ASSEMBLE_URL,
            json={"userAddr": taker, "pathId": path_id, "simulate": False},
            headers={"Content-Type": "application/json", "accept": "application/json"},
            timeout=25.0,
        )
        print(f"[odos] assemble {assembled.status_code} {assembled.text[:400]}")
        if assembled.status_code >= 400:
            return None
        tx_wrap = assembled.json()
        tx = tx_wrap.get("transaction") or {}
        if not tx.get("to") or not tx.get("data"):
            return None
        impact = data.get("priceImpact")
        try:
            price_impact_bps = int(Decimal(str(impact)) * 100) if impact is not None else 0
        except Exception:
            price_impact_bps = 0
        return {
            "route": "odos",
            "mock": False,
            "buyAmount": str(out_amounts[0]),
            "priceImpactBps": price_impact_bps,
            "spender": tx.get("to"),
            "tx": {
                "to": tx.get("to"),
                "data": tx.get("data"),
                "value": str(tx.get("value") or "0"),
            },
            "raw": {"quote": data, "assembled": tx_wrap},
        }
    except Exception as exc:
        print("[odos]", exc)
        return None

def fetch_kyber_quote(*, sell_token, buy_token, sell_amount_wei, taker):
    if not taker:
        print("[kyber] no taker", flush=True)
        return None
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-client-id": "stocktalk",
    }
    try:
        routed = httpx.get(
            KYBER_ROUTE,
            params={
                "tokenIn": sell_token,
                "tokenOut": buy_token,
                "amountIn": str(sell_amount_wei),
                "gasInclude": "true",
            },
            headers=headers,
            timeout=25.0,
        )
        print("[kyber] route", routed.status_code, routed.text[:400], flush=True)
        if routed.status_code >= 400:
            return None
        body = routed.json().get("data") or {}
        summary = body.get("routeSummary")
        router = body.get("routerAddress")
        if not summary or not router:
            return None
        built = httpx.post(
            KYBER_BUILD,
            json={
                "routeSummary": summary,
                "sender": taker,
                "recipient": taker,
                "slippageTolerance": 100,
            },
            headers=headers,
            timeout=25.0,
        )
        print("[kyber] build", built.status_code, built.text[:400], flush=True)
        if built.status_code >= 400:
            return None
        data = built.json().get("data") or {}
        tx_to = data.get("routerAddress") or router
        tx_data = data.get("data")
        if not tx_to or not tx_data:
            return None
        return {
            "route": "kyber",
            "mock": False,
            "buyAmount": str(summary.get("amountOut") or data.get("amountOut") or "0"),
            "priceImpactBps": 0,
            "spender": tx_to,
            "tx": {"to": tx_to, "data": tx_data, "value": str(data.get("value") or "0")},
            "raw": {"route": body, "built": data},
        }
    except Exception as exc:
        print("[kyber]", exc, flush=True)
        return None


def get_quote(*, from_token: dict, to_token: dict, amount: str, wallet: str | None) -> dict:
    # print("[quote] start", from_token["symbol"], "->", to_token["symbol"], amount, wallet, flush=True)
    try:
        sell_amt = Decimal(str(amount))
    except Exception:
        sell_amt = Decimal(0)
    if sell_amt <= 0:
        return {"error": "Amount is zero. Tell me how much to swap, e.g. swap $2 USD for AAPL."}

    sell_amount_wei = to_wei(amount, from_token["decimals"])
    if int(sell_amount_wei) < 10 ** max(int(from_token["decimals"]) - 6, 0):
        return {
            "error": (
                f"Your {from_token['symbol']} amount is dust ({amount}). "
                "Swap a real size first, e.g. swap $2 USD for AAPL."
            )
        }

    live = None
    if _env("ONEINCH_API_KEY"):
        live = fetch_1inch_quote(
            sell_token=from_token["address"],
            buy_token=to_token["address"],
            sell_amount_wei=sell_amount_wei,
            taker=wallet,
        )
    if live is None:
        live = fetch_kyber_quote(
            sell_token=from_token["address"],
            buy_token=to_token["address"],
            sell_amount_wei=sell_amount_wei,
            taker=wallet,
        )
    if live is None:
        live = fetch_odos_quote(
            sell_token=from_token["address"],
            buy_token=to_token["address"],
            sell_amount_wei=sell_amount_wei,
            taker=wallet,
        )
    if live is None:
        live = quote_slipstream(
            from_token=from_token,
            to_token=to_token,
            amount_wei=sell_amount_wei,
            wallet=wallet,
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
        return {
            "error": (
                f"No live route on Base for {from_token['symbol']} → {to_token['symbol']}. "
                "1inch, Aerodrome (including a USDC hop), and 0x all missed. "
                "That pair may have no pool yet."
            )
        }

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