from dotenv import load_dotenv
import os
from typing import Optional, TypedDict

from langchain_groq import ChatGroq
from langchain_tavily import TavilySearch
from langgraph.graph import END, START, StateGraph

try:
    from langgraph.checkpoint.memory import MemorySaver
except ImportError:
    from langgraph.checkpoint.memory import InMemorySaver as MemorySaver

from agent import tools as agent_tools
from agent.prompts import RESEARCH_SYSTEM
from agent.registry import list_tokens
from services.aave import (
    build_aave_borrow,
    build_aave_collateral,
    build_aave_repay,
    build_aave_supply,
    build_aave_withdraw,
    listed_asset,
    describe_account
)
from services.aerodrome import find_pool
from services.aerodrome_lp import build_add_lp, build_remove_lp
from services.rpc import token_balance
from services.uniswap_lp import build_uni_add
from agent.intent import parse_intent

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


_AAVE_ACTIONS = {
    "aave_supply",
    "aave_withdraw",
    "aave_borrow",
    "aave_repay",
    "aave_collateral",
}

_AAVE_ONLY = "Aave lending on Base is only for USDC and WETH. Tokenized stocks cannot be supplied, used as collateral, borrowed, or repaid."


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
    if action_name in {"lp_add", "lp_remove"}:
        from_symbol = from_symbol or "AAPL"
        if from_symbol == "USDC":
            from_symbol = "AAPL"
        to_symbol = "USDC" if to_symbol in {None, from_symbol} else to_symbol
    if action_name in _AAVE_ACTIONS:
        from_symbol = from_symbol or "USDC"
    from_token = agent_tools.resolve_ticker(db, from_symbol) if from_symbol else None
    to_token = agent_tools.resolve_ticker(db, to_symbol) if to_symbol else None
    updates = {"from_token": from_token, "to_token": to_token}
    if action_name in {"swap", "sell", "quote", "lp_add", "lp_remove"} and (not from_token or not to_token):
        updates["action"] = {"type": "error", "message": "Need two allowlisted tokens."}
        updates["assistant_text"] = "I only use official Coinbase Tokenized Stocks + USDC on Base."
    if action_name in _AAVE_ACTIONS:
        asset = listed_asset(from_token or to_token or {"symbol": from_symbol})
        if not asset:
            updates["action"] = {"type": "error", "message": _AAVE_ONLY}
            updates["assistant_text"] = _AAVE_ONLY
    return updates


def maybe_web_search(state: AgentState) -> dict:
    intent = state.get("intent") or {}
    if (intent.get("action") or "").lower() != "research":
        return {"search_notes": ""}
    query = intent.get("query") or state.get("user_message") or ""
    return {"search_notes": agent_tools.tavily_search(web_search, query)}


def _balance_map(state: AgentState) -> dict:
    out = {}
    for item in state.get("balances") or []:
        out[item["symbol"]] = item
    return out


def _held_amount(state: AgentState, token: dict | None) -> str | None:
    if not token:
        return None
    row = _balance_map(state).get(token["symbol"])
    if not row:
        addr = token["address"].lower()
        for item in state.get("balances") or []:
            if (item.get("address") or "").lower() == addr:
                row = item
                break
    if not row:
        return None
    return str(row.get("formatted") or "0")


def _too_poor(state: AgentState, token: dict | None, amount, fraction):
    if not token:
        return None
    held = _held_amount(state, token)
    try:
        have = float(held or 0)
    except (TypeError, ValueError):
        have = 0.0
    if fraction:
        if have <= 0:
            return f"Balance too low. You have 0 {token['symbol']} for that action."
        return None
    if amount is None:
        return None
    try:
        need = float(amount)
    except (TypeError, ValueError):
        return None
    if have + 1e-12 < need:
        return (
            f"Balance too low. You have {have:.6f} {token['symbol']}, "
            f"which is less than {need}."
        )
    return None


def maybe_lp(state: AgentState) -> dict:
    intent = state.get("intent") or {}
    action_name = (intent.get("action") or "").lower()
    protocol = (intent.get("protocol") or "aerodrome").lower()
    wallet = state.get("wallet")
    token_a = state.get("from_token")
    token_b = state.get("to_token")
    balances = state.get("balances") or []
    frac = intent.get("fraction")
    amount = intent.get("amount")

    if action_name in {"lp_add", "aave_supply", "aave_repay"}:
        poor = _too_poor(state, token_a or token_b, amount, frac)
        if poor:
            return {"action": {"type": "error"}, "assistant_text": poor}

    if action_name == "aave_supply":
        built = build_aave_supply(token=token_a or token_b, amount=amount, fraction=frac, wallet=wallet, balances=balances)
    elif action_name == "aave_withdraw":
        built = build_aave_withdraw(token=token_a or token_b, amount=amount, fraction=frac, wallet=wallet, balances=balances)
    elif action_name == "aave_borrow":
        built = build_aave_borrow(token=token_a or token_b, amount=amount, fraction=frac, wallet=wallet, balances=balances)
    elif action_name == "aave_repay":
        built = build_aave_repay(token=token_a or token_b, amount=amount, fraction=frac, wallet=wallet, balances=balances)
    elif action_name == "aave_collateral":
        built = build_aave_collateral(token=token_a or token_b, wallet=wallet, enabled=True)
    elif action_name == "lp_add" and protocol == "uniswap":
        built = build_uni_add(
            token_a=token_a, token_b=token_b, amount_a=amount, amount_b=None,
            fraction=frac or 1, wallet=wallet, balances=balances,
        )
    elif action_name == "lp_remove" and protocol == "uniswap":
        built = {"error": "Uniswap V3 remove needs the position NFT id. Use the Uniswap UI for now."}
    elif action_name == "lp_remove":
        built = build_remove_lp(token_a=token_a, token_b=token_b, fraction=frac or 1, wallet=wallet, balances=balances)
    elif action_name == "lp_add":
        if not amount and frac:
            held = _held_amount(state, token_a)
            if held:
                try:
                    amount = str(float(held) * float(frac))
                except (TypeError, ValueError):
                    amount = held
        built = build_add_lp(
            token_a=token_a, token_b=token_b, amount_a=amount, amount_b=None, wallet=wallet, balances=balances
        )
    else:
        return {}

    if built.get("error"):
        return {"action": {"type": "error"}, "assistant_text": built["error"]}
    return {"action": built, "assistant_text": (built.get("summary") or "Confirm") + ". Confirm in your wallet."}


def maybe_lp_positions(state: AgentState) -> dict:
    intent = state.get("intent") or {}
    if (intent.get("action") or "").lower() != "lp_positions":
        return {}
    wallet = state.get("wallet")
    if not wallet:
        return {"action": {"type": "none"}, "assistant_text": "Connect a Base wallet to read LP balances."}
    lines = []
    seen = set()
    tokens = list_tokens(_db())
    usdc = next((t for t in tokens if t["symbol"] == "USDC"), None)
    stocks = [t for t in tokens if t.get("kind") == "stock"] or [t for t in tokens if t["symbol"] != "USDC"]
    wanted = []
    if state.get("from_token") and state.get("to_token"):
        wanted.append((state["from_token"], state["to_token"]))
    elif usdc:
        wanted.extend((stock, usdc) for stock in stocks)
    for token_a, token_b in wanted:
        pool, stable = find_pool(token_a["address"], token_b["address"])
        if not pool or pool.lower() in seen:
            continue
        seen.add(pool.lower())
        raw = token_balance(pool, wallet) or 0
        if raw <= 0:
            continue
        lines.append(
            f"{token_a['symbol']}/{token_b['symbol']} "
            f"({'stable' if stable else 'volatile'}): {raw / 10**18:.8f} LP ({pool})"
        )
    text = (
        "Aerodrome LP positions:\n" + "\n".join(lines)
        if lines
        else "No Aerodrome LP tokens in this wallet for allowlisted pairs."
    )
    return {"action": {"type": "none"}, "assistant_text": text}


def maybe_get_quote(state: AgentState) -> dict:
    if (state.get("action") or {}).get("type") == "error":
        return {}
    intent = state.get("intent") or {}
    if (intent.get("action") or "").lower() not in {"swap", "sell", "quote"}:
        return {}
    wallet = state.get("wallet")
    if not wallet:
        return {"action": {"type": "none"}, "assistant_text": "Connect a Base wallet so I can quote a swap."}
    from_token = state.get("from_token")
    to_token = state.get("to_token")
    if not from_token or not to_token:
        return {"action": {"type": "error"}, "assistant_text": "Need an allowlisted pair."}
    amount = intent.get("amount")
    fraction = intent.get("fraction")
    poor = _too_poor(state, from_token, amount, fraction)
    if poor:
        return {"action": {"type": "error"}, "assistant_text": poor}
    if not amount and fraction:
        held = _held_amount(state, from_token)
        if held:
            try:
                amount = str(float(held) * float(fraction))
            except (TypeError, ValueError):
                amount = held
    if not amount:
        return {"action": {"type": "none"}, "assistant_text": "How much should I swap? Example: swap $2 USD for AAPL."}
    quote = agent_tools.get_quote(from_token=from_token, to_token=to_token, amount=str(amount), wallet=wallet)
    if quote.get("error"):
        return {"action": {"type": "error"}, "assistant_text": quote["error"]}
    text = (
        f"I'll swap {quote['from']['amount']} {quote['from']['symbol']} for "
        f"{quote['to']['amount']} {quote['to']['symbol']} on Base via {quote.get('route') or 'router'}. "
        "Confirm in your wallet."
    )
    return {"quote": quote, "assistant_text": text}


def maybe_balance(state: AgentState) -> dict:
    intent = state.get("intent") or {}
    if (intent.get("action") or "").lower() != "balance":
        return {}
    wallet = state.get("wallet")
    if not wallet:
        return {"action": {"type": "none"}, "assistant_text": "Connect your Base wallet to read balances."}
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
    text = "On-chain balances:\n" + "\n".join(lines) if lines else "No allowlisted balances found."
    return {"action": {"type": "none"}, "assistant_text": text}


def format_response(state: AgentState) -> dict:
    history = list(state.get("messages") or [])
    action = state.get("action") or {"type": "none"}
    intent = state.get("intent") or {}
    action_name = (intent.get("action") or "research").lower()

    if action_name == "tokens":
        names = [t["symbol"] for t in list_tokens(_db())]
        text = "I can swap these allowlisted tokens on Base:\n" + ", ".join(names)
        history.append({"role": "assistant", "content": text})
        return {"action": {"type": "none"}, "assistant_text": text, "messages": history}

    if action_name == "aave_account":
        wallet = state.get("wallet")
        text = (
            "Connect a Base wallet to read your Aave account."
            if not wallet
            else describe_account(wallet)
        )
        history.append({"role": "assistant", "content": text})
        return {"action": {"type": "none"}, "assistant_text": text, "messages": history}

    if action.get("type") == "error":
        text = state.get("assistant_text") or action.get("message") or "That failed."
        history.append({"role": "assistant", "content": text})
        return {"action": action, "assistant_text": text, "messages": history}
    if action.get("type") == "tx":
        text = state.get("assistant_text") or action.get("summary") or "Confirm in your wallet."
        history.append({"role": "assistant", "content": text})
        return {"action": action, "assistant_text": text, "messages": history}
    quote = state.get("quote")
    if quote and not quote.get("error"):
        action = {
            "type": "quote",
            "quote_id": None,
            "from": quote["from"],
            "to": quote["to"],
            "priceImpactBps": quote.get("priceImpactBps") or 0,
            "route": quote.get("route") or "aerodrome",
            "tx": quote.get("tx") or {"to": None, "data": "0x", "value": "0"},
            "spender": quote.get("spender"),
            "mock": bool(quote.get("mock")),
        }
        text = state.get("assistant_text") or (
            f"I’ll swap {quote['from']['amount']} {quote['from']['symbol']} for "
            f"{quote['to']['amount']} {quote['to']['symbol']} on Base."
        )
        history.append({"role": "assistant", "content": text})
        return {"action": action, "assistant_text": text, "messages": history}

    if action_name in {"research", "chat"}:
        notes = state.get("search_notes") or ""
        question = state.get("user_message") or ""
        text = None
        if llm is not None:
            try:
                result = _invoke_llm(
                    [
                        {"role": "system", "content": RESEARCH_SYSTEM},
                        *[{"role": m["role"], "content": m["content"]} for m in history[-12:]],
                        {"role": "user", "content": f"{question}\n\nWeb notes:\n{notes}"},
                    ]
                )
                text = getattr(result, "content", None)
            except Exception:
                text = None
        text = text or notes or "Okay."
        history.append({"role": "assistant", "content": text})
        return {"action": {"type": "none"}, "assistant_text": text, "messages": history}

    text = state.get("assistant_text") or "Try: swap $2 USD for AAPL."
    history.append({"role": "assistant", "content": text})
    return {"action": {"type": "none"}, "assistant_text": text, "messages": history}


def _route_after_parse(state: AgentState) -> str:
    action = ((state.get("intent") or {}).get("action") or "research").lower()
    if action in {"chat", "tokens", "aave_account"}:
        return "format"
    if action == "research":
        return "search"
    if action in {"chat", "tokens"}:
        return "format"
    return "resolve"


def _route_after_resolve(state: AgentState) -> str:
    if (state.get("action") or {}).get("type") == "error":
        return "format"
    action = ((state.get("intent") or {}).get("action") or "").lower()
    if action in {"lp_add", "lp_remove"} or action in _AAVE_ACTIONS:
        return "lp"
    if action == "lp_positions":
        return "lp_positions"
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
    graph.add_node("lp", maybe_lp)
    graph.add_node("lp_positions", maybe_lp_positions)
    graph.add_node("format_response", format_response)
    graph.add_edge(START, "parse_intent")
    graph.add_conditional_edges(
        "parse_intent",
        _route_after_parse,
        {"search": "web_search", "resolve": "resolve_tokens", "format": "format_response"},
    )
    graph.add_edge("web_search", "format_response")
    graph.add_conditional_edges(
        "resolve_tokens",
        _route_after_resolve,
        {
            "quote": "get_quote",
            "balance": "balance",
            "lp": "lp",
            "lp_positions": "lp_positions",
            "format": "format_response",
        },
    )
    graph.add_edge("get_quote", "format_response")
    graph.add_edge("balance", "format_response")
    graph.add_edge("lp", "format_response")
    graph.add_edge("lp_positions", "format_response")
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
        if isinstance(row, dict) and row.get("role") in {"user", "assistant"} and row.get("content"):
            prior.append({"role": row["role"], "content": row["content"]})
    result = _GRAPH.invoke(
        {
            "user_message": message,
            "wallet": wallet,
            "balances": agent_tools.normalize_balances(balances, db),
            "messages": prior,
        },
        config={"configurable": {"thread_id": thread_id or "page-session"}},
    )
    return {
        "message": result.get("assistant_text") or "",
        "action": result.get("action") or {"type": "none"},
        "quote": result.get("quote"),
        "intent": result.get("intent") or {},
        "thread_id": thread_id,
    }