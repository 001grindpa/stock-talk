from __future__ import annotations

from dotenv import load_dotenv
import os
import asyncio
from typing import Annotated, Optional, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_mcp_adapters.client import MultiServerMCPClient

try:
    from langgraph.checkpoint.memory import MemorySaver
except ImportError:
    from langgraph.checkpoint.memory import InMemorySaver as MemorySaver

from agent import tools as agent_tools
from agent.registry import list_tokens
from services.aave import (
    build_aave_borrow,
    build_aave_collateral,
    build_aave_repay,
    build_aave_supply,
    build_aave_withdraw,
    describe_account,
    LISTED,
)
from services.morpho import (
    build_morpho_borrow,
    build_morpho_repay,
    build_morpho_supply,
    build_morpho_withdraw,
    describe_account as describe_morpho,
)
from services.aerodrome import find_pool
from services.aerodrome_lp import build_add_lp, build_remove_lp
from services.slipstream_lp import build_slip_add, build_slip_remove, list_slip_positions
from services.rpc import token_balance
from services.uniswap_lp import build_uni_add, build_uni_remove, list_uni_positions
from services.quotes import from_wei

load_dotenv()
os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY") or ""
os.environ["TAVILY_API_KEY"] = os.getenv("TAVILY_API_KEY") or ""
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY") or ""

_GROQ_MODELS = [
    os.getenv("GROQ_MODEL") or "qwen/qwen3.8-27b",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
]
_groq_model_index = 0
_llm = None
if os.getenv("OPENAI_API_KEY"):
    _llm = ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        model="minimax/minimax-m3",
        temperature=0,
        extra_body={"provider": {"sort": "throughput"}},
    )

memory = MemorySaver()
_DB = None
_CTX: dict = {"wallet": None, "balances": [], "action": None, "quote": None}

NATIVE_ETH = "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"

SYSTEM = """
You are Stocktalk, a Base-only assistant for official Coinbase Tokenized Stocks (B20) plus USDC, USDT, native ETH, WETH, cbBTC, and WBTC.

You can use Aave V3 on Base for USDC and WETH, and Morpho Blue on Base for isolated WETH/USDC markets (supply collateral, borrow, repay, withdraw).
Rules:
1. Always call a tool for facts, balances, quotes, LP, Aave, or Morpho. Do not invent or assume prices, txs, or addresses.
2. Never say you signed a transaction. The user's wallet signs after you return a quote/tx card.
3. Tokenized stocks cannot be supplied or borrowed on Aave V3 or these Morpho markets. Say that via the tool error.
4. If the user wants a swap/sell, call quote_swap. ETH means native gas Ether (0xEeee…). WETH is wrapped. BTC/BITCOIN means cbBTC. WBTC is the separate wrapped BTC token.
5. If they want LP, call the matching LP tool and pass pair_symbol=USDC|USDT|WETH|WBTC|CBBTC. Do not use native ETH as an LP quote token; use WETH.
6. If they ask what tokens you support, call list_allowlisted_tokens.
7. If a tool returns Balance too low, tell the user that. Do not ask them to sign.
8. Keep the final user-facing line short. Do not mention tool names unless asked.
9. If the user asks what routes, protocols, DEXes, or venues you use, call list_routes.
10. If the user asks for protocol or router contract addresses, call list_protocol_addresses. Never guess an address.
11. Use light markdown only: short paragraphs, **bold**, `code`, and lists. No headings, no HTML, no tables.
12. Keep replies brief.
13. If the user says Morpho, call the morpho_* tools, not Aave.
14. If the user wants to supply or borrow a tokenized stock, say Aave V4 stock markets are not live on Base yet.
15. Coinbase Tokenized Stocks are only for eligible non-US persons. If the user says they are a US person, do not build a quote. Not investment advice.
16. When you use the 'get_stock_data' tool, keep your final response specific to what user asked, don't give user everything returned from tool by default.
17. If the user says $N or N dollars of a token (e.g. "swap $1 ETH to MSFT"), pass amount_usd=N into quote_swap. Do not pass amount=1. "$1 ETH" is not 1 ETH.
18. If the user asks what LP pools exist (not their balances), call list_live_stock_pools. list_lp_positions is only the user's positions.
"""


class State(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    wallet: Optional[str]


def _token(symbol: str | None):
    return agent_tools.resolve_ticker(_DB, symbol) if symbol else None


QUOTE_SYMS = ("USDC", "USDT", "WETH", "WBTC", "CBBTC")


def _quote_token(symbol: str):
    s = (symbol or "USDC").upper().replace(" ", "")
    s = {
        "ETH": "WETH",
        "ETHER": "WETH",
        "USD": "USDC",
        "BTC": "CBBTC",
        "BITCOIN": "CBBTC",
    }.get(s, s)
    if s not in QUOTE_SYMS:
        return None
    return _token(s)


def _is_native(token: dict | None) -> bool:
    if not token:
        return False
    return (token.get("address") or "").lower() == NATIVE_ETH or (token.get("kind") == "native")


def _held(symbol: str) -> float:
    want = (symbol or "").upper()
    for item in _CTX.get("balances") or []:
        if (item.get("symbol") or "").upper() == want:
            try:
                return float(item.get("formatted") or 0)
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def _too_poor(symbol: str, amount: str | None, fraction: float | None) -> str | None:
    have = _held(symbol)
    if fraction:
        if have <= 0:
            return f"Balance too low. You have 0 {symbol} for that action."
        return None
    if not amount:
        return None
    try:
        need = float(amount)
    except (TypeError, ValueError):
        return None
    if have + 1e-12 < need:
        return (
            f"Balance too low. You have {have:.6f} {symbol}, "
            f"which is less than {need}."
        )
    return None


def _set_action(action: dict | None, quote: dict | None = None, text: str = "") -> str:
    if action and action.get("error"):
        _CTX["action"] = {"type": "error", "message": action["error"]}
        _CTX["quote"] = None
        return action["error"]
    if quote and quote.get("error"):
        _CTX["action"] = {"type": "error", "message": quote["error"]}
        _CTX["quote"] = None
        return quote["error"]
    if quote:
        _CTX["quote"] = quote
        _CTX["action"] = {
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
        return text or (
            f"I'll swap {quote['from']['amount']} {quote['from']['symbol']} for "
            f"{quote['to']['amount']} {quote['to']['symbol']} on Base via {quote.get('route')}. "
            "Confirm in your wallet."
        )
    if action:
        _CTX["action"] = action
        _CTX["quote"] = None
        return text or ((action.get("summary") or "Confirm") + ". Confirm in your wallet.")
    return text


@tool
def list_allowlisted_tokens() -> str:
    """List official allowlisted tokens this agent can swap or LP."""
    names = [t["symbol"] for t in list_tokens(_DB)]
    return (
        "Allowlisted on Base: " + ", ".join(names)
        + ". Swaps: stocks plus USDC, USDT, native ETH, WETH, cbBTC, WBTC. "
        "LP quote tokens: USDC, USDT, WETH, cbBTC, WBTC (not native ETH). "
        "Aave V3 and Morpho Blue lending are USDC and WETH only."
    )


@tool
def list_routes() -> str:
    """Describe swap, LP, and lending venues this agent can use on Base."""
    return (
        "Swaps (quote_swap), in order: 1inch if ONEINCH_API_KEY is set, "
        "KyberSwap aggregator, Odos if their API is up, Aerodrome Slipstream CL, "
        "Aerodrome V2 (direct or USDC hop), then 0x (often blocked for B20 stocks). "
        "Native ETH sells use the 0xEeee… sentinel and send tx.value (no approve).\n"
        "LP add/remove/list: stock paired with USDC, USDT, WETH, cbBTC, or WBTC on "
        "Aerodrome V2, Slipstream, or Uniswap V3. "
        "Pass pair_symbol=USDC|USDT|WETH|CBBTC|WBTC and protocol=aerodrome|slipstream|uniswap.\n"
        "Lending: Aave V3 on Base for USDC and WETH. "
        "Morpho Blue isolated markets: WETH collateral → borrow USDC (86% LLTV), "
        "USDC collateral → borrow WETH (86% LLTV). "
        "Tokenized stocks are not listed on Aave V3 or these Morpho markets. "
        "USDT, cbBTC, WBTC, and native ETH are swap-only for lending.\n"
        "Wallet signs every tx. Backend never holds keys."
    )


@tool
def list_protocol_addresses() -> str:
    """Official Base contract addresses this app uses. Do not invent others."""
    return (
        "Base chainId 8453.\n"
        "Native ETH sentinel 0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE\n"
        "USDC 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913\n"
        "WETH 0x4200000000000000000000000000000000000006\n"
        "cbBTC 0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf\n"
        "WBTC 0x0555e30da8f98308EdB960aa94C0Db47230d2b9c\n"
        "USDT 0xfde4C96c8593536E31F229EA8f37b2ADa2699bb2\n"
        "Aerodrome V2 router 0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43\n"
        "Aerodrome V2 factory 0x420DD381b31aEf6683db6B902084cB0FFECe40Da\n"
        "Slipstream CL factories 0x5e7BB104d84c7CB9B682AaC2F3d509f5F406809A, "
        "0xaDe65c38CD4849aDBA595a4323a8C7DdfE89716a, "
        "0xf8f2eB4940CFE7d13603DDDD87f123820Fc061Ef\n"
        "Slipstream routers 0xBE6D8f0d05cC4be24d5167a3eF062215bE6D18a5, "
        "0x698Cb2b6dd822994581fEa6eA4Fc755d1363A92F\n"
        "Slipstream NPMs 0x827922686190790b37229fd06084350E74485b72, "
        "0xa990C6a764b73BF43cee5Bb40339c3322FB9D55F, "
        "0xe1f8cd9AC4e4A65F54f38a5CdAfCA44f6dD68b53\n"
        "Uniswap V3 factory 0x33128a8fC17869897dcE68Ed026d694621f6FDfD\n"
        "Uniswap V3 NPM 0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1\n"
        "Uniswap SwapRouter02 0x2626664c2603336E57B271c5C0b26F421741e481\n"
        "Kyber MetaAggregationRouterV2 0x6131B5fae19EA4f9D964eAc0408E4408b66337b5\n"
        "Aave V3 Pool (Base) 0xA238Dd80C259a72e81d7e4664a9801593F98d1c5\n"
        "Morpho Blue (Base) 0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb\n"
        "Morpho AdaptiveCurveIRM 0x46415998764C29aB2a25CbeA6254146D50D22687\n"
        "Morpho WETH/USDC 86% 0x8793cf302b8ffd655ab97bd1c695dbd967807e8367a65cb2f4edaf1380ba1bda\n"
        "Morpho USDC/WETH 86% 0x3b3769cfca57be2eaed03fcc5299c25691b77781a1e124e7a8d520eb9a7eabb5\n"
        "Stock token addresses come from list_allowlisted_tokens / the registry, not from memory."
    )


@tool
def get_balances(symbol: str = "") -> str:
    """Read wallet balances for allowlisted tokens, native ETH, aTokens, Aave, and Morpho."""
    wallet = _CTX.get("wallet")
    if not wallet:
        return "Connect a Base wallet to read balances."

    wanted = [_token(symbol)] if symbol else list_tokens(_DB)
    wanted = [t for t in wanted if t]
    needle = (symbol or "").upper().replace("AUSDC", "USDC").replace("AWETH", "WETH")
    if needle in {"BTC", "BITCOIN"}:
        needle = "CBBTC"
    if needle in {"ETHER"}:
        needle = "ETH"
    if not needle or needle in {"WETH"}:
        wanted = wanted + [_token("WETH")]
    if not needle or needle in {"ETH", "GAS"}:
        wanted = wanted + [_token("ETH")]
    if not needle or needle in {"WBTC"}:
        wanted = wanted + [_token("WBTC")]
    if not needle or needle in {"CBBTC", "BTC", "BITCOIN"}:
        wanted = wanted + [_token("CBBTC")]

    lines = []
    held = {i.get("symbol"): i for i in (_CTX.get("balances") or [])}
    seen = set()
    for item in wanted:
        if not item:
            continue
        key = (item.get("address") or item["symbol"]).lower()
        if key in seen:
            continue
        seen.add(key)
        row = held.get(item["symbol"])
        if row:
            lines.append(f"{item['symbol']}: {row.get('formatted')}")
            continue
        if _is_native(item):
            continue
        raw = token_balance(item["address"], wallet)
        if raw is None:
            continue
        human = raw / (10 ** int(item["decimals"]))
        if human or symbol:
            lines.append(f"{item['symbol']}: {human:.6f}")

    want_aave = (not needle) or needle in {"AAVE", "USDC", "WETH", "ETH", "AUSDC", "AWETH"}
    want_morpho = (not needle) or needle in {"MORPHO", "USDC", "WETH", "ETH"}
    if want_aave:
        for asset in LISTED.values():
            raw = token_balance(asset["a_token"], wallet) or 0
            if raw or needle:
                human = raw / (10 ** int(asset["decimals"]))
                lines.append(f"a{asset['symbol']}: {human:.6f}")

    text = "On-chain balances:\n" + "\n".join(lines) if lines else "No allowlisted balances found."
    if want_aave:
        text += "\n\n" + describe_account(wallet)
    if want_morpho:
        text += "\n\n" + describe_morpho(wallet)
    return text


@tool
def quote_swap(from_symbol: str, to_symbol: str, amount: str = "", fraction: float = 0, amount_usd: float = 0) -> str:
    """Build an unsigned swap quote on Base. Use fraction=1 for all/100%. ETH is native gas."""
    wallet = _CTX.get("wallet")
    if not wallet:
        return "Connect a Base wallet so I can quote a swap."

    def _swap_sym(raw: str) -> str:
        s = (raw or "").upper().replace(" ", "")
        return {
            "AUSDC": "USDC",
            "AWETH": "WETH",
            "ETHER": "ETH",
            "GAS": "ETH",
            "BTC": "CBBTC",
            "BITCOIN": "CBBTC",
        }.get(s, raw)

    from_token = _token(_swap_sym(from_symbol))
    to_token = _token(_swap_sym(to_symbol))
    if not from_token or not to_token:
        return _set_action({
            "error": "I only swap official Coinbase Tokenized Stocks, USDC, USDT, ETH, WETH, cbBTC, and WBTC on Base."
        })
    if from_token["address"].lower() == to_token["address"].lower():
        return "Those are the same asset after mapping aliases."

    a_from = LISTED.get(from_token["symbol"])
    if a_from:
        a_bal = token_balance(a_from["a_token"], wallet) or 0
        wallet_bal = _held(from_token["symbol"])
        if wallet_bal <= 0 and a_bal > 0:
            return _set_action({
                "error": (
                    f"Your {from_token['symbol']} is in Aave as a{from_token['symbol']}. "
                    f"Withdraw it first, then I can swap it."
                )
            })

    if amount_usd and float(amount_usd) > 0:
        usd = float(amount_usd)
        if from_token["symbol"] in {"USDC", "USDT"}:
            amt = format(usd, "f")
        else:
            usdc = _token("USDC")
            probe = "0.001" if from_token["symbol"] in {"ETH", "WETH"} else "0.01"
            sample = agent_tools.get_quote(
                from_token=from_token, to_token=usdc, amount=probe, wallet=wallet
            )
            if sample.get("error"):
                return _set_action({"error": sample["error"]})
            usd_out = float(sample["to"]["amount"])
            if usd_out <= 0:
                return _set_action({"error": "Could not price that token in USD."})
            amt = format(float(probe) * (usd / usd_out), "f")
        use_frac = None
    else:
        amt = amount
        use_frac = fraction if (not amt or amt in {"0", "0.0"}) else None

    if use_frac:
        raw = None
        for row in _CTX.get("balances") or []:
            if (row.get("symbol") or "").upper() == from_token["symbol"].upper():
                raw = row.get("raw")
                break
        if raw not in (None, ""):
            take = int(int(raw) * float(use_frac))
            if take < 1:
                return _set_action({"error": f"Balance too low to swap {from_token['symbol']}."})
            amt = from_wei(str(take), from_token["decimals"], places=18)
        else:
            amt = format(_held(from_token["symbol"]) * float(use_frac), "f")
    poor = _too_poor(from_token["symbol"], amt, use_frac)
    if poor:
        return _set_action({"error": poor})
    if not amt:
        return "How much should I swap? Example: swap 0.001 ETH for USDC."
    quote = agent_tools.get_quote(from_token=from_token, to_token=to_token, amount=str(amt), wallet=wallet)
    return _set_action(None, quote)


@tool
def add_liquidity(
    stock_symbol: str,
    pair_symbol: str = "USDC",
    amount: str = "",
    fraction: float = 1,
    protocol: str = "aerodrome",
) -> str:
    """Add LP for a tokenized stock paired with USDC, USDT, WETH, cbBTC, or WBTC."""
    wallet = _CTX.get("wallet")
    token_a = _token(stock_symbol) or _token("AAPL")
    token_b = _quote_token(pair_symbol)
    if not token_b:
        return _set_action({
            "error": "LP quote token must be USDC, USDT, WETH, cbBTC, or WBTC. Native ETH is not used for LP."
        })
    use_frac = fraction if (not amount or amount in {"0", "0.0"}) else None
    poor = _too_poor(token_a["symbol"] if token_a else stock_symbol, amount, use_frac)
    if poor:
        return _set_action({"error": poor})
    proto = (protocol or "aerodrome").lower()
    balances = _CTX.get("balances")
    if proto in {"uniswap", "uni"}:
        built = build_uni_add(
            token_a=token_a, token_b=token_b, amount_a=amount or None, amount_b=None,
            fraction=fraction or 1, wallet=wallet, balances=balances,
        )
    elif proto in {"slipstream", "aero-cl", "aerodrome-cl", "cl"}:
        built = build_slip_add(
            token_a=token_a, token_b=token_b, amount_a=amount or None, amount_b=None,
            fraction=fraction or 1, wallet=wallet, balances=balances,
        )
    else:
        built = build_add_lp(
            token_a=token_a, token_b=token_b, amount_a=amount or None, amount_b=None,
            wallet=wallet, balances=balances,
        )
    if isinstance(built, dict) and built.get("error"):
        err = built["error"]
        if "pool" in err.lower() or "route" in err.lower() or "no " in err.lower():
            built["error"] = (
                f"No live {token_a['symbol']}/{token_b['symbol']} pool on {proto}. "
                f"{err}"
            )
    return _set_action(built)


@tool
def remove_liquidity(
    stock_symbol: str,
    pair_symbol: str = "USDC",
    fraction: float = 1,
    protocol: str = "aerodrome",
) -> str:
    """Remove LP for stock paired with USDC, USDT, WETH, cbBTC, or WBTC."""
    token_a = _token(stock_symbol) or _token("AAPL")
    token_b = _quote_token(pair_symbol) or _token("USDC")
    proto = (protocol or "aerodrome").lower()
    balances = _CTX.get("balances")
    wallet = _CTX.get("wallet")
    if proto in {"uniswap", "uni"}:
        built = build_uni_remove(
            token_a=token_a, token_b=token_b, fraction=fraction or 1,
            wallet=wallet, balances=balances,
        )
    elif proto in {"slipstream", "aero-cl", "aerodrome-cl", "cl"}:
        built = build_slip_remove(
            token_a=token_a, token_b=token_b, fraction=fraction or 1,
            wallet=wallet, balances=balances,
        )
    else:
        built = build_remove_lp(
            token_a=token_a, token_b=token_b, fraction=fraction or 1,
            wallet=wallet, balances=balances,
        )
    return _set_action(built)


@tool
def list_lp_positions(stock_symbol: str = "") -> str:
    """List Aerodrome / Slipstream / Uniswap LP for stock paired with USDC, USDT, WETH, cbBTC, or WBTC."""
    wallet = _CTX.get("wallet")
    if not wallet:
        return "Connect a Base wallet to read LP balances."
    tokens = list_tokens(_DB)
    quotes = [t for t in tokens if t["symbol"] in QUOTE_SYMS]
    stocks = [t for t in tokens if t.get("kind") == "stock"] or [
        t for t in tokens if t["symbol"] not in QUOTE_SYMS and t.get("kind") != "native"
    ]
    if stock_symbol:
        match = _token(stock_symbol)
        stocks = [match] if match else [
            t for t in stocks if t["symbol"].upper().startswith(stock_symbol.upper()[:4])
        ]
    lines, seen = [], set()
    if not quotes:
        return "Quote tokens missing from the allowlist."
    for stock in stocks:
        if not stock:
            continue
        for quote in quotes:
            pool, stable = find_pool(stock["address"], quote["address"])
            if pool and pool.lower() not in seen:
                seen.add(pool.lower())
                raw = token_balance(pool, wallet) or 0
                if raw > 0:
                    lines.append(
                        f"Aerodrome {stock['symbol']}/{quote['symbol']} "
                        f"({'stable' if stable else 'volatile'}): {raw / 10**18:.8f} LP ({pool})"
                    )
        for pos in list_uni_positions(wallet, stock):
            q = pos.get("quote") or pos.get("token1") or "USDC"
            lines.append(
                f"Uniswap V3 {stock['symbol']}/{q} "
                f"NFT #{pos['tokenId']} fee {pos['fee'] / 10000:.2f}% "
                f"liquidity {pos['liquidity']}"
            )
        for pos in list_slip_positions(wallet, stock):
            q = pos.get("quote") or "USDC"
            lines.append(
                f"Slipstream {stock['symbol']}/{q} "
                f"NFT #{pos['tokenId']} tick {pos['tickSpacing']} "
                f"liquidity {pos['liquidity']}"
            )
    return "LP positions:\n" + "\n".join(lines) if lines else "No Aerodrome, Slipstream, or Uniswap V3 LP found."


@tool
def list_live_stock_pools(query: str = "") -> str:
    """Web-search DefiLlama, DexScreener, GeckoTerminal for live Base stock LP pairs."""
    if not os.getenv("TAVILY_API_KEY"):
        return "TAVILY_API_KEY missing."
    ticker = (query or "AAPL NVDA META GOOGL TSLA Coinbase tokenized stocks").strip()
    search = TavilySearch(max_results=6)
    questions = [
        f"site:defillama.com {ticker} Base Aerodrome Slipstream Uniswap pool USDC",
        f"site:dexscreener.com/base {ticker}c USDC OR WETH Base",
        f"site:geckoterminal.com/base {ticker} tokenized stock pool Base",
        f"Coinbase tokenized stocks {ticker} Base LP pools Aerodrome Uniswap 2026",
    ]
    chunks = []
    for q in questions:
        chunks.append(f"## {q}\n{agent_tools.tavily_search(search, q)}")
    return (
        "Live-web pool search (DefiLlama / DexScreener / Gecko / news). "
        "Treat addresses from those pages as source of truth.\n\n"
        + "\n\n".join(chunks)
    )


@tool
def aave_supply(symbol: str, amount: str = "", fraction: float = 0) -> str:
    """Supply USDC or WETH to Aave V3 on Base."""
    use_frac = fraction if (not amount or amount in {"0", "0.0"}) else None
    poor = _too_poor(symbol, amount, use_frac)
    if poor:
        return _set_action({"error": poor})
    return _set_action(
        build_aave_supply(
            token=_token(symbol) or {"symbol": symbol},
            amount=amount or None,
            fraction=fraction or None,
            wallet=_CTX.get("wallet"),
            balances=_CTX.get("balances"),
        )
    )


@tool
def aave_withdraw(symbol: str, amount: str = "", fraction: float = 1) -> str:
    """Withdraw USDC or WETH from Aave V3 on Base."""
    return _set_action(
        build_aave_withdraw(
            token=_token(symbol) or {"symbol": symbol},
            amount=amount or None,
            fraction=fraction or 1,
            wallet=_CTX.get("wallet"),
            balances=_CTX.get("balances"),
        )
    )


@tool
def aave_borrow(symbol: str, amount: str) -> str:
    """Borrow USDC or WETH from Aave V3. Requires collateral."""
    return _set_action(
        build_aave_borrow(
            token=_token(symbol) or {"symbol": symbol},
            amount=amount,
            fraction=None,
            wallet=_CTX.get("wallet"),
            balances=_CTX.get("balances"),
        )
    )


@tool
def aave_repay(symbol: str, amount: str = "", fraction: float = 1) -> str:
    """Repay USDC or WETH debt on Aave V3."""
    use_frac = fraction if (not amount or amount in {"0", "0.0"}) else None
    poor = _too_poor(symbol, amount, use_frac)
    if poor:
        return _set_action({"error": poor})
    return _set_action(
        build_aave_repay(
            token=_token(symbol) or {"symbol": symbol},
            amount=amount or None,
            fraction=fraction or 1,
            wallet=_CTX.get("wallet"),
            balances=_CTX.get("balances"),
        )
    )


@tool
def aave_set_collateral(symbol: str, enabled: bool = True) -> str:
    """Enable or disable USDC/WETH as Aave collateral."""
    return _set_action(
        build_aave_collateral(
            token=_token(symbol) or {"symbol": symbol},
            wallet=_CTX.get("wallet"),
            enabled=enabled,
        )
    )


@tool
def aave_account() -> str:
    """Show Aave V3 collateral, debt, available borrow, and health factor."""
    wallet = _CTX.get("wallet")
    if not wallet:
        return "Connect a Base wallet to read your Aave account."
    return describe_account(wallet)


@tool
def morpho_supply(symbol: str, amount: str = "", fraction: float = 0) -> str:
    """Supply WETH or USDC as Morpho Blue collateral on Base."""
    raw = (symbol or "").upper().replace(" ", "")
    if raw not in {"ETH", "ETHER", "WETH", "AWETH", "USDC", "AUSDC", "USD"}:
        return _set_action({"error": "Morpho on Stocktalk is WETH and USDC only."})
    use_frac = fraction if (not amount or amount in {"0", "0.0"}) else None
    tick = "WETH" if raw in {"ETH", "ETHER", "WETH", "AWETH"} else "USDC"
    poor = _too_poor(tick, amount, use_frac)
    if poor:
        return _set_action({"error": poor})
    return _set_action(
        build_morpho_supply(
            token=_token(tick) or {"symbol": tick},
            amount=amount or None,
            fraction=fraction or None,
            wallet=_CTX.get("wallet"),
            balances=_CTX.get("balances"),
        )
    )


@tool
def morpho_withdraw(symbol: str, amount: str = "", fraction: float = 1) -> str:
    """Withdraw WETH or USDC collateral from Morpho Blue."""
    return _set_action(
        build_morpho_withdraw(
            token=_token(symbol) or {"symbol": symbol},
            amount=amount or None,
            fraction=fraction or 1,
            wallet=_CTX.get("wallet"),
            balances=_CTX.get("balances"),
        )
    )


@tool
def morpho_borrow(symbol: str, amount: str) -> str:
    """Borrow USDC or WETH from Morpho Blue. Requires collateral in that market."""
    return _set_action(
        build_morpho_borrow(
            token=_token(symbol) or {"symbol": symbol},
            amount=amount,
            fraction=None,
            wallet=_CTX.get("wallet"),
            balances=_CTX.get("balances"),
        )
    )


@tool
def morpho_repay(symbol: str, amount: str = "", fraction: float = 1) -> str:
    """Repay USDC or WETH debt on Morpho Blue."""
    use_frac = fraction if (not amount or amount in {"0", "0.0"}) else None
    poor = _too_poor(symbol, amount, use_frac)
    if poor:
        return _set_action({"error": poor})
    return _set_action(
        build_morpho_repay(
            token=_token(symbol) or {"symbol": symbol},
            amount=amount or None,
            fraction=fraction or 1,
            wallet=_CTX.get("wallet"),
            balances=_CTX.get("balances"),
        )
    )


@tool
def morpho_account() -> str:
    """Show Morpho Blue WETH/USDC collateral and debt shares."""
    wallet = _CTX.get("wallet")
    if not wallet:
        return "Connect a Base wallet to read Morpho."
    return describe_morpho(wallet)


@tool
def web_search(query: str) -> str:
    """Search the web for news or explainers about tokenized stocks / Base DeFi."""
    if not os.getenv("TAVILY_API_KEY"):
        return "Web search is not configured."
    search = TavilySearch(max_results=5)
    return agent_tools.tavily_search(search, query)


client = MultiServerMCPClient({
    "external": {
        "url": "http://127.0.0.1:8000/mcp",
        "transport": "streamable_http"
    }
})
mcp_tools = asyncio.run(client.get_tools())

TOOLS = [
    list_allowlisted_tokens,
    list_protocol_addresses,
    list_routes,
    get_balances,
    quote_swap,
    add_liquidity,
    remove_liquidity,
    list_lp_positions,
    aave_supply,
    aave_withdraw,
    aave_borrow,
    aave_repay,
    aave_set_collateral,
    aave_account,
    morpho_supply,
    morpho_withdraw,
    morpho_borrow,
    morpho_repay,
    morpho_account,
    web_search,
    list_live_stock_pools
] + mcp_tools


def _bound_llm():
    global _llm, _groq_model_index
    if _llm is None:
        return None
    last = None
    while _groq_model_index < len(_GROQ_MODELS):
        try:
            return _llm.bind_tools(TOOLS)
        except Exception as exc:
            last = exc
            text = str(exc).lower()
            if "404" not in text and "does not exist" not in text:
                raise
            _groq_model_index += 1
            if _groq_model_index >= len(_GROQ_MODELS):
                break
            _llm = ChatGroq(model=_GROQ_MODELS[_groq_model_index], temperature=0)
    if last:
        raise last
    return None


async def llm_node(state: State):
    bound = _bound_llm()
    messages = [SystemMessage(content=SYSTEM), *state.get("messages")] or []
    if bound is None:
        return {"messages": [AIMessage(content="GROQ_API_KEY missing.")]}
    result = await bound.ainvoke(messages)
    return {"messages": [result]}


def build_graph():
    graph = StateGraph(State)
    graph.add_node("llm_node", llm_node)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.add_edge(START, "llm_node")
    graph.add_conditional_edges("llm_node", tools_condition)
    graph.add_edge("tools", "llm_node")
    return graph.compile(checkpointer=memory)


_GRAPH = None


async def run_agent(*, db, message: str, wallet: str | None, balances=None, thread_id: str | None = None, history=None) -> dict:
    global _GRAPH, _DB
    _DB = db
    _CTX["wallet"] = wallet
    _CTX["balances"] = agent_tools.normalize_balances(balances, db)
    _CTX["action"] = {"type": "none"}
    _CTX["quote"] = None
    if _GRAPH is None:
        _GRAPH = build_graph()

    prior = []
    for row in history or []:
        if isinstance(row, dict) and row.get("role") in {"user", "assistant"} and row.get("content"):
            prior.append({"role": row["role"], "content": row["content"]})
    prior.append(HumanMessage(content=message))

    result = await _GRAPH.ainvoke(
        {"messages": prior, "wallet": wallet},
        config={"configurable": {"thread_id": thread_id or "page-session"}},
    )
    last = ""
    for item in reversed(result.get("messages") or []):
        content = getattr(item, "content", None)
        if isinstance(content, str) and content.strip() and getattr(item, "type", "") != "tool":
            last = content
            break
        if isinstance(item, dict) and item.get("content") and item.get("role") != "tool":
            last = item["content"]
            break

    action = _CTX.get("action") or {"type": "none"}
    text = last or action.get("message") or action.get("summary") or "Try: swap $2 USD for AAPL."
    return {
        "message": text,
        "action": action,
        "quote": _CTX.get("quote"),
        "intent": {"action": action.get("kind") or action.get("type")},
        "thread_id": thread_id,
    }