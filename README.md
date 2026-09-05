# Stocktalk

A small Elsa-style chat app for **official Coinbase Tokenized Stocks on Base**.

The model parses intent and the backend returns a structured swap quote. **The backend never holds keys and never signs.** Your browser wallet signs every transaction after you click Confirm.

Flow:

`chat API → action JSON → app.js → wallet`

1. You type `swap $2 USD for AAPL`.
2. Frontend `POST /api/chat`.
3. LangGraph maps AAPL → official **AAPLc**, USD → **USDC**.
4. Backend fetches a 0x quote on Base (1inch fallback, MOCK if keys are missing).
5. Response includes assistant text plus `action.type: "quote"`.
6. The page renders a confirm card. **MetaMask opens only after Confirm** — never because the LLM asked.
7. `app.js` approves the spender if needed, then `ethers.sendTransaction`.
8. Frontend `POST /api/trades` with the hash.
9. Chat shows a [Basescan](https://basescan.org) link.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill `.env`:

- `GROQ_API_KEY` — ChatGroq (tries `llama-3.3-70b-versatile`, then Groq’s live replacement)
- `GROQ_MODEL` — optional override
- `TAVILY_API_KEY` — research questions only (`what is AAPLc?`)
- `ZEROX_API_KEY` — live Swap API quotes on Base
- `ONEINCH_API_KEY` — optional fallback
- `BASE_RPC_URL` — defaults to `https://mainnet.base.org`
- `FLASK_SECRET_KEY`
- `DEMO_ALLOW_MOCK=1` — allow Confirm on MOCK quotes (local demo only)

Token addresses are **not** taken from the LLM or Tavily. They are hardcoded from [Base tokenized stocks](https://www.base.org/stocks) and [B20 docs](https://docs.base.org/specifications/b20/tokenized-stocks-on-base), then stored in SQLite.

## Run

```bash
flask --app app run --debug
```

Open http://127.0.0.1:5000. Connect a wallet on **Base (chainId 8453)**.

Without a 0x/1inch key, quotes are labeled **MOCK** and Confirm is disabled unless `DEMO_ALLOW_MOCK=1` or you open `/?demo=1`.

## Example prompts

- `swap $2 USD for AAPL` → USDC → official AAPLc quote
- `sell 0.01 NVDAc for USDC`
- `what is AAPLc?` → Tavily + Groq research, `action.type: "none"`
- `swap $2 USD for FAKE` → `action.type: "error"`

Demo cap: **$50**.

## API

`POST /api/chat` `{ message, wallet, conversation_id }`

Quote payload shape:

```json
{
  "conversation_id": 1,
  "message": "I’ll swap 2 USDC for AAPLc on Base. Confirm in your wallet.",
  "action": {
    "type": "quote",
    "quote_id": 12,
    "from": {
      "symbol": "USDC",
      "address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
      "decimals": 6,
      "amount": "2",
      "amountWei": "2000000"
    },
    "to": {
      "symbol": "AAPLc",
      "address": "0xb200000000000000000000C2e324d24d7eEcd1fb",
      "decimals": 18,
      "amount": "0.0060"
    },
    "priceImpactBps": 12,
    "route": "0x",
    "tx": { "to": "0x...", "data": "0x...", "value": "0" },
    "spender": "0x..."
  }
}
```

If no transaction is needed: `action.type` is `"none"`. Unknown ticker: `"error"`.

Other routes: `GET /api/tokens`, `POST /api/trades`, `GET /api/conversation/<id>`.

## Safety

- Backend does not sign.
- No private keys in the repo (`.env` is gitignored).
- Allowlist only.
- Confirm before every transaction.
- Eligible non-US users only. Not investment advice.
