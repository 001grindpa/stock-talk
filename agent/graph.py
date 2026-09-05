from dotenv import load_dotenv
import os
import json
import re
from typing import Any, Optional, TypedDict

from langchain_groq import ChatGroq
from langchain_tavily import TavilySearch
from langgraph.graph import END, START, StateGraph

try:
    from langgraph.checkpoint.memory import MemorySaver
except ImportError:
    from langgraph.checkpoint.memory import InMemorySaver as MemorySaver

from agent import tools as agent_tools
from agent.prompts import INTENT_SYSTEM, RESEARCH_SYSTEM, RESPONSE_SYSTEM
from agent.registry import MAX_DEMO_USD, list_tokens
from services.rpc import token_balance

load_dotenv()
os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY") or ""
os.environ["TAVILY_API_KEY"] = os.getenv("TAVILY_API_KEY") or ""

_GROQ_MODELS = [
    os.getenv("GROQ_MODEL") or "llama-3.3-70b-versatile",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
]
_groq_model_index = 0
llm = None
if os.getenv("GROQ_API_KEY"):
    llm = ChatGroq(model=_GROQ_MODELS[0], temperature=0)

_DB = None
memory = MemorySaver()


def _invoke_llm(messages: list):
    global llm, _groq_model_index
    if llm is None:
        return None
    last_error = None
    while _groq_model_index < len(_GROQ_MODELS):
        try:
            return llm.invoke(messages)
        except Exception as exc:
            last_error = exc
            text = str(exc).lower()
            if "404" not in text and "does not exist" not in text:
                raise
            _groq_model_index += 1
            if _groq_model_index >= len(_GROQ_MODELS):
                break
            llm = ChatGroq(model=_GROQ_MODELS[_groq_model_index], temperature=0)
    if last_error:
        raise last_error
    return None


web_search = None
if os.getenv("TAVILY_API_KEY"):
    web_search = TavilySearch(max_results=5)


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


def _db():
    return _DB


def _extract_json(text: str) -> dict | None:
    if not text:
        return None
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _regex_intent(message: str) -> dict:
    text = (message or "").strip()
    lower = text.lower()

    research_hints = (
        "what is",
        "what's",
        "news",
        "explain",
        "why",
        "how does",
        "tell me about",
        "price of apple stock today",
    )
    if any(h in lower for h in research_hints) and "swap" not in lower and "sell" not in lower:
        return {
            "action": "research",
            "from_symbol": None,
            "to_symbol": None,
            "amount": None,
            "amount_usd": None,
            "fraction": None,
            "query": text,
        }

    if "balance" in lower or "how much" in lower or "holdings" in lower:
        return {
            "action": "balance",
            "from_symbol": _first_ticker(text),
            "to_symbol": None,
            "amount": None,
            "amount_usd": None,
            "fraction": None,
            "query": None,
        }

    amount, amount_usd = _parse_amount(text)
    from_symbol, to_symbol = _parse_pair(text)
    fraction = None
    if re.search(r"\bhalf\b", lower):
        fraction = 0.5
    pct = re.search(r"\b(\d{1,3})\s*%", lower)
    if pct:
        fraction = min(max(int(pct.group(1)) / 100.0, 0), 1)

    action = "swap"
    if lower.startswith("sell") or re.search(r"\bsell\b", lower):
        action = "sell"
        if not from_symbol:
            from_symbol = _first_ticker(text)
        if not to_symbol:
            to_symbol = "USDC"
    elif "quote" in lower:
        action = "quote"

    if not from_symbol and not to_symbol:
        return {
            "action": "research",
            "from_symbol": None,
            "to_symbol": None,
            "amount": amount,
            "amount_usd": amount_usd,
            "fraction": fraction,
            "query": text,
        }

    return {
        "action": action,
        "from_symbol": from_symbol,
        "to_symbol": to_symbol,
        "amount": amount,
        "amount_usd": amount_usd,
        "fraction": fraction,
        "query": None,
    }


def _parse_amount(text: str) -> tuple[str | None, float | None]:
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


def _first_ticker(text: str) -> str | None:
    names = {
        "apple": "AAPL",
        "nvidia": "NVDA",
        "tesla": "TSLA",
        "meta": "META",
        "google": "GOOGL",
        "alphabet": "GOOGL",
        "amazon": "AMZN",
        "microsoft": "MSFT",
        "coinbase": "COIN",
        "intel": "INTC",
        "spacex": "SPCX",
        "usdc": "USDC",
        "usd": "USDC",
    }
    lower = text.lower()
    for name, tick in names.items():
        if re.search(rf"\b{name}\b", lower):
            return tick
    match = re.search(r"\b([A-Za-z]{2,6}c?)\b", text)
    if match:
        word = match.group(1)
        if word.lower() not in {"for", "swap", "sell", "quote", "with", "from", "into", "the", "and", "half"}:
            return word.upper()
    return None


def _parse_pair(text: str) -> tuple[str | None, str | None]:
    lower = text.lower()
    if re.search(r"(?:swap|buy|quote)\s+(?:\$\s*)?[\d,.]+\s*(?:usd|usdc|dollars?)?\s+(?:for|of|into)\s+", text, re.I) or re.search(
        r"\$\s*[\d,.]+\s*(usd|usdc|dollars?)?\s+for\s+", lower
    ):
        dest = None
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


def parse_intent(state: AgentState) -> dict:
    message = state.get("user_message") or ""
    history = list(state.get("messages") or [])
    history.append({"role": "user", "content": message})
    intent = None
    if llm is not None:
        try:
            result = _invoke_llm(
                [
                    {"role": "system", "content": INTENT_SYSTEM},
                    *[{"role": m["role"], "content": m["content"]} for m in history[-8:]],
                ]
            )
            intent = _extract_json(getattr(result, "content", "") or "")
        except Exception:
            intent = None
    if not intent:
        intent = _regex_intent(message)
    intent.setdefault("action", "research")
    return {"intent": intent, "messages": history, "action": {}, "quote": None, "assistant_text": ""}


def resolve_tokens(state: AgentState) -> dict:
    db = _db()
    intent = state.get("intent") or {}
    action_name = (intent.get("action") or "research").lower()
    from_symbol = intent.get("from_symbol")
    to_symbol = intent.get("to_symbol")

    if action_name == "sell":
        from_symbol = from_symbol or to_symbol
        to_symbol = intent.get("to_symbol") or "USDC"
    if action_name in {"swap", "quote"} and not from_symbol:
        from_symbol = "USDC"

    from_token = agent_tools.resolve_ticker(db, from_symbol) if from_symbol else None
    to_token = agent_tools.resolve_ticker(db, to_symbol) if to_symbol else None

    unknown = None
    if from_symbol and not from_token:
        unknown = from_symbol
    if to_symbol and not to_token:
        unknown = to_symbol

    updates: dict = {"from_token": from_token, "to_token": to_token}
    if unknown and action_name in {"swap", "sell", "quote"}:
        updates["action"] = {
            "type": "error",
            "message": f"{unknown} is not an official Coinbase Tokenized Stock on Base.",
        }
        updates["assistant_text"] = (
            f"I only trade official Coinbase Tokenized Stocks on Base. "
            f"I don't have an allowlisted token for {unknown}."
        )
    return updates


def maybe_web_search(state: AgentState) -> dict:
    intent = state.get("intent") or {}
    if (intent.get("action") or "").lower() != "research":
        return {"search_notes": ""}
    query = intent.get("query") or state.get("user_message") or ""
    notes = agent_tools.tavily_search(web_search, query)
    return {"search_notes": notes}


def _balance_map(state: AgentState) -> dict:
    out = {}
    for item in state.get("balances") or []:
        out[item["symbol"]] = item
    return out


def maybe_get_quote(state: AgentState) -> dict:
    if (state.get("action") or {}).get("type") == "error":
        return {}
    intent = state.get("intent") or {}
    action_name = (intent.get("action") or "").lower()
    if action_name not in {"swap", "sell", "quote"}:
        return {}

    wallet = state.get("wallet")
    if not wallet:
        return {
            "action": {"type": "none"},
            "assistant_text": "Connect a Base wallet (chain 8453) so I can quote a swap for you to sign.",
        }

    from_token = state.get("from_token")
    to_token = state.get("to_token")
    if not from_token or not to_token:
        return {
            "action": {"type": "error", "message": "Could not resolve both tokens."},
            "assistant_text": "I need an allowlisted from-token and to-token on Base.",
        }

    amount = intent.get("amount")
    amount_usd = intent.get("amount_usd")
    fraction = intent.get("fraction")
    held = _balance_map(state)

    if not amount and fraction and from_token:
        row = held.get(from_token["symbol"])
        if row:
            try:
                amount = str(float(row["formatted"]) * float(fraction))
            except (TypeError, ValueError):
                amount = None

    if amount_usd is None and from_token["symbol"] == "USDC" and amount:
        try:
            amount_usd = float(amount)
        except ValueError:
            amount_usd = None
    if amount_usd is not None and amount_usd > MAX_DEMO_USD:
        return {
            "action": {"type": "error", "message": f"Demo max is ${MAX_DEMO_USD:.0f}."},
            "assistant_text": f"This demo caps swaps at ${MAX_DEMO_USD:.0f} USD.",
        }

    if from_token and amount:
        row = held.get(from_token["symbol"])
        if row:
            try:
                if float(amount) - 1e-12 > float(row["formatted"]):
                    return {
                        "action": {"type": "error"},
                        "assistant_text": (
                            f"You have {row['formatted']} {from_token['symbol']}, "
                            f"which is less than {amount}."
                        ),
                    }
            except (TypeError, ValueError):
                pass

    if not amount:
        return {
            "action": {"type": "none"},
            "assistant_text": "How much should I swap? For example: swap $2 USD for AAPL.",
        }

    quote = agent_tools.get_quote(
        from_token=from_token,
        to_token=to_token,
        amount=str(amount),
        wallet=wallet,
    )
    mock = bool(quote.get("mock"))
    text = (
        f"I'll swap {quote['from']['amount']} {quote['from']['symbol']} for "
        f"{quote['to']['amount']} {quote['to']['symbol']} on Base. Confirm in your wallet."
    )
    if mock:
        text = (
            f"MOCK quote: {quote['from']['amount']} {quote['from']['symbol']} → "
            f"{quote['to']['amount']} {quote['to']['symbol']} on Base. "
            "Add a 0x API key for a live quote. Confirm stays off unless demo mode is enabled."
        )
    return {"quote": quote, "assistant_text": text}


def maybe_balance(state: AgentState) -> dict:
    intent = state.get("intent") or {}
    if (intent.get("action") or "").lower() != "balance":
        return {}
    wallet = state.get("wallet")
    if not wallet:
        return {
            "action": {"type": "none"},
            "assistant_text": "Connect your Base wallet to read allowlisted token balances.",
        }

    held = _balance_map(state)
    token = state.get("from_token")
    wanted = [token] if token else list_tokens(_db())
    lines = []
    for item in wanted:
        row = held.get(item["symbol"])
        if row:
            lines.append(f"{item['symbol']}: {row['formatted']}")
            continue
        raw = token_balance(item["address"], wallet)
        if raw is None:
            continue
        human = raw / (10 ** int(item["decimals"]))
        if human or token:
            lines.append(f"{item['symbol']}: {human:.6f}")

    if not lines:
        text = "I couldn't read balances. Connect the wallet and try “what’s my stock balance?” again."
    else:
        text = "On-chain balances (allowlist only):\n" + "\n".join(lines)
    return {"action": {"type": "none"}, "assistant_text": text}


def format_response(state: AgentState) -> dict:
    if (state.get("action") or {}).get("type") == "error":
        text = state.get("assistant_text") or state["action"].get("message")
        history = list(state.get("messages") or [])
        history.append({"role": "assistant", "content": text or ""})
        return {"action": state["action"], "assistant_text": text, "messages": history}

    intent = state.get("intent") or {}
    action_name = (intent.get("action") or "research").lower()
    quote = state.get("quote")
    history = list(state.get("messages") or [])

    if quote:
        action = {
            "type": "quote",
            "quote_id": None,
            "from": quote["from"],
            "to": quote["to"],
            "priceImpactBps": quote.get("priceImpactBps") or 0,
            "route": quote.get("route") or "0x",
            "tx": quote.get("tx") or {"to": None, "data": "0x", "value": "0"},
            "spender": quote.get("spender"),
            "mock": bool(quote.get("mock")),
        }
        text = state.get("assistant_text")
        if not text:
            text = (
                f"I’ll swap {quote['from']['amount']} {quote['from']['symbol']} for "
                f"{quote['to']['amount']} {quote['to']['symbol']} on Base. Confirm in your wallet."
            )
        history.append({"role": "assistant", "content": text})
        return {"action": action, "assistant_text": text, "messages": history}

    if action_name == "research":
        notes = state.get("search_notes") or ""
        question = state.get("user_message") or ""
        text = None
        if llm is not None:
            try:
                result = _invoke_llm(
                    [
                        {"role": "system", "content": RESEARCH_SYSTEM},
                        {"role": "user", "content": f"Question: {question}\n\nSearch notes:\n{notes}"},
                    ]
                )
                text = getattr(result, "content", None)
            except Exception:
                text = None
        if not text:
            text = notes or (
                "I can explain official Coinbase Tokenized Stocks on Base, or quote a swap such as "
                "“swap $2 USD for AAPL”."
            )
        history.append({"role": "assistant", "content": text})
        return {"action": {"type": "none"}, "assistant_text": text, "messages": history}

    text = state.get("assistant_text") or "Try: swap $2 USD for AAPL."
    history.append({"role": "assistant", "content": text})
    return {
        "action": state.get("action") or {"type": "none"},
        "assistant_text": text,
        "messages": history,
    }


def _route_after_parse(state: AgentState) -> str:
    action = ((state.get("intent") or {}).get("action") or "research").lower()
    if action == "research":
        return "search"
    return "resolve"


def _route_after_resolve(state: AgentState) -> str:
    if (state.get("action") or {}).get("type") == "error":
        return "format"
    action = ((state.get("intent") or {}).get("action") or "").lower()
    if action == "balance":
        return "balance"
    if action in {"swap", "sell", "quote"}:
        return "quote"
    return "format"


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("parse_intent", parse_intent)
    graph.add_node("resolve_tokens", resolve_tokens)
    graph.add_node("web_search", maybe_web_search)
    graph.add_node("get_quote", maybe_get_quote)
    graph.add_node("balance", maybe_balance)
    graph.add_node("format_response", format_response)
    graph.add_edge(START, "parse_intent")
    graph.add_conditional_edges(
        "parse_intent",
        _route_after_parse,
        {"search": "web_search", "resolve": "resolve_tokens"},
    )
    graph.add_edge("web_search", "format_response")
    graph.add_conditional_edges(
        "resolve_tokens",
        _route_after_resolve,
        {"quote": "get_quote", "balance": "balance", "format": "format_response"},
    )
    graph.add_edge("get_quote", "format_response")
    graph.add_edge("balance", "format_response")
    graph.add_edge("format_response", END)
    return graph.compile(checkpointer=memory)


_GRAPH = None


def run_agent(*, db, message: str, wallet: str | None, balances=None, thread_id: str | None = None, history=None) -> dict:
    global _GRAPH, _DB
    _DB = db
    if _GRAPH is None:
        _GRAPH = build_graph()

    prior = []
    for row in history or []:
        role = row.get("role") if isinstance(row, dict) else None
        content = row.get("content") if isinstance(row, dict) else None
        if role in {"user", "assistant"} and content:
            prior.append({"role": role, "content": content})

    thread = thread_id or "page-session"
    config = {"configurable": {"thread_id": thread}}
    result = _GRAPH.invoke(
        {
            "user_message": message,
            "wallet": wallet,
            "balances": agent_tools.normalize_balances(balances, db),
            "messages": prior,
        },
        config=config,
    )
    return {
        "message": result.get("assistant_text") or "",
        "action": result.get("action") or {"type": "none"},
        "quote": result.get("quote"),
        "intent": result.get("intent") or {},
        "thread_id": thread,
    }