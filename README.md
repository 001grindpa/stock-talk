# Stocktalk

Stocktalk is a non-custodial, natural-language DeFi assistant for official Coinbase Tokenized Stocks on Base (Chain ID `8453`). Users can request swaps, liquidity operations, Aave actions, portfolio information, and market research through chat. Transactions are prepared for review and signed in the user's wallet.

## Features

- Multi-route swaps across 1inch, KyberSwap, Odos, Aerodrome Slipstream, Aerodrome V2, and 0x.
- Aerodrome V2 and Slipstream liquidity management.
- Uniswap V3 concentrated-liquidity positions.
- Aave V3 supply, borrow, repay, withdraw, and collateral actions for USDC and WETH.
- Morpho Blue isolated-market supply, borrow, repay, withdraw, and account actions for WETH/USDC markets.
- Live market search through Tavily and optional external data through MCP.
- ENS and Basename resolution, wallet balances, trade history, and Basescan links.
- Client-side wallet signing with no private-key custody.
- Responsive light/dark chat interface with landing-page routing and pending prompt support.

## Supported Assets

The token registry includes USDC, USDT, WETH, WBTC and official Coinbase Tokenized Stocks such as AAPLc, NVDAc, METAc, GOOGLc, TSLAc, AMZNc, MSFTc, MSTRc, COINc, CRCLc, INTCc, SNDKc, and SPCXc. Lending integrations currently support USDC and WETH; tokenized stocks are not supported as Aave or Morpho collateral or debt assets.

## Architecture

- **Frontend:** Flask/Jinja templates, vanilla JavaScript, Ethers.js, and a custom responsive CSS theme.
- **Backend:** Flask REST endpoints in `app.py`.
- **Agent:** LangGraph and LangChain with an OpenRouter-hosted LLM, deterministic protocol tools, and optional MCP tools.
- **Protocol services:** Base RPC clients and transaction encoders under `services/`.
- **Persistence:** `stocks.db` stores completed trade history only. Token metadata is held in a thread-safe in-memory registry; chat context is not persisted in SQLite.

## Requirements

- Python 3.10 or later
- An injected EVM wallet configured for Base Mainnet
- Git

## Setup

```bash
git clone https://github.com/001grindpa/stock-talk.git
cd stock-talk
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Configure the required values in `.env`:

| Variable | Purpose | Required |
| --- | --- | --- |
| `OPENAI_API_KEY` | OpenRouter API key used for agent model access | Yes |
| `GROQ_API_KEY` | Legacy Groq configuration | No |
| `GROQ_MODEL` | Legacy model configuration | No |
| `BASE_RPC_URL` | Base JSON-RPC endpoint | Yes |
| `FLASK_SECRET_KEY` | Flask session signing | Yes |
| `TAVILY_API_KEY` | Web search | No |
| `ONEINCH_API_KEY` | 1inch quotes | No |
| `ZEROX_API_KEY` | 0x quotes | No |
| `DEMO_ALLOW_MOCK` | Enable demo fallback mode | No |

Start the application:

```bash
python app.py
```

Open `http://127.0.0.1:5000/`. The chat application is available at `/app`.

The optional MCP server can be started separately:

```bash
python mcp/external.py
```

## API Surface

- `GET /api/tokens` returns the supported token registry.
- `POST /api/chat` sends a message with a memory `thread_id` and returns the assistant response and any unsigned action.
- `POST /api/trades` records or updates a completed trade by transaction hash.
- `GET /api/trades?wallet=0x...` returns up to 50 trades for one wallet.

## Example Prompts

```text
swap $2 USD for AAPL
add LP to Aerodrome AAPL/USDC
mint Uniswap V3 position for NVDA/USDC
supply 5 USDC to Aave
supply 0.1 WETH as Morpho collateral
borrow 5 USDC from Morpho
check my balances on Base
what is the current price of Ethereum?
```

## Security

Stocktalk never requests or stores private keys or seed phrases. The server prepares transaction data; the connected wallet reviews and signs it. The application is intended for eligible non-US users interacting with Coinbase Tokenized Stocks on Base and is not financial, investment, or legal advice.

## License

MIT. See [LICENSE](LICENSE).
