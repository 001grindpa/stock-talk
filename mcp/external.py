import httpx
import asyncio
from mcp.server.fastmcp import FastMCP
from defillama_sdk import DefiLlama
from typing import Any

mcp = FastMCP("external")
client = DefiLlama()

STOCKS: dict[str, str] = {
    "AAPL": "0xb200000000000000000000C2e324d24d7eEcd1fb",
    "AMZN": "0xb200000000000000000000d9192b6B456483C2E8",
    "COIN": "0xb200000000000000000000c85a31389D71F3ecfb",
    "CRCL": "0xB20000000000000000000019f6E7C675b73C2e4D",
    "GOOGL": "0xb2000000000000000000002D0BA3164cc74f58B7",
    "INTC": "0xB2000000000000000000004AFF16039bA04bdFBc",
    "META": "0xb2000000000000000000008bC8786B856E61707C",
    "MSFT": "0xB200000000000000000000Ab99cFa739E253872B",
    "MSTR": "0xb2000000000000000000004884b426556b92883d",
    "NVDA": "0xb20000000000000000000078ee7ce2fE4908108C",
    "SNDK": "0xb200000000000000000000397293Cb8cda9a10c5",
    "SPCX": "0xb2000000000000000000007b9fcbd005511aCBd5",
    "TSLA": "0xb2000000000000000000001e800a7f5189430cD0",
}

@mcp.tool()
def get_stock_data(
    ticker: str,
    url: str = "https://coins.llama.fi/prices/current/{coins}",
    chain: str = "base",
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Fetch stock price.
    args -> ticker: stock token ticker, e.g. Apple is AAPL
    """

    address = STOCKS[ticker]

    coin = f"{chain}:{address}"
    request_url = url.format(coins=coin) if "{coins}" in url else url
    try:
        with httpx.Client(timeout=timeout, headers={"User-Agent": "base-stock-prices/1.0"}) as client:
            resp = client.get(request_url)
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"DefiLlama HTTP {e.response.status_code}: {e.response.reason_phrase}") from e
    except httpx.HTTPError as e:
        raise RuntimeError(f"DefiLlama request failed: {e}") from e

    coins_data = payload.get("coins") or {}
    row = coins_data.get(coin) or coins_data.get(f"{chain}:{address.lower()}")
    if not row:
        row = next(
            (v for k, v in coins_data.items() if k.lower() == coin.lower()),
            None,
        )
    if not row:
        return {
            "address": address,
            "url": request_url,
            "price": None,
            "error": "no price from DefiLlama",
        }
    return {
        "address": address,
        "url": request_url,
        "onchain_symbol": row.get("symbol"),
        "price": row.get("price"),
        "decimals": row.get("decimals"),
        "timestamp": row.get("timestamp"),
        "confidence": row.get("confidence"),
        "source": "coins.llama.fi",
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