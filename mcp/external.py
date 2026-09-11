import httpx
import asyncio
from mcp.server.fastmcp import FastMCP
from defillama_sdk import DefiLlama
from typing import Any

mcp = FastMCP("external")
client = DefiLlama()

STOCKS: dict[str, str] = {
    "AAPLc": "0xb200000000000000000000C2e324d24d7eEcd1fb",
    "AMZNc": "0xb200000000000000000000d9192b6B456483C2E8",
    "COINc": "0xb200000000000000000000c85a31389D71F3ecfb",
    "CRCLc": "0xB20000000000000000000019f6E7C675b73C2e4D",
    "GOOGLc": "0xb2000000000000000000002D0BA3164cc74f58B7",
    "INTCc": "0xB2000000000000000000004AFF16039bA04bdFBc",
    "METAc": "0xb2000000000000000000008bC8786B856E61707C",
    "MSFTc": "0xB200000000000000000000Ab99cFa739E253872B",
    "MSTRc": "0xb2000000000000000000004884b426556b92883d",
    "NVDAc": "0xb20000000000000000000078ee7ce2fE4908108C",
    "SNDKc": "0xb200000000000000000000397293Cb8cda9a10c5",
    "SPCXc": "0xb2000000000000000000007b9fcbd005511aCBd5",
    "TSLAc": "0xb2000000000000000000001e800a7f5189430cD0",
}

@mcp.tool()
def get_stock_data(
    ticker: str,
    url: str = "https://api.dexscreener.com/latest/dex/tokens/{address}",
    chain: str = "base",
    timeout: float = 15.0,
) -> dict[str, Any]:
    """
    Fetch stock price.
    args -> ticker: stock token ticker, e.g. Apple is AAPLc
    """

    address = STOCKS[ticker]

    request_url = url.format(address=address) if "{address}" in url else url
    try:
        with httpx.Client(timeout=timeout, headers={"User-Agent": "base-stock-prices/1.0"}) as client:
            resp = client.get(request_url)
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"DexScreener HTTP {e.response.status_code}: {e.response.reason_phrase}") from e
    except httpx.HTTPError as e:
        raise RuntimeError(f"DexScreener request failed: {e}") from e

    pairs = payload.get("pairs") or []
    chain_pairs = [
        p for p in pairs
        if str(p.get("chainId", "")).lower() in (chain.lower(), "8453")
    ]
    pool = max(
        chain_pairs or pairs,
        key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0),
        default=None,
    )
    if not pool:
        return {
            "address": address,
            "url": request_url,
            "price": None,
            "error": "no DexScreener pair",
        }

    liq = (pool.get("liquidity") or {}).get("usd")
    return {
        "address": address,
        "url": request_url,
        "onchain_symbol": (pool.get("baseToken") or {}).get("symbol"),
        "price": float(pool["priceUsd"]) if pool.get("priceUsd") is not None else None,
        "dex": pool.get("dexId"),
        "pair": pool.get("pairAddress"),
        "liquidity_usd": liq,
        "price_change_24h": (pool.get("priceChange") or {}).get("h24"),
        "volume_24h": (pool.get("volume") or {}).get("h24"),
        "source": "dexscreener",
    }

@mcp.tool()
def get_price(token_identifier=None, timestamp=None):
    """
    fetch current or historical token prices.
    args:
        token_identifier (str, required)
        Token ID in one of these formats:
            network:address — e.g. ethereum:0xdac17f958d2ee523a2206206994597c13d831ec7
            Use ethereum or solana as the network, followed by the token's contract/mint address on that chain.
            coingecko:name — e.g. coingecko:bitcoin
            Use coingecko plus the token's full CoinGecko slug.

        timestamp (int, optional)
        Unix timestamp for a historical price. Pass this only when requesting a past price; otherwise omit or set to None for the current price.
    """
    # return historical price
    if timestamp != None:
        return client.prices.getHistoricalPrices(
            timestamp,
            [token_identifier],
        )
    # return current price
    else:
        return client.prices.getCurrentPrices(
            [token_identifier]
        )

@mcp.tool()
def get_protocol_tvl(protocol_name: str):
    """
    fetch sorted protocol tvl(total value locked).
    protocol_name(str) is the full protocol name e.g "aave", "uniswap" etc
    """

    return client.tvl.getTvl(protocol_name)


# == NON CRYPTO TOOLS == #
@mcp.tool()
async def get_datetime():
    """
    fetch current time and date details.
    takes no arguments
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=60, headers=headers) as client:
        url = "https://timeapi.io/api/v1/time/current/zone?timeZone=UTC"

        date_time = await client.get(url=url)
        date_time.raise_for_status()

        return date_time.json()

@mcp.tool()
async def get_weather(city_name: str):
    """
    fetch current weather.
    takes one argument;
    city_name(str) is the name of the sorted city
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=60, headers=headers) as client:
        url = "https://wttr.in/{}".format(city_name)
        params = {"format": "j1"}

        response = await client.get(url=url, params=params)
        response.raise_for_status()

        return response.json()["current_condition"]


if __name__ == "__main__":
    mcp.run(transport="streamable-http")