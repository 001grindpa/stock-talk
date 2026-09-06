# Stocktalk 📈🤖

> **Natural-Language Assistant for Coinbase Tokenized Stocks on Base**

Stocktalk is a non-custodial, AI-powered DeFi assistant built for the **Base** ecosystem (Chain ID `8453`). It empowers users to execute token swaps, manage concentrated and classic liquidity pools, and interact with money markets for official Coinbase Tokenized Equities (such as **AAPL**, **TSLA**, **NVDA**, **GOOGL**, **MSFT**, and **COIN**) using intuitive, natural-language prompts.

---

## 🌟 Key Features

- ⚡ **Multi-Route DEX Swaps**: Seamlessly swap between USDC and official Base B20 tokenized stocks with intelligent multi-aggregator fallback:
  $$\text{1inch} \longrightarrow \text{KyberSwap} \longrightarrow \text{Odos} \longrightarrow \text{Aerodrome Slipstream (CL)} \longrightarrow \text{Aerodrome V2} \longrightarrow \text{0x API}$$
- 🌊 **Aerodrome V2 & Slipstream (CL) Liquidity**:
  - **Aerodrome V2**: Add and remove liquidity for classic volatile and stable pools (ERC-20 LP tokens).
  - **Aerodrome Slipstream (CL)**: Mint concentrated liquidity positions, track LP NFTs across multiple factory generations, and execute multicall decreases and burns.
- 🎯 **Uniswap V3 Positions**: Mint full-range concentrated liquidity positions, track LP NFTs, and collect/burn positions.
- 🏦 **Aave V3 Lending & Borrowing**: Supply, withdraw, borrow, repay, and toggle collateral for USDC and WETH on Base with automated health factor calculations. *(Note: Tokenized stocks are strictly non-borrowable/non-collateral on Aave).*
- 🔌 **Model Context Protocol (MCP) Integration**: Built-in FastMCP server (`mcp/external.py`) integrated via `langchain-mcp-adapters` providing external market data (DefiLlama token prices and protocol TVL), time services, and live weather.
- 🔍 **Real-Time Market Search**: Integrated Tavily search capabilities to fetch up-to-date market intelligence and tokenized stock news.
- 🔒 **100% Non-Custodial & Deterministic**: The assistant prepares explicit, unsigned transactions client-side for user verification and signing via injected Web3 wallets (MetaMask, Coinbase Wallet, etc.). All contract addresses are hardcoded to official Base deployments—the AI never hallucinates addresses or executes transactions.
- 🌐 **Web3 Identity & Responsive UX**: Full ENS (`.eth`) and Basename (`.base.eth`) resolution, automatic wallet balance detection, and dark/light mode toggle with persistent local storage.

---

## 📊 Supported Tokens on Base (B20 Specification)

Stocktalk uses official Coinbase Tokenized Stocks deployed on Base (Chain ID `8453`) along with native USDC and WETH:

| Token Symbol | Asset Name | Decimals | Contract Address | Kind |
| :--- | :--- | :---: | :--- | :--- |
| **USDC** | USD Coin | 6 | `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` | Stablecoin |
| **AAPLc** | Apple Inc. | 18 | `0xb200000000000000000000C2e324d24d7eEcd1fb` | Tokenized Stock |
| **NVDAc** | NVIDIA Corporation | 18 | `0xb20000000000000000000078ee7ce2fE4908108C` | Tokenized Stock |
| **METAc** | Meta Platforms Inc. | 18 | `0xb2000000000000000000008bC8786B856E61707C` | Tokenized Stock |
| **GOOGLc** | Alphabet Inc. | 18 | `0xb2000000000000000000002D0BA3164cc74f58B7` | Tokenized Stock |
| **TSLAc** | Tesla Inc. | 18 | `0xb2000000000000000000001e800a7f5189430cD0` | Tokenized Stock |
| **AMZNc** | Amazon.com Inc. | 18 | `0xb200000000000000000000d9192b6B456483C2E8` | Tokenized Stock |
| **MSFTc** | Microsoft Corporation | 18 | `0xB200000000000000000000Ab99cFa739E253872B` | Tokenized Stock |
| **MSTRc** | MicroStrategy Inc. | 18 | `0xb2000000000000000000004884b426556b92883d` | Tokenized Stock |
| **COINc** | Coinbase Global Inc. | 18 | `0xb200000000000000000000c85a31389D71F3ecfb` | Tokenized Stock |
| **CRCLc** | Circle Internet Financial | 18 | `0xB20000000000000000000019f6E7C675b73C2e4D` | Tokenized Stock |
| **INTCc** | Intel Corporation | 18 | `0xB2000000000000000000004AFF16039bA04bdFBc` | Tokenized Stock |
| **SNDKc** | SanDisk | 18 | `0xb200000000000000000000397293Cb8cda9a10c5` | Tokenized Stock |
| **SPCXc** | SpaceX | 18 | `0xb2000000000000000000007b9fcbd005511aCBd5` | Tokenized Stock |
| **WETH** | Wrapped Ether | 18 | `0x4200000000000000000000000000000000000006` | Base Asset |

---

## 🛠️ Architecture & Tech Stack

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Client Browser                                │
│   Landing Page (/) │ Web App (/app) │ Ethers.js (v6) │ Non-Custodial UI │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ JSON REST API
┌────────────────────────────────────▼────────────────────────────────────┐
│                         Flask Backend (app.py)                          │
│         SQLite Session Storage (stocks.db) │ SQLite Token Registry      │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────────┐
│                    LangGraph Workflow Engine (agent/)                   │
│   • Intent Extraction & Dialogue Memory (ChatGroq / LLaMA-3.3-70B)      │
│   • Built-in Deterministic Execution Tools                              │
│   • MultiServerMCPClient (FastMCP Server Adapter)                       │
└──────────┬─────────────────────────┬───────────────────────┬────────────┘
           │                         │                       │
           ▼                         ▼                       ▼
┌────────────────────┐    ┌─────────────────────┐    ┌────────────────────┐
│  Swap Aggregators  │    │ Protocols & Pools   │    │  MCP Tools Server  │
│  • 1inch API       │    │ • Aerodrome V2      │    │  • DefiLlama Price │
│  • KyberSwap API   │    │ • Slipstream (CL)   │    │  • DefiLlama TVL   │
│  • Odos API        │    │ • Uniswap V3 (NPM)  │    │  • TimeAPI UTC     │
│  • 0x Swap API     │    │ • Aave V3 Pool      │    │  • Wttr.in Weather │
└────────────────────┘    └─────────────────────┘    └────────────────────┘
```

- **Frontend**: Flask Jinja2 templates (`landing.html`, `index.html`, `base.html`), custom CSS design system (`style.css`), and Vanilla JavaScript (`app.js`).
- **Web3 Integration**: Ethers.js (v6) for wallet connection, Basename/ENS resolution, balance checks, and client-side transaction signing.
- **Backend**: Flask with SQLite database (`stocks.db`) for user management, message history, and quote tracking.
- **AI Agent Framework**: LangChain & LangGraph with Groq LLM (`llama-3.3-70b-versatile`), memory checkpointer (`MemorySaver`), and custom tool nodes.
- **MCP Integration**: FastMCP server (`mcp/external.py`) connected dynamically via `langchain-mcp-adapters`.
- **DEX & DeFi Routing**: Direct RPC multicall queries, Slipstream quoter/factory encoders, Uniswap V3 NPM helpers, Aave V3 Pool contract encoding, and 1inch/Kyber/Odos/0x API integrations.

---

## 🤖 Agent Tools & Capabilities

The LangGraph agent is equipped with deterministic tools:

### Built-in Core Tools
- `quote_swap`: Generates unsigned swap transactions comparing 1inch, Kyber, Odos, Slipstream CL, Aerodrome V2, and 0x.
- `add_liquidity`: Prepares LP add transactions for Aerodrome V2, Slipstream CL, or Uniswap V3.
- `remove_liquidity`: Prepares LP decrease/burn/collect transactions for Aerodrome V2, Slipstream CL, or Uniswap V3.
- `list_lp_positions`: Scans and reports open LP positions across Aerodrome V2, Slipstream CL, and Uniswap V3 for the connected wallet.
- `get_balances`: Queries live on-chain balances for allowlisted tokens.
- `aave_supply`, `aave_withdraw`, `aave_borrow`, `aave_repay`, `aave_set_collateral`: Prepares non-custodial transactions for Aave V3 Base markets (USDC/WETH).
- `aave_account`: Fetches user collateral, debt balance, available borrow, and liquidation health factor.
- `list_allowlisted_tokens`: Lists supported Base B20 tokens and rules.
- `list_routes`: Displays supported DEX and lending routing venues.
- `list_protocol_addresses`: Returns verified contract addresses on Base.
- `web_search`: Searches real-time web context via Tavily.

### MCP Tools (via FastMCP)
- `get_price`: Fetches current or historical token prices via DefiLlama SDK.
- `get_protocol_tvl`: Fetches total value locked (TVL) for any DeFi protocol via DefiLlama SDK.
- `get_datetime`: Retrieves current UTC time and date details.
- `get_weather`: Retrieves live weather conditions for a given city.

---

## 📋 Prerequisites

- **Python**: 3.10 or higher
- **Git**
- **Web3 Wallet**: MetaMask, Coinbase Wallet, Rainbow, or any injected EVM browser wallet configured for **Base Mainnet (Chain ID `8453`)**.

---

## ⚙️ Environment Configuration (`.env`)

Copy the template environment file to create your local `.env`:

```bash
cp .env.example .env
```

### Environment Variables Breakdown

| Variable | Description | Default / Example | Required |
| :--- | :--- | :--- | :---: |
| `GROQ_API_KEY` | API Key from [Groq Console](https://console.groq.com/) for the agent LLM | `gsk_...` | **Yes** |
| `GROQ_MODEL` | Primary Groq LLM model name | `llama-3.3-70b-versatile` | Yes |
| `BASE_RPC_URL` | Base Mainnet RPC endpoint | `https://mainnet.base.org` | Yes |
| `FLASK_SECRET_KEY` | Secret key for Flask session security | `change-me-to-a-secure-key` | Yes |
| `TAVILY_API_KEY` | [Tavily](https://tavily.com/) API Key for real-time web search | `tvly-...` | Optional |
| `ONEINCH_API_KEY` | [1inch Developer API](https://1inch.dev/) Key for swap quotes | `1inch_...` | Optional |
| `ZEROX_API_KEY` | [0x API](https://0x.org/) Key for swap quotes | `0x_...` | Optional |
| `DEMO_ALLOW_MOCK` | Enable fallback mock mode if all live DEX routes miss (`1` or `0`) | `0` | No |

---

## 🚀 Local Setup & Installation

### 1. Clone the Repository

```bash
git clone https://github.com/001grindpa/stock-talk.git
cd stock-talk
```

### 2. Create and Activate a Virtual Environment

**On Linux / macOS / WSL:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**On Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
cp .env.example .env
```
Edit `.env` and add your `GROQ_API_KEY` along with any optional keys (`TAVILY_API_KEY`, `ONEINCH_API_KEY`, `ZEROX_API_KEY`).

### 5. (Optional) Run the FastMCP Server

If you want to use the external MCP tools (DefiLlama prices/TVL, weather, UTC time):

```bash
python mcp/external.py
```
*The MCP server runs at `http://127.0.0.1:8000/mcp` with streamable HTTP transport.*

### 6. Launch the Stocktalk Application

Run the Flask application:

```bash
python app.py
```

The SQLite database (`stocks.db`) will automatically initialize and seed official token entries on startup.

### 7. Access the Application

Open your browser and navigate to:
- **Landing Page**: [http://127.0.0.1:5000/](http://127.0.0.1:5000/)
- **Chat App**: [http://127.0.0.1:5000/app](http://127.0.0.1:5000/app)

---

## 💬 Example Prompts

Once inside the app (`/app`), interact with the assistant using natural-language requests:

### ⚡ Swaps
- *`swap $2 USD for AAPL`*
- *`swap 0.5 TSLA for USDC`*
- *`swap 10 USDC to NVDA`*

### 🌊 Liquidity Pools
- *`add LP to Aerodrome AAPL/USDC pool`*
- *`add liquidity to Slipstream NVDA/USDC`*
- *`mint Uniswap V3 position for GOOGL/USDC`*
- *`list my LP positions`*
- *`remove 50% of my Slipstream AAPL LP`*

### 🏦 Aave V3 Lending & Money Markets
- *`supply 5 USDC to Aave`*
- *`check my Aave account health`*
- *`borrow 2 USDC on Aave`*
- *`repay 2 USDC on Aave`*

### 📊 Portfolio & Market Information
- *`check my balances on Base`*
- *`what tokens are supported?`*
- *`what is the current price of Ethereum?`*
- *`what is the TVL of Aerodrome?`*
- *`what routes and DEXes do you use?`*

---

## 📂 Project Structure

```
stock-talk/
├── agent/                  # AI agent workflow & execution logic
│   ├── graph.py            # LangGraph state machine, tools, & MCP binding
│   ├── prompts.py          # System prompt definitions & safety rules
│   ├── registry.py         # Official Base B20 token registry & aliases
│   └── tools.py            # Tool execution wrappers & helpers
├── mcp/                    # Model Context Protocol (MCP) server
│   └── external.py         # FastMCP server (DefiLlama, TimeAPI, Weather)
├── services/               # On-chain DeFi protocol services
│   ├── aave.py             # Aave V3 Pool transaction encoder & account reader
│   ├── aerodrome.py        # Aerodrome V2 swap quote & route resolver
│   ├── aerodrome_lp.py     # Aerodrome V2 LP add/remove encoders
│   ├── quotes.py           # Multi-aggregator swap quote engine (1inch, Kyber, Odos, Slipstream, Aero, 0x)
│   ├── rpc.py              # Read-only Base JSON-RPC client
│   ├── slipstream.py       # Aerodrome Slipstream CL swap quoter & encoder
│   ├── slipstream_lp.py    # Aerodrome Slipstream CL LP mint/list/remove
│   └── uniswap_lp.py       # Uniswap V3 concentrated LP mint/list/remove
├── static/                 # Static assets
│   ├── css/
│   │   └── style.css       # Complete UI design system & themes
│   ├── img/
│   │   └── stocktalk-logo.png
│   └── js/
│       └── app.js          # Web3 wallet connection, Ethers.js signing, chat UI
├── templates/              # Flask Jinja2 templates
│   ├── base.html           # Base layout template
│   ├── index.html          # Main chat interface (/app)
│   └── landing.html        # Landing page (/)
├── .env.example            # Environment variable template
├── app.py                  # Flask entrypoint & REST API routes
├── requirements.txt        # Python package dependencies
├── schema.sql              # SQLite database schema
└── README.md               # Project documentation
```

---

## 🔒 Security & Non-Custodial Model

- **Zero Key Custody**: Stocktalk never asks for, receives, or stores private keys or seed phrases.
- **Client-Side Signature**: All transaction payloads are generated for explicit user confirmation in an injected Web3 wallet.
- **Deterministic Token Addresses**: All token contracts and protocol router addresses are hardcoded and verified against official Base deployments.
- **Notice**: Designed exclusively for eligible non-US users interacting with Coinbase Tokenized Stocks on Base. Not financial, investment, or legal advice.

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](./LICENSE) for details.
