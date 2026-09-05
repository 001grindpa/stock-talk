import re
from typing import Optional, TypedDict

class AgentState(TypedDict, total=False):
    messages: list
    wallet: Optional[str]
    user_message: str
    intent: dict
    from_token: Optional[dict]
    to_token: Optional[dict]
    quote: Optional[dict]
    action: dict
    assistant_text: str
    search_notes: str
    balances: list

def _first_ticker(text: str) -> str | None:
    names = {
        "apple": "AAPL",
        "aapl": "AAPL",
        "nvidia": "NVDA",
        "nvda": "NVDA",
        "tesla": "TSLA",
        "tsla": "TSLA",
        "meta": "META",
        "google": "GOOGL",
        "googl": "GOOGL",
        "alphabet": "GOOGL",
        "amazon": "AMZN",
        "amzn": "AMZN",
        "microsoft": "MSFT",
        "msft": "MSFT",
        "coinbase": "COIN",
        "coin": "COIN",
        "intel": "INTC",
        "intc": "INTC",
        "spacex": "SPCX",
        "weth": "WETH",
    }
    lower = text.lower()
    for name, tick in names.items():
        if re.search(rf"\b{name}\b", lower):
            return tick
    if re.search(r"\busdc\b|\busd\b|\$", lower) and not any(
        re.search(rf"\b{n}\b", lower) for n in names
    ):
        return "USDC"
    match = re.search(r"\b([A-Za-z]{2,6}c?)\b", text)
    if match:
        word = match.group(1)
        if word.lower() not in {
                "for", "swap", "sell", "quote", "with", "from", "into", "the", "and",
                "half", "add", "my", "lp", "on", "ok", "can", "you", "to",
                "hey", "hi", "hello", "yo", "please", "thanks", "thank", "yes", "no",
                "now", "want", "need",
            }:
            return word.upper()
    return None

def _protocol(text: str) -> str:
    lower = text.lower()
    if "uniswap" in lower:
        return "uniswap"
    if "aave" in lower:
        return "aave"
    return "aerodrome"

def _stock_or_default(text: str) -> str:
    ticker = _first_ticker(text) or "AAPL"
    if ticker == "USDC":
        return "AAPL"
    return ticker


def _parse_amount(text: str) -> tuple[str | None, float | None]:
    if re.search(r"\b\d{1,3}\s*%", text):
        dollar = re.search(r"\$\s*([\d,.]+)", text)
        usd = re.search(r"\b([\d,.]+)\s*(usd|dollars?|usdc)\b", text, re.I)
        if dollar:
            raw = dollar.group(1)
            return raw.replace(",", ""), float(raw.replace(",", ""))
        if usd:
            raw = usd.group(1)
            return raw.replace(",", ""), float(raw.replace(",", ""))
        return None, None
    
    dollar = re.search(r"\$\s*([\d,.]+)", text)
    usd = re.search(r"\b([\d,.]+)\s*(usd|dollars?|usdc)\b", text, re.I)
    generic = re.search(r"\b([\d,.]+)\b", text)
    raw = None
    amount_usd = None
    if dollar:
        raw = dollar.group(1)
        amount_usd = float(raw.replace(",", ""))
    elif usd:
        raw = usd.group(1)
        amount_usd = float(raw.replace(",", ""))
    elif generic:
        raw = generic.group(1)
    if raw is None:
        return None, None
    return raw.replace(",", ""), amount_usd


def _parse_pair(text: str) -> tuple[str | None, str | None]:
    lower = text.lower()
    if re.search(r"(?:swap|buy|quote)\s+(?:\$\s*)?[\d,.]+\s*(?:usd|usdc|dollars?)?\s+(?:for|of|into)\s+", text, re.I) or re.search(
        r"\$\s*[\d,.]+\s*(usd|usdc|dollars?)?\s+for\s+", lower
    ):
        m = re.search(r"\bfor\s+([A-Za-z]{2,12})\b", text, re.I)
        dest = m.group(1) if m else _first_ticker(re.sub(r"\$?\s*[\d,.]+\s*(usd|usdc|dollars?)?", "", text, flags=re.I))
        return "USDC", dest
    sell = re.search(
        r"(?:sell|swap)\s+([\d,.]+\s+)?([A-Za-z]{2,12})\s+(?:for|to|into)\s+([A-Za-z]{2,12})",
        text,
        re.I,
    )
    if sell:
        return sell.group(2), sell.group(3)
    into = re.search(r"\b([A-Za-z]{2,12})\s+(?:to|into|->)\s+([A-Za-z]{2,12})\b", text, re.I)
    if into:
        return into.group(1), into.group(2)
    return None, _first_ticker(text)


def _regex_intent(message: str) -> dict:
    text = (message or "").strip()
    lower = text.lower()
    protocol = _protocol(text)

    fraction = None

    if re.search(r"\b(i said|not \d+|not 100 of|percentage|percent)\b", lower):
        return {
            "action": "lp_add",
            "from_symbol": _stock_or_default(text),
            "to_symbol": "USDC",
            "amount": None,
            "amount_usd": None,
            "fraction": 1.0,
            "query": None,
            "protocol": "uniswap" if "uniswap" in lower else "aerodrome",
        }
    if re.search(r"\b(all|everything|entire|max|100\s*%|100%)\b", lower):
        fraction = 1.0
    if re.search(r"\bhalf\b", lower):
        fraction = 0.5
    pct = re.search(r"\b(\d{1,3})\s*%", lower)
    if pct:
        fraction = min(max(int(pct.group(1)) / 100.0, 0), 1)

    amount, amount_usd = _parse_amount(text)

    if re.search(r"\b(supply|deposit|lend)\b.+\baave\b", lower) or re.search(
        r"\baave\b.+\b(supply|deposit|lend)\b", lower
    ):
        return {
            "action": "aave_supply",
            "from_symbol": _first_ticker(text) or "USDC",
            "to_symbol": None,
            "amount": amount,
            "amount_usd": amount_usd,
            "fraction": fraction,
            "query": None,
            "protocol": "aave",
        }
    if re.search(r"\b(withdraw|remove)\b.+\baave\b", lower) or re.search(
        r"\baave\b.+\b(withdraw|remove)\b", lower
    ):
        return {
            "action": "aave_withdraw",
            "from_symbol": _first_ticker(text) or "USDC",
            "to_symbol": None,
            "amount": amount,
            "amount_usd": amount_usd,
            "fraction": 1.0 if fraction is None else fraction,
            "query": None,
            "protocol": "aave",
        }

    if re.search(r"\b(my|show|check|list|what).*\b(lp|liquidity|positions?)\b", lower) and not re.search(
        r"\b(add|provide|deposit|remove|withdraw|pull)\b", lower
    ):
        ticker = _first_ticker(text)
        return {
            "action": "lp_positions",
            "from_symbol": None if ticker == "USDC" else ticker,
            "to_symbol": "USDC" if ticker and ticker != "USDC" else None,
            "amount": None,
            "amount_usd": None,
            "fraction": None,
            "query": None,
            "protocol": protocol,
        }

    if re.search(r"\b(remove|withdraw|pull)\b.+\b(lp|liquidity)\b", lower) or re.search(
        r"\b(lp|liquidity)\b.+\b(remove|withdraw)\b", lower
    ):
        return {
            "action": "lp_remove",
            "from_symbol": _stock_or_default(text),
            "to_symbol": "USDC",
            "amount": None,
            "amount_usd": None,
            "fraction": 1.0 if fraction is None else fraction,
            "query": None,
            "protocol": protocol,
        }

    if (
        re.search(r"\b(add|provide|deposit).*\b(lp|liquidity)\b", lower)
        or (re.search(r"\b(lp|liquidity)\b", lower) and re.search(r"\b(add|uniswap|aerodrome)\b", lower))
    ):
        return {
            "action": "lp_add",
            "from_symbol": _stock_or_default(text),
            "to_symbol": "USDC",
            "amount": amount,
            "amount_usd": amount_usd,
            "fraction": 1.0 if fraction is None and not amount else fraction,
            "query": None,
            "protocol": protocol,
        }

    personal = (
        "my name",
        "what's my name",
        "whats my name",
        "what is my name",
        "who am i",
        "do you remember",
    )
    if any(p in lower for p in personal) and "swap" not in lower and "sell" not in lower:
        return {
            "action": "chat",
            "from_symbol": None,
            "to_symbol": None,
            "amount": None,
            "amount_usd": None,
            "fraction": None,
            "query": None,
            "protocol": protocol,
        }

    wants_trade = bool(re.search(r"\b(sell|swap|dump|cash out|convert)\b", lower))
    if ("balance" in lower or "how much" in lower or "holdings" in lower) and not wants_trade:
        return {
            "action": "balance",
            "from_symbol": _first_ticker(text),
            "to_symbol": None,
            "amount": None,
            "amount_usd": None,
            "fraction": None,
            "query": None,
            "protocol": protocol,
        }

    research_hints = ("what is", "what's", "news", "explain", "why", "how does", "tell me about")
    if any(h in lower for h in research_hints) and not wants_trade:
        return {
            "action": "research",
            "from_symbol": None,
            "to_symbol": None,
            "amount": None,
            "amount_usd": None,
            "fraction": None,
            "query": text,
            "protocol": protocol,
        }

    from_symbol, to_symbol = _parse_pair(text)
    if to_symbol and to_symbol.upper() in {"HEY", "HI", "HELLO", "OK", "YO"}:
        to_symbol = None
        from_symbol = None
    
    action = "swap"
    if lower.startswith("sell") or re.search(r"\b(sell|dump|cash out)\b", lower):
        action = "sell"
        if not from_symbol:
            from_symbol = _first_ticker(text)
        if not to_symbol:
            to_symbol = "USDC"
    elif "quote" in lower and not wants_trade:
        action = "quote"
    if action == "sell" and not to_symbol:
        to_symbol = "USDC"
    if not from_symbol and not to_symbol:
        return {
            "action": "chat" if len(text.split()) < 12 else "research",
            "from_symbol": None,
            "to_symbol": None,
            "amount": amount,
            "amount_usd": amount_usd,
            "fraction": fraction,
            "query": None if len(text.split()) < 12 else text,
            "protocol": protocol,
        }
    return {
        "action": action,
        "from_symbol": from_symbol,
        "to_symbol": to_symbol,
        "amount": amount,
        "amount_usd": amount_usd,
        "fraction": fraction,
        "query": None,
        "protocol": protocol,
    }

def parse_intent(state: AgentState) -> dict:
    message = state.get("user_message") or ""
    history = list(state.get("messages") or [])
    history.append({"role": "user", "content": message})
    intent = _regex_intent(message)
    lower = message.lower()
    if "aave" in lower:
        intent["protocol"] = "aave"
        if re.search(r"\b(withdraw|remove)\b", lower):
            intent["action"] = "aave_withdraw"
        elif re.search(r"\b(supply|deposit|lend|add)\b", lower):
            intent["action"] = "aave_supply"
    elif "uniswap" in lower and ("liquidity" in lower or re.search(r"\blp\b", lower) or "add" in lower):
        intent["protocol"] = "uniswap"
        intent["action"] = "lp_remove" if re.search(r"\b(remove|withdraw|pull)\b", lower) else "lp_add"
        intent["from_symbol"] = _stock_or_default(message)
        intent["to_symbol"] = "USDC"
    elif "liquidity" in lower or re.search(r"\blp\b", lower):
        if re.search(r"\b(my|show|check|list|what).*\b(lp|liquidity|positions?)\b", lower) and not re.search(
            r"\b(add|provide|deposit|remove|withdraw|pull)\b", lower
        ):
            intent["action"] = "lp_positions"
        elif re.search(r"\b(remove|withdraw|pull)\b", lower):
            intent["action"] = "lp_remove"
            intent["from_symbol"] = _stock_or_default(message)
            intent["to_symbol"] = "USDC"
        elif re.search(r"\b(add|provide|deposit|uniswap|aerodrome)\b", lower):
            intent["action"] = "lp_add"
            intent["from_symbol"] = _stock_or_default(message)
            intent["to_symbol"] = "USDC"
    intent.setdefault("action", "research")
    intent.setdefault("protocol", _protocol(message))
    return {"intent": intent, "messages": history, "action": {}, "quote": None, "assistant_text": ""}