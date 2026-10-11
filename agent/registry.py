"""Official Coinbase Tokenized Stocks on Base + stables + ETH/WETH + BTC wrappers + Coinbase wraps.

Addresses are hardcoded from Base documentation and seeded into SQLite.
Never invent a ticker or contract address.
https://docs.base.org/specifications/b20/tokenized-stocks-on-base
https://www.base.org/stocks
"""

from __future__ import annotations

import json

from sqlalchemy import func, select

from models import Token

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
        "aliases": ["WETH", "AWETH"],
    },
    {
        "symbol": "ETH",
        "name": "Ether",
        "address": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
        "decimals": 18,
        "kind": "native",
        "aliases": ["ETH", "BASE ETH", "NATIVE ETH", "GAS"],
    },
    {
        "symbol": "cbBTC",
        "name": "Coinbase Wrapped BTC",
        "address": "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf",
        "decimals": 8,
        "kind": "btc",
        "aliases": ["CBBTC", "BTC", "BITCOIN"],
    },
    {
        "symbol": "cbETH",
        "name": "Coinbase Wrapped Staked ETH",
        "address": "0x2Ae3F1Ec7F1F5012CFEab0185bfc7aa3cf0DEc22",
        "decimals": 18,
        "kind": "eth",
        "aliases": ["CBETH"],
    },
    {
        "symbol": "cbLTC",
        "name": "Coinbase Wrapped LTC",
        "address": "0xcb17C9Db87B595717C857a08468793f5bAb6445F",
        "decimals": 8,
        "kind": "other",
        "aliases": ["CBLTC"],
    },
    {
        "symbol": "cbADA",
        "name": "Coinbase Wrapped ADA",
        "address": "0xcbADA732173e39521CDBE8bf59a6Dc85A9fc7b8c",
        "decimals": 6,
        "kind": "other",
        "aliases": ["CBADA"],
    },
    {
        "symbol": "cbDOGE",
        "name": "Coinbase Wrapped DOGE",
        "address": "0xcbD06E5A2B0C65597161de254AA074E489dEb510",
        "decimals": 8,
        "kind": "other",
        "aliases": ["CBDOGE"],
    },
    {
        "symbol": "cbXRP",
        "name": "Coinbase Wrapped XRP",
        "address": "0xcb585250f852C6c6bf90434AB21A00f02833a4af",
        "decimals": 6,
        "kind": "other",
        "aliases": ["CBXRP"],
    },
    {
        "symbol": "cbMEGA",
        "name": "Coinbase Wrapped MEGA",
        "address": "0xcb111E6A2a3bde90856D299d61341ac302167D23",
        "decimals": 18,
        "kind": "other",
        "aliases": ["CBMEGA"],
    },
    {
        "symbol": "cbHYPE",
        "name": "Coinbase Wrapped HYPE",
        "address": "0xB200000000000000000000451d033a5000cb479e",
        "decimals": 18,
        "kind": "other",
        "aliases": ["CBHYPE"],
    },
    {
        "symbol": "cbZEC",
        "name": "Coinbase Wrapped ZEC",
        "address": "0xB2000000000000000000008501b13360000cb2EC",
        "decimals": 8,
        "kind": "other",
        "aliases": ["CBZEC"],
    },
    {
        "symbol": "WBTC",
        "name": "Wrapped Bitcoin",
        "address": "0x0555e30da8f98308EdB960aa94C0Db47230d2b9c",
        "decimals": 8,
        "kind": "btc",
        "aliases": ["WBTC"],
    },
    {
        "symbol": "USDT",
        "name": "Tether USD",
        "address": "0xfde4C96c8593536E31F229EA8f37b2ADa2699bb2",
        "decimals": 6,
        "kind": "stable",
        "aliases": ["USDT", "TETHER"],
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
    """Insert missing official tokens and refresh their decimal metadata."""
    existing = {
        (row.address or "").lower(): row
        for row in db.scalars(select(Token)).all()
    }
    changed = False
    for token in OFFICIAL_TOKENS:
        row = existing.get(token["address"].lower())
        if row is None:
            db.add(
                Token(
                    symbol=token["symbol"],
                    name=token["name"],
                    address=token["address"],
                    decimals=token["decimals"],
                    kind=token["kind"],
                    aliases=json.dumps(token["aliases"]),
                )
            )
            changed = True
            continue
        if row.decimals != token["decimals"]:
            row.decimals = token["decimals"]
            changed = True
    if changed:
        db.commit()


def list_tokens(db) -> list[dict]:
    rows = db.scalars(select(Token).order_by(Token.kind.desc(), Token.symbol)).all()
    out = []
    for token in rows:
        item = {
            "symbol": token.symbol,
            "name": token.name,
            "address": token.address,
            "decimals": token.decimals,
            "kind": token.kind,
            "aliases": token.aliases,
        }
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
    # light aliases that are not already on the token rows
    if needle in {"USD", "DOLLAR", "DOLLARS", "US DOLLAR", "AUSDC"}:
        needle = "USDC"
    if needle in {"AWETH"}:
        needle = "WETH"
    if needle in {"ETHER"}:
        needle = "ETH"
    if needle in {"BTC", "BITCOIN"}:
        needle = "CBBTC"
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