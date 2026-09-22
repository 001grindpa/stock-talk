"""Named baskets → N unsigned swap quotes. Not a vault."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json

from agent.registry import resolve_ticker
from services.quotes import get_quote


DEFAULT_QUOTE = "USDC"
MAX_LEGS = 8
MIN_USD_PER_LEG = Decimal("0.5")
MIN_STOCK_UNITS = Decimal("0.00000001")
MIN_ETH = Decimal("0.00005")
MIN_BTC = Decimal("0.00001")
PROBE_STOCK = "0.001"
PROBE_ETH = "0.00005"
PROBE_BTC = "0.00001"


def parse_symbols(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.replace(",", " ").split() if p.strip()]
    elif isinstance(raw, (list, tuple)):
        parts = [str(p).strip() for p in raw if str(p).strip()]
    else:
        return []
    out, seen = [], set()
    for p in parts:
        key = p.upper()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out[:MAX_LEGS]


def _dec(value) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _held(balances, symbol: str) -> Decimal:
    want = (symbol or "").upper()
    for row in balances or []:
        if not isinstance(row, dict):
            continue
        if (row.get("symbol") or "").upper() != want:
            continue
        formatted = _dec(row.get("formatted"))
        if formatted is not None:
            return formatted
        raw = row.get("raw")
        decimals = int(row.get("decimals") or 0)
        if raw not in (None, "") and decimals >= 0:
            try:
                return Decimal(str(int(raw))) / (Decimal(10) ** decimals)
            except (InvalidOperation, ValueError, TypeError):
                return Decimal("0")
    return Decimal("0")


def _unit_floor(token: dict) -> Decimal:
    symbol = (token.get("symbol") or "").upper()
    kind = token.get("kind") or ""
    if symbol in {"ETH", "WETH"} or kind in {"gas", "native"}:
        return MIN_ETH
    if symbol in {"WBTC", "CBBTC"} or kind == "btc":
        return MIN_BTC
    if symbol in {"USDC", "USDT"} or kind == "stable":
        return MIN_USD_PER_LEG
    return MIN_STOCK_UNITS


def _probe_amount(token: dict) -> str:
    symbol = (token.get("symbol") or "").upper()
    kind = token.get("kind") or ""
    if symbol in {"ETH", "WETH"} or kind in {"gas", "native"}:
        return PROBE_ETH
    if symbol in {"WBTC", "CBBTC"} or kind == "btc":
        return PROBE_BTC
    if symbol in {"USDC", "USDT"} or kind == "stable":
        return str(MIN_USD_PER_LEG)
    return PROBE_STOCK


def _usd_value(db, token: dict, amount: Decimal, wallet) -> Decimal | None:
    if token.get("symbol") in {"USDC", "USDT"} or token.get("kind") == "stable":
        return amount
    usdc = resolve_ticker(db, "USDC")
    if not usdc:
        return None
    probe = _probe_amount(token)
    sample = get_quote(from_token=token, to_token=usdc, amount=probe, wallet=wallet)
    if sample.get("error"):
        return None
    usd_out = _dec((sample.get("to") or {}).get("amount"))
    probe_amt = _dec(probe)
    if not usd_out or not probe_amt or probe_amt <= 0:
        return None
    return amount * (usd_out / probe_amt)


def _failed(sell, buy, error: str) -> dict:
    sell_sym = (sell or {}).get("symbol") or "?"
    buy_sym = (buy or {}).get("symbol") or "?"
    return {
        "symbol": f"{sell_sym}→{buy_sym}",
        "name": (buy or {}).get("name"),
        "ok": False,
        "error": error,
    }


def _clean_quote_error(err: str, sell, buy) -> str:
    text = (err or "").strip()
    low = text.lower()
    if "amount is zero" in low or "how much" in low:
        return (
            f"Could not size {sell.get('symbol')}→{buy.get('symbol')} "
            "from the current balance."
        )
    return text or f"No live route for {sell.get('symbol')}→{buy.get('symbol')}."


def quote_basket(
    *,
    db,
    legs_json=None,
    symbols=None,
    amount_usd: float | None = None,
    amount_each: str | None = None,
    from_symbol: str = DEFAULT_QUOTE,
    wallet: str | None = None,
    balances=None,
) -> dict:
    planned = _normalize_legs(
        db,
        legs_json=legs_json,
        symbols=symbols,
        amount_usd=amount_usd,
        amount_each=amount_each,
        from_symbol=from_symbol,
    )
    if planned.get("error"):
        return planned

    legs = []
    ok = 0
    for spec in planned["specs"]:
        sell = spec.get("sell") or {}
        buy = spec.get("buy") or {}
        if spec.get("error"):
            legs.append(_failed(sell, buy, spec.get("message") or "Could not build that leg."))
            continue
        if (sell.get("address") or "").lower() == (buy.get("address") or "").lower():
            legs.append(_failed(sell, buy, "Sell token and buy token are the same."))
            continue

        sized = _size_leg(spec, balances=balances, db=db, wallet=wallet)
        if sized.get("error"):
            legs.append(_failed(sell, buy, sized["error"]))
            continue
        amount = sized["amount"]

        q = get_quote(
            from_token=sell,
            to_token=buy,
            amount=str(amount),
            wallet=wallet,
        )
        fallback = None
        if q.get("error") and sell.get("symbol") == "USDT":
            usdc = resolve_ticker(db, "USDC")
            if usdc and usdc["address"].lower() != buy["address"].lower():
                q2 = get_quote(
                    from_token=usdc,
                    to_token=buy,
                    amount=str(amount),
                    wallet=wallet,
                )
                if not q2.get("error"):
                    q = q2
                    fallback = "USDT route missed; using USDC"

        if q.get("error"):
            legs.append(_failed(sell, buy, _clean_quote_error(q["error"], sell, buy)))
            continue

        ok += 1
        legs.append({
            "symbol": buy["symbol"],
            "name": buy.get("name"),
            "ok": True,
            "type": "quote",
            "from": q["from"],
            "to": q["to"],
            "priceImpactBps": q.get("priceImpactBps") or 0,
            "route": q.get("route") or "aggregator",
            "tx": q.get("tx") or {"to": None, "data": "0x", "value": "0"},
            "spender": q.get("spender"),
            "mock": bool(q.get("mock")),
            "note": fallback,
        })

    if not legs:
        return {"error": "Name at least two swaps. Example: $2 USDC to AMZN and $2 USDT to SNDK."}

    fallbacks = sum(1 for leg in legs if leg.get("ok") and leg.get("note"))
    summary = f"Basket: {ok}/{len(legs)} quotes ready."
    if fallbacks:
        summary += f" {fallbacks} leg(s) use USDC because USDT had no route."
    summary += " Confirm each swap in your wallet, one after another."

    return {
        "type": "basket",
        "legs": legs,
        "ok_legs": ok,
        "total_legs": len(legs),
        "summary": summary,
    }


def _size_leg(spec: dict, *, balances, db, wallet) -> dict:
    sell = spec["sell"]
    buy = spec["buy"]
    amount = str(spec.get("amount") or "").strip()
    fraction = float(spec.get("fraction") or 0)
    if fraction > 0:
        bal = _held(balances, sell["symbol"])
        if bal <= 0:
            return {"error": f"You have no {sell['symbol']} to swap."}
        amount = format(bal * Decimal(str(fraction)), "f")

    sized = _dec(amount)
    if sized is None or sized <= 0:
        return {"error": f"Need a size for {sell['symbol']} → {buy['symbol']}."}
    if sized < _unit_floor(sell):
        return {
            "error": (
                f"{sell['symbol']} amount {format(sized, 'f')} is below "
                "the minimum swap size."
            )
        }

    usd = _usd_value(db, sell, sized, wallet)
    if usd is None:
        return {
            "error": (
                f"{sell['symbol']} amount {format(sized, 'f')} could not be priced in USD, "
                "so it was not quoted."
            )
        }
    if usd < MIN_USD_PER_LEG:
        return {
            "error": (
                f"{sell['symbol']} amount is {format(sized, 'f')} "
                f"(~${format(usd, '0.4f')}), below the ${MIN_USD_PER_LEG} minimum."
            )
        }
    return {"amount": format(sized, "f")}


def _normalize_legs(db, *, legs_json, symbols, amount_usd, amount_each, from_symbol):
    specs = []
    raw_legs = None
    if isinstance(legs_json, list):
        raw_legs = legs_json
    elif isinstance(legs_json, str) and legs_json.strip():
        try:
            parsed = json.loads(legs_json)
        except json.JSONDecodeError:
            return {"error": "Basket legs must be valid JSON."}
        if not isinstance(parsed, list):
            return {"error": "Basket legs must be a JSON list."}
        raw_legs = parsed

    if raw_legs is not None:
        if len(raw_legs) < 2:
            return {"error": "A basket needs two or more swaps."}
        for item in raw_legs[:MAX_LEGS]:
            if not isinstance(item, dict):
                continue
            specs.append(_spec_from_item(db, item))
        return {"specs": specs}

    tickers = parse_symbols(symbols)
    if len(tickers) < 2:
        return {"error": "A basket needs two or more tokens. Use a normal swap for one ticker."}
    sell = resolve_ticker(db, from_symbol or DEFAULT_QUOTE)
    if not sell:
        return {"error": "I can only fund a basket from USDC, USDT, ETH, WETH, cbBTC, or WBTC."}
    usd = float(amount_usd or 0)
    each = (amount_each or "").strip()
    if usd > 0 and sell["symbol"] in {"USDC", "USDT"}:
        if Decimal(str(usd)) < MIN_USD_PER_LEG:
            return {"error": f"Each leg must be at least ${MIN_USD_PER_LEG}."}
        amount = format(Decimal(str(usd)), "f")
    elif each:
        amount = each
    else:
        return {"error": "How much per name? Example: buy $20 each of AAPL MSFT GOOGL."}
    for ticker in tickers:
        buy = resolve_ticker(db, ticker)
        if not buy:
            specs.append({
                "error": True,
                "buy": {"symbol": ticker, "name": None},
                "sell": sell,
                "amount": amount,
                "message": f"{ticker} is not an official Coinbase Tokenized Stock on this app.",
            })
            continue
        specs.append({"sell": sell, "buy": buy, "amount": amount})
    return {"specs": specs}


def _spec_from_item(db, item: dict) -> dict:
    sell = resolve_ticker(db, item.get("from_symbol") or DEFAULT_QUOTE)
    buy = resolve_ticker(db, item.get("to_symbol"))
    if not sell:
        return {
            "error": True,
            "buy": {"symbol": str(item.get("to_symbol") or "?"), "name": None},
            "sell": {"symbol": str(item.get("from_symbol") or "?"), "address": ""},
            "amount": "0",
            "message": f"{item.get('from_symbol')} is not an allowlisted sell token.",
        }
    if not buy:
        return {
            "error": True,
            "buy": {"symbol": str(item.get("to_symbol") or "?"), "name": None},
            "sell": sell,
            "amount": "0",
            "message": f"{item.get('to_symbol')} is not an official Coinbase Tokenized Stock on this app.",
        }

    amount = str(item.get("amount") or "").strip()
    amount_usd = float(item.get("amount_usd") or 0)
    fraction = float(item.get("fraction") or 0)
    if amount_usd > 0 and sell["symbol"] in {"USDC", "USDT"}:
        amount = format(Decimal(str(amount_usd)), "f")
        fraction = 0
    return {
        "sell": sell,
        "buy": buy,
        "amount": amount,
        "fraction": fraction,
    }