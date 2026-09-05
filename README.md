# Stocktalk 📈🤖

> **Natural-Language Assistant for Coinbase Tokenized Stocks on Base**

Stocktalk is a non-custodial, AI-powered DeFi assistant built for the **Base** ecosystem. It enables users to trade, manage liquidity, and interact with money markets for official Coinbase Tokenized Equities (such as **AAPL**, **TSLA**, **NVDA**, **GOOGL**, **MSFT**, and **COIN**) using intuitive, natural-language prompts.

---

## 🌟 Key Features

- ⚡ **Token Swaps**: Swap seamlessly between USDC and Coinbase tokenized stock pairs.
- 🌊 **Aerodrome Liquidity**: Add and remove liquidity in Aerodrome pools with automated quote building.
- 🎯 **Uniswap V3 Positions**: Mint concentrated liquidity positions for tokenized equity trading pairs.
- 🏦 **Aave Supply & Borrow**: Deposit USDC or tokenized collateral, borrow, and manage loan positions on Base.
- 🔒 **100% Non-Custodial**: All transaction payloads are generated client-side for user verification and signed directly via injected Web3 wallets (MetaMask, Coinbase Wallet, etc.).
- 🌐 **ENS & Basename Resolution**: Automatic resolution for `.eth` and `.base.eth` web3 domain names.
- 🌓 **Adaptive Theme**: Dark and Light theme modes with automatic user preference persistence.

---

## 🛠️ Architecture & Tech Stack

- **Frontend**: Flask Jinja2 templates (`landing.html`, `index.html`), custom CSS design system, and Vanilla JavaScript (`app.js`).
- **Web3 Integration**: Ethers.js (v6) for wallet connection, ENS/Basename resolution, and transaction dispatching.
- **Backend Framework**: Flask (`app.py`) providing page routes and REST APIs.
- **AI Agent**: LangChain & LangGraph workflow engine (`agent/graph.py`, `agent/intent.py`) for intent parsing, quote building, and conversational memory.
- **Database**: SQLite (`stocks.db`) initialized via `schema.sql`.
- **Integrations**: Groq (LLaMA-3.3-70b-versatile), 0x Swap API, 1inch API, Tavily Search, and Base Mainnet RPC.

---

## 📋 Prerequisites

Before running Stocktalk locally, ensure you have:

- **Python**: 3.10 or higher
- **Git**
- **Web3 Wallet**: MetaMask, Coinbase Wallet, or any injected EVM browser wallet configured for Base Mainnet (Chain ID `8453`).

---

## ⚙️ Environment Configuration (`.env`)

Copy the template environment file to create your local `.env`:

```bash
cp .env.example .env
```

### Environment Variables Breakdown

| Variable | Description | Default / Example | Required |
| :--- | :--- | :--- | :---: |
| `GROQ_API_KEY` | API Key from [Groq Console](https://console.groq.com/) for natural language processing | `gsk_...` | **Yes** |
| `GROQ_MODEL` | Groq LLM model name | `llama-3.3-70b-versatile` | Yes |
| `TAVILY_API_KEY` | [Tavily](https://tavily.com/) API Key for real-time web search context | `tvly-...` | Optional |
| `ZEROX_API_KEY` | [0x API](https://0x.org/) Key for live swap quote generation | `0x_...` | Optional |
| `ONEINCH_API_KEY` | [1inch API](https://1inch.dev/) Key for DEX aggregation quotes | `1inch_...` | Optional |
| `BASE_RPC_URL` | Base Mainnet RPC endpoint | `https://mainnet.base.org` | Yes |
| `FLASK_SECRET_KEY` | Secret key used by Flask for secure session management | `change-me-to-a-secure-key` | Yes |
| `DEMO_ALLOW_MOCK` | Set to `1` to enable fallback mock quotes if live DEX keys are omitted | `0` | No |

---

## 🚀 Local Setup & Installation

Follow these steps to run Stocktalk locally on your machine:

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

### 4. Setup Environment Variables

```bash
cp .env.example .env
```
Edit `.env` using your text editor and add your `GROQ_API_KEY` (and optional API keys).

### 5. Launch the Application

Run `app.py`:

```bash
python app.py
```

The database (`stocks.db`) will automatically initialize on startup using `schema.sql`.

### 6. Access the Application

Open your browser and navigate to:
- **Landing Page**: [http://127.0.0.1:5000/](http://127.0.0.1:5000/)
- **Chat Interface**: [http://127.0.0.1:5000/app](http://127.0.0.1:5000/app)

---

## 💬 Example Prompts

Once inside the app (`/app`), try typing:

- `"swap $2 USD for AAPL"`
- `"swap 1 TSLA for USDC"`
- `"check my portfolio balances on Base"`
- `"add LP to Aerodrome AAPL/USDC pool"`
- `"supply 5 USDC to Aave V3 market"`

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for details.
