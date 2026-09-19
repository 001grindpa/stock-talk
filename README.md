# Stocktalk

Stocktalk is a non-custodial, natural-language DeFi assistant for official Coinbase Tokenized Stocks and other allowlisted assets on Base (Chain ID `8453`). Users can request swaps, liquidity operations, Aave and Morpho actions, portfolio information, and market research through chat. Transactions are prepared for review and signed in the user's wallet.

## Features

- Multi-route swap planning across 1inch, KyberSwap, Odos, Aerodrome Slipstream, Aerodrome V2, and 0x when the relevant providers are available.
- Liquidity management for Aerodrome V2, Slipstream, and Uniswap V3 positions.
- Aave V3 actions for USDC and WETH supply, borrow, repay, and withdraw flows.
- Morpho Blue supply, borrow, repay, withdraw, and account actions for its configured Base markets.
- Wallet and balance checks, DeFi position lookup, token registry lookup, transaction history, and Basescan links.
- Tavily web search, live pool discovery, and external MCP tools for market data, protocol TVL, date, and weather.
- Flask and Jinja frontend with a landing page and an in-app chat route.

## Supported Assets

The in-memory token registry includes USDC, USDT, WETH, native ETH, cbBTC, WBTC, and the official Coinbase Tokenized Stocks AAPLc, NVDAc, METAc, GOOGLc, TSLAc, AMZNc, MSFTc, MSTRc, COINc, CRCLc, INTCc, SNDKc, and SPCXc. Swaps support the listed assets. LP quote tokens are USDC, USDT, WETH, cbBTC, and WBTC; native ETH is not an LP token. Aave supports USDC and WETH, while Morpho uses its configured isolated markets.

## Architecture

- Frontend: Flask templates, vanilla JavaScript, Ethers.js, and responsive CSS.
- Backend: Flask app and REST endpoints in `app.py`.
- Agent: LangGraph and LangChain orchestration with an OpenRouter-backed model, deterministic protocol tools, and MCP tools.
- Protocol services: Base RPC and transaction-building helpers under `services/`.
- Persistence: `stocks.db` stores completed trade history; token metadata is kept in a thread-safe in-memory registry; agent memory is process-local and is not persisted in SQLite.

## Requirements

- Python 3.10 or later
- An injected EVM wallet on Base Mainnet for signing transactions
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
| `BASE_RPC_URL` | Base JSON-RPC endpoint used for onchain reads | No; defaults to `https://mainnet.base.org` |
| `FLASK_SECRET_KEY` | Flask session signing key | Yes |
| `TAVILY_API_KEY` | Web search / market research | No |
| `ONEINCH_API_KEY` | 1inch quote support | No |
| `ZEROX_API_KEY` | 0x quote support | No |
| `DEMO_ALLOW_MOCK` | Enables demo/mock mode in the UI | No |

The app reads these values from the environment when it starts, so they should be set in `.env` before launching. `OPENAI_API_KEY` is used with OpenRouter for the primary agent model. Groq settings are used only by the model fallback path.

## Running the app

```bash
python mcp/external.py
```

In another terminal, start the Flask app:

```bash
python app.py
```

The app also supports:

```bash
flask run
```

The MCP service listens on `http://127.0.0.1:8000/mcp` and is loaded by the agent during startup. Open `http://127.0.0.1:5000/` in the browser. The chat UI is available at `/app`.

## API Surface

- `GET /api/tokens` returns the supported token registry.
- `POST /api/chat` accepts a message, optional wallet address, optional balances, and a `thread_id`; it returns the assistant response plus any unsigned action payload.
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
