import os
import re
import sqlite3
import threading

from cs50 import SQL
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from agent.graph import run_agent
from agent.registry import seed_tokens

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or "change-me"
if not os.path.exists("stocks.db"):
    open("stocks.db", "a", encoding="utf-8").close()
db = SQL("sqlite:///stocks.db")


class TokenDatabase:
    def __init__(self) -> None:
        self.connection = sqlite3.connect(":memory:", check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.lock = threading.Lock()

    def execute(self, query: str, *args):
        with self.lock:
            cursor = self.connection.execute(query, args)
            self.connection.commit()
            if cursor.description:
                return cursor.fetchall()
            return cursor.lastrowid


token_db = TokenDatabase()
token_db.execute(
    """
    CREATE TABLE tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        address TEXT NOT NULL UNIQUE,
        decimals INTEGER NOT NULL,
        kind TEXT NOT NULL,
        aliases TEXT NOT NULL DEFAULT '[]'
    )
    """
)
seed_tokens(token_db)

WALLET_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
TX_RE = re.compile(r"^0x[a-fA-F0-9]{64}$")


def init_db() -> None:
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, encoding="utf-8") as handle:
        sql = handle.read()
    with sqlite3.connect("stocks.db") as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        legacy_trades = False
        if "trades" in tables:
            columns = {
                row[1] for row in conn.execute("PRAGMA table_info(trades)")
            }
            if "wallet" not in columns:
                conn.execute("ALTER TABLE trades RENAME TO trades_legacy")
                legacy_trades = True
        conn.executescript(sql)
        if legacy_trades:
            conn.execute(
                """
                INSERT OR IGNORE INTO trades (
                    wallet, tx_hash, explorer, kind, route,
                    from_symbol, to_symbol, from_amount, to_amount, created_at
                )
                SELECT lower(u.wallet_address), t.tx_hash,
                       'https://basescan.org/tx/' || t.tx_hash,
                       q.from_token, NULL, q.from_token, q.to_token,
                       q.amount_in, q.amount_out, t.created_at
                FROM trades_legacy t
                JOIN users u ON u.id = t.user_id
                LEFT JOIN quotes q ON q.id = t.quote_id
                WHERE u.wallet_address IS NOT NULL AND t.tx_hash IS NOT NULL
                """
            )
        conn.executescript(
            """
            DROP TABLE IF EXISTS messages;
            DROP TABLE IF EXISTS conversations;
            DROP TABLE IF EXISTS quotes;
            DROP TABLE IF EXISTS users;
            DROP TABLE IF EXISTS trades_legacy;
            DROP TABLE IF EXISTS tokens;
            """
        )
        conn.commit()


def normalize_wallet(value: str | None) -> str | None:
    if not value:
        return None
    wallet = value.strip()
    if not WALLET_RE.match(wallet):
        return None
    return wallet.lower()


@app.route("/")
def landing():
    session["redirect_to_landing"] = True
    return render_template("landing.html", page_id="landing")


@app.route("/app")
def app_route():
    if session.get("redirect_to_landing") and request.args.get("from_landing") != "1":
        return redirect(url_for("landing"))
    session.pop("redirect_to_landing", None)
    demo = os.getenv("DEMO_ALLOW_MOCK", "0").strip() in {"1", "true", "True", "yes"}
    return render_template("index.html", page_id="index", demo_allow_mock=demo)


@app.get("/api/tokens")
def api_tokens():
    rows = token_db.execute(
        "SELECT symbol, name, address, decimals, kind FROM tokens ORDER BY kind DESC, symbol"
    )
    return jsonify({"chainId": 8453, "tokens": [dict(row) for row in rows]})


@app.post("/api/chat")
async def api_chat():
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify({"error": "message is required"}), 400

    wallet = normalize_wallet(payload.get("wallet"))
    balances = payload.get("balances") if isinstance(payload.get("balances"), list) else []
    thread_id = (payload.get("thread_id") or "").strip() or "page-session"

    result = await run_agent(
        db=token_db,
        message=message,
        wallet=wallet,
        balances=balances,
        thread_id=thread_id,
        history=[],
    )
    action = result.get("action") or {"type": "none"}
    assistant_text = result.get("message") or ""

    return jsonify(
        {
            "thread_id": thread_id,
            "message": assistant_text,
            "action": action,
        }
    )


@app.post("/api/trades")
def api_trades():
    payload = request.get_json(silent=True) or {}
    wallet = normalize_wallet(payload.get("wallet"))
    tx_hash = (payload.get("tx_hash") or "").strip()

    if not wallet:
        return jsonify({"error": "valid wallet is required"}), 400
    if not TX_RE.match(tx_hash):
        return jsonify({"error": "valid tx_hash is required"}), 400
    explorer = (payload.get("explorer") or "").strip() or f"https://basescan.org/tx/{tx_hash}"
    fields = {
        "wallet": wallet,
        "tx_hash": tx_hash,
        "explorer": explorer,
        "kind": payload.get("kind"),
        "route": payload.get("route"),
        "from_symbol": payload.get("from_symbol"),
        "to_symbol": payload.get("to_symbol"),
        "from_amount": payload.get("from_amount"),
        "to_amount": payload.get("to_amount"),
    }
    db.execute(
        """
        INSERT INTO trades (
            wallet, tx_hash, explorer, kind, route, from_symbol, to_symbol,
            from_amount, to_amount
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(tx_hash) DO UPDATE SET
            wallet = excluded.wallet,
            explorer = excluded.explorer,
            kind = excluded.kind,
            route = excluded.route,
            from_symbol = excluded.from_symbol,
            to_symbol = excluded.to_symbol,
            from_amount = excluded.from_amount,
            to_amount = excluded.to_amount
        """,
        *fields.values(),
    )
    row = db.execute("SELECT * FROM trades WHERE tx_hash = ?", tx_hash)[0]
    return jsonify(dict(row))


@app.get("/api/trades")
def get_trades():
    wallet = normalize_wallet(request.args.get("wallet"))
    if not wallet:
        return jsonify({"error": "valid wallet is required"}), 400
    rows = db.execute(
        "SELECT * FROM trades WHERE wallet = ? ORDER BY created_at DESC, id DESC LIMIT 50",
        wallet,
    )
    return jsonify({"trades": [dict(row) for row in rows]})


init_db()


if __name__ == "__main__":
    app.run(debug=True)
