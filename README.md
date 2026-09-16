# Stocktalk

Stocktalk is a non-custodial, natural-language DeFi assistant for official Coinbase Tokenized Stocks on Base (Chain ID 8453). Users can request swaps, liquidity operations, Aave and Morpho actions, portfolio information, and market research through chat. Transactions are prepared for review and signed in the user's wallet.

## Features

- Multi-route swap planning across 1inch, KyberSwap, Odos, Aerodrome, Slipstream, and 0x when the relevant keys and market data are available.
- Liquidity management for Aerodrome V2, Slipstream, and Uniswap V3 positions.
- Aave V3 actions for USDC and WETH supply, borrow, repay, and withdraw flows.
- Morpho Blue actions for isolated WETH and USDC markets.
- Wallet and balance checks, token registry lookup, transaction history, and Basescan links.
- Live search via Tavily and optional external MCP integrations.
- Lightweight Flask + Jinja frontend with a landing page and an in-app chat route.

## Supported Assets

The in-memory token registry includes USDC, USDT, WETH, WBTC, cbBTC, and official Coinbase Tokenized Stocks such as AAPLc, NVDAc, METAc, GOOGLc, TSLAc, AMZNc, MSFTc, MSTRc, COINc, CRCLc, INTCc, SNDKc, and SPCXc. Lending support is currently limited to USDC and WETH for Aave and Morpho market actions.

## Architecture

- Frontend: Flask templates, vanilla JavaScript, and a responsive CSS theme.
- Backend: Flask app and REST endpoints in `app.py`.
- Agent: LangGraph and LangChain orchestration with an OpenRouter-backed LLM and deterministic protocol tools.
- Protocol services: Base RPC and transaction-building helpers under `services/`.
- Persistence: `stocks.db` stores completed trade history; token metadata is kept in a thread-safe in-memory registry; chat context is not persisted in SQLite.

## Requirements

- Python 3.10 or later
- An injected EVM wallet on Base Mainnet
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

Configure the values in `.env`:

| Variable | Purpose | Required |
| --- | --- | --- |
| `OPENAI_API_KEY` | OpenRouter API key used by the agent model layer | Yes |
| `GROQ_API_KEY` | Legacy Groq access key | No |
| `GROQ_MODEL` | Legacy Groq model selection | No |
| `BASE_RPC_URL` | Base JSON-RPC endpoint used for onchain reads | No, defaults to `https://mainnet.base.org` |
| `FLASK_SECRET_KEY` | Flask session signing key | Yes |
| `TAVILY_API_KEY` | Web search / market research | No |
| `ONEINCH_API_KEY` | 1inch quote support | No |
| `ZEROX_API_KEY` | 0x quote support | No |
| `DEMO_ALLOW_MOCK` | Enables demo/mock mode in the UI | No |

The app reads these values from the environment when it starts, so they should be set in `.env` before launching.

## Running the app

```bash
python app.py
```

The app also supports:

```bash
flask run
```

Open `http://127.0.0.1:5000/` in the browser. The chat UI is available at `/app`.

The optional MCP server can be started separately:

```bash
python mcp/external.py
```

## API Surface

- `GET /api/tokens` returns the supported token registry.
- `POST /api/chat` sends a message and returns the assistant response plus any unsigned action payload.
- `POST /api/trades` records or updates a completed trade by transaction hash.
- `GET /api/trades?wallet=0x...` returns up to 50 trades for a wallet.

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

Stocktalk never requests or stores private keys or seed phrases. The server prepares transaction data and the connected wallet reviews and signs it. The application is intended for eligible non-US users interacting with Coinbase Tokenized Stocks on Base and is not financial, investment, or legal advice.

## License

MIT. See [LICENSE](LICENSE).
