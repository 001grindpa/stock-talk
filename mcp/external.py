import httpx
import asyncio
from mcp.server.fastmcp import FastMCP
from defillama_sdk import DefiLlama

mcp = FastMCP("external")
client = DefiLlama()

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