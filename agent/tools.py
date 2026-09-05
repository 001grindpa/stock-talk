"""Deterministic tools. Token addresses never come from the LLM or Tavily."""

from __future__ import annotations

from agent.registry import resolve_ticker as registry_resolve
from services.quotes import get_quote as fetch_quote


def resolve_ticker(db, symbol: str | None) -> dict | None:
    return registry_resolve(db, symbol)


def get_quote(*, from_token: dict, to_token: dict, amount: str, wallet: str | None) -> dict:
    return fetch_quote(
        from_token=from_token,
        to_token=to_token,
        amount=amount,
        wallet=wallet,
    )


def normalize_balances(raw, db) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out = []
    seen = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        token = registry_resolve(db, item.get("symbol"))
        if not token:
            continue
        addr = (item.get("address") or token["address"]).lower()
        if addr != token["address"].lower():
            continue
        if token["symbol"] in seen:
            continue
        seen.add(token["symbol"])
        out.append(
            {
                "symbol": token["symbol"],
                "address": token["address"],
                "decimals": token["decimals"],
                "raw": str(item.get("raw") or "0"),
                "formatted": str(item.get("formatted") if item.get("formatted") is not None else "0"),
            }
        )
    return out


def tavily_search(web_search, query: str) -> str:
    if web_search is None:
        return ""
    try:
        raw = web_search.invoke({"query": query})
    except Exception as exc:
        return f"(search unavailable: {exc})"
    if isinstance(raw, str):
        return raw[:4000]
    if isinstance(raw, dict):
        results = raw.get("results") or raw.get("content") or raw
        return str(results)[:4000]
    if isinstance(raw, list):
        lines = []
        for item in raw[:5]:
            if isinstance(item, dict):
                title = item.get("title") or ""
                url = item.get("url") or ""
                content = item.get("content") or item.get("snippet") or ""
                lines.append(f"{title} {url} {content}".strip())
            else:
                lines.append(str(item))
        return "\n".join(lines)[:4000]
    return str(raw)[:4000]