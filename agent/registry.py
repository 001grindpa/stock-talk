"""Official Coinbase Tokenized Stocks on Base + USDC + WETH.

Addresses are hardcoded from Base documentation and seeded into SQLite.
Never invent a ticker or contract address.
https://docs.base.org/specifications/b20/tokenized-stocks-on-base
https://www.base.org/stocks
"""

from __future__ import annotations

import json

# Source of truth: Base B20 tokenized stocks contract table (docs.base.org).
# USDC is the native USDC on Base, not a tokenized equity.
OFFICIAL_TOKENS = [
    {
        "symbol": "USDC",
        "name": "USD Coin",
        "address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "decimals": 6,
        "kind": "stable",
        "aliases": ["USDC", "USD", "DOLLAR", "DOLLARS", "US DOLLAR", "$", "AUSDC"],
    },
    {
        "symbol": "WETH",
        "name": "Wrapped Ether",
        "address": "0x4200000000000000000000000000000000000006",
        "decimals": 18,
        "kind": "gas",
        "aliases": ["WETH", "ETH", "ETHER", "AWETH"],
    },
    {
        "symbol": "AAPLc",
        "name": "Apple",
        "address": "0xb200000000000000000000C2e324d24d7eEcd1fb",
        "decimals": 8,
        "kind": "stock",
        "aliases": ["AAPLC", "AAPL", "APPLE"],
    },
    {
        "symbol": "NVDAc",
        "name": "NVIDIA",
        "address": "0xb20000000000000000000078ee7ce2fE4908108C",
        "decimals": 8,
        "kind": "stock",
        "aliases": ["NVDAC", "NVDA", "NVIDIA"],
    },
    {
        "symbol": "METAc",
        "name": "Meta",
        "address": "0xb2000000000000000000008bC8786B856E61707C",
        "decimals": 8,
        "kind": "stock",
        "aliases": ["METAC", "META", "FACEBOOK", "FB"],
    },
    {
        "symbol": "GOOGLc",
        "name": "Alphabet",
        "address": "0xb2000000000000000000002D0BA3164cc74f58B7",
        "decimals": 8,
        "kind": "stock",
        "aliases": ["GOOGLC", "GOOGL", "GOOG", "GOOGLE", "ALPHABET"],
    },
    {
        "symbol": "TSLAc",
        "name": "Tesla",
        "address": "0xb2000000000000000000001e800a7f5189430cD0",
        "decimals": 8,
        "kind": "stock",
        "aliases": ["TSLAC", "TSLA", "TESLA"],
    },
    {
        "symbol": "AMZNc",
        "name": "Amazon",
        "address": "0xb200000000000000000000d9192b6B456483C2E8",
        "decimals": 8,
        "kind": "stock",
        "aliases": ["AMZNC", "AMZN", "AMAZON"],
    },
    {
        "symbol": "MSFTc",
        "name": "Microsoft",
        "address": "0xB200000000000000000000Ab99cFa739E253872B",
        "decimals": 8,
        "kind": "stock",
        "aliases": ["MSFTC", "MSFT", "MICROSOFT"],
    },
    {
        "symbol": "MSTRc",
        "name": "MicroStrategy",
        "address": "0xb2000000000000000000004884b426556b92883d",
        "decimals": 8,
        "kind": "stock",
        "aliases": ["MSTRC", "MSTR", "MICROSTRATEGY", "STRATEGY"],
    },
    {
        "symbol": "COINc",
        "name": "Coinbase",
        "address": "0xb200000000000000000000c85a31389D71F3ecfb",
        "decimals": 8,
        "kind": "stock",
        "aliases": ["COINC", "COIN", "COINBASE"],
    },
    {
        "symbol": "CRCLc",
        "name": "Circle",
        "address": "0xB20000000000000000000019f6E7C675b73C2e4D",
        "decimals": 8,
        "kind": "stock",
        "aliases": ["CRCLC", "CRCL", "CIRCLE"],
    },
    {
        "symbol": "INTCc",
        "name": "Intel",
        "address": "0xB2000000000000000000004AFF16039bA04bdFBc",
        "decimals": 8,
        "kind": "stock",
        "aliases": ["INTCC", "INTC", "INTEL"],
    },
    {
        "symbol": "SNDKc",
        "name": "SanDisk",
        "address": "0xb200000000000000000000397293Cb8cda9a10c5",
        "decimals": 8,
        "kind": "stock",
        "aliases": ["SNDKC", "SNDK", "SANDISK"],
    },
    {
        "symbol": "SPCXc",
        "name": "SpaceX",
        "address": "0xb2000000000000000000007b9fcbd005511aCBd5",
        "decimals": 8,
        "kind": "stock",
        "aliases": ["SPCXC", "SPCX", "SPACEX"],
    },
]

CHAIN_ID = 8453
MAX_DEMO_USD = 50.0


def seed_tokens(db) -> None:
    existing = db.execute("SELECT COUNT(*) AS n FROM tokens")[0]["n"]
    if existing:
        return
    for token in OFFICIAL_TOKENS:
        db.execute(
            "INSERT INTO tokens (symbol, name, address, decimals, kind, aliases) VALUES (?, ?, ?, ?, ?, ?)",
            token["symbol"],
            token["name"],
            token["address"],
            token["decimals"],
            token["kind"],
            json.dumps(token["aliases"]),
        )


def list_tokens(db) -> list[dict]:
    rows = db.execute(
        "SELECT symbol, name, address, decimals, kind, aliases FROM tokens ORDER BY kind DESC, symbol"
    )
    out = []
    for row in rows:
        item = dict(row)
        try:
            item["aliases"] = json.loads(item["aliases"])
        except (TypeError, json.JSONDecodeError):
            item["aliases"] = []
        out.append(item)
    return out


def _normalize(symbol: str | None) -> str:
    if not symbol:
        return ""
    text = str(symbol).strip().upper()
    if text.startswith("$"):
        text = text[1:]
    return text.replace(".", "")


def resolve_ticker(db, symbol: str | None) -> dict | None:
    """Map a user ticker or name to an allowlisted token. Returns None if unknown."""
    needle = _normalize(symbol)
    if not needle:
        return None
    if needle in {"USD", "DOLLAR", "DOLLARS", "US DOLLAR", "AUSDC"}:
        needle = "USDC"
    if needle in {"ETH", "ETHER", "AWETH"}:
        needle = "WETH"
    tokens = list_tokens(db)
    for token in tokens:
        aliases = {_normalize(a) for a in token.get("aliases") or []}
        aliases.add(_normalize(token["symbol"]))
        aliases.add(_normalize(token["name"]))
        if needle in aliases:
            return {
                "symbol": token["symbol"],
                "name": token["name"],
                "address": token["address"],
                "decimals": int(token["decimals"]),
                "kind": token["kind"],
            }
    return None