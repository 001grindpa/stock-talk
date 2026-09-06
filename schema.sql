CREATE TABLE IF NOT EXISTS trades (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	wallet TEXT NOT NULL,
	tx_hash TEXT NOT NULL UNIQUE,
	explorer TEXT NOT NULL,
	kind TEXT,
	route TEXT,
	from_symbol TEXT,
	to_symbol TEXT,
	from_amount TEXT,
	to_amount TEXT,
	created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
