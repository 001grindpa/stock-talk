import json
import os
import re
import sqlite3

from cs50 import SQL
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from agent.graph import run_agent
from agent.registry import seed_tokens

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or "change-me"
if not os.path.exists("stocks.db"):
    open("stocks.db", "a", encoding="utf-8").close()
db = SQL("sqlite:///stocks.db")

WALLET_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
TX_RE = re.compile(r"^0x[a-fA-F0-9]{64}$")


def init_db() -> None:
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, encoding="utf-8") as handle:
        sql = handle.read()
    with sqlite3.connect("stocks.db") as conn:
        conn.executescript(sql)
        conn.commit()
    seed_tokens(db)


def normalize_wallet(value: str | None) -> str | None:
    if not value:
        return None
    wallet = value.strip()
    if not WALLET_RE.match(wallet):
        return None
    return wallet.lower()


def get_or_create_user(wallet: str) -> int:
    rows = db.execute("SELECT id FROM users WHERE wallet_address = ?", wallet)
    if rows:
        return rows[0]["id"]
    return db.execute("INSERT INTO users (wallet_address) VALUES (?)", wallet)


def get_or_create_conversation(conversation_id: int | None, user_id: int | None) -> int:
    if conversation_id:
        rows = db.execute("SELECT id FROM conversations WHERE id = ?", conversation_id)
        if rows:
            if user_id:
                db.execute(
                    "UPDATE conversations SET user_id = ? WHERE id = ? AND user_id IS NULL",
                    user_id,
                    conversation_id,
                )
            return conversation_id
    return db.execute("INSERT INTO conversations (user_id) VALUES (?)", user_id)


@app.route("/")
def index():
    demo = os.getenv("DEMO_ALLOW_MOCK", "0").strip() in {"1", "true", "True", "yes"}
    return render_template("index.html", demo_allow_mock=demo)


@app.get("/api/tokens")
def api_tokens():
    rows = db.execute(
        "SELECT symbol, name, address, decimals, kind FROM tokens ORDER BY kind DESC, symbol"
    )
    return jsonify({"chainId": 8453, "tokens": rows})


@app.post("/api/chat")
def api_chat():
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify({"error": "message is required"}), 400

    wallet = normalize_wallet(payload.get("wallet"))
    user_id = get_or_create_user(wallet) if wallet else None
    conversation_id = get_or_create_conversation(payload.get("conversation_id"), user_id)

    db.execute(
        "INSERT INTO messages (conversation_id, role, content, action_json) VALUES (?, ?, ?, ?)",
        conversation_id,
        "user",
        message,
        None,
    )

    result = run_agent(db=db, message=message, wallet=wallet)
    action = result.get("action") or {"type": "none"}
    quote = result.get("quote")

    if action.get("type") == "quote" and quote:
        quote_id = db.execute(
            """
            INSERT INTO quotes (
                conversation_id, from_token, to_token, amount_in, amount_out,
                spender, tx_to, tx_data, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            conversation_id,
            quote["from"]["symbol"],
            quote["to"]["symbol"],
            quote["from"]["amount"],
            quote["to"]["amount"],
            quote.get("spender"),
            (quote.get("tx") or {}).get("to"),
            (quote.get("tx") or {}).get("data"),
            json.dumps(quote.get("raw") or quote),
        )
        action["quote_id"] = quote_id

    assistant_text = result.get("message") or ""
    db.execute(
        "INSERT INTO messages (conversation_id, role, content, action_json) VALUES (?, ?, ?, ?)",
        conversation_id,
        "assistant",
        assistant_text,
        json.dumps(action),
    )

    return jsonify(
        {
            "conversation_id": conversation_id,
            "message": assistant_text,
            "action": action,
        }
    )


@app.post("/api/trades")
def api_trades():
    payload = request.get_json(silent=True) or {}
    wallet = normalize_wallet(payload.get("wallet"))
    tx_hash = (payload.get("tx_hash") or "").strip()
    quote_id = payload.get("quote_id")

    if not wallet:
        return jsonify({"error": "valid wallet is required"}), 400
    if not TX_RE.match(tx_hash):
        return jsonify({"error": "valid tx_hash is required"}), 400
    if not quote_id:
        return jsonify({"error": "quote_id is required"}), 400

    quotes = db.execute("SELECT id FROM quotes WHERE id = ?", quote_id)
    if not quotes:
        return jsonify({"error": "quote not found"}), 404

    user_id = get_or_create_user(wallet)
    trade_id = db.execute(
        "INSERT INTO trades (user_id, quote_id, tx_hash, status) VALUES (?, ?, ?, ?)",
        user_id,
        quote_id,
        tx_hash,
        "submitted",
    )
    return jsonify(
        {
            "id": trade_id,
            "tx_hash": tx_hash,
            "explorer": f"https://basescan.org/tx/{tx_hash}",
            "status": "submitted",
        }
    )


@app.get("/api/conversation/<int:conversation_id>")
def api_conversation(conversation_id: int):
    conv = db.execute("SELECT id, user_id, created_at FROM conversations WHERE id = ?", conversation_id)
    if not conv:
        return jsonify({"error": "not found"}), 404
    messages = db.execute(
        """
        SELECT id, role, content, action_json, created_at
        FROM messages WHERE conversation_id = ? ORDER BY id
        """,
        conversation_id,
    )
    out = []
    for row in messages:
        item = dict(row)
        if item.get("action_json"):
            try:
                item["action"] = json.loads(item["action_json"])
            except json.JSONDecodeError:
                item["action"] = None
        else:
            item["action"] = None
        del item["action_json"]
        out.append(item)
    return jsonify({"conversation": conv[0], "messages": out})


init_db()


if __name__ == "__main__":
    app.run(debug=True)
