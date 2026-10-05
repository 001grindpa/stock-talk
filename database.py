from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import Engine, create_engine, inspect, select
from sqlalchemy.orm import Session, sessionmaker

from models import Base, Trade

DATABASE_PATH = Path(__file__).resolve().parent / "stocks.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine: Engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def initialize_database() -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "trades" in tables:
        trade_columns = {column["name"] for column in inspector.get_columns("trades")}
        if "wallet" not in trade_columns:
            if "trades_legacy" in tables:
                raise RuntimeError(
                    "Cannot migrate legacy trades: trades_legacy already exists."
                )
            with engine.begin() as connection:
                connection.exec_driver_sql("ALTER TABLE trades RENAME TO trades_legacy")

    Base.metadata.create_all(engine)
    _migrate_legacy_trades()


def _migrate_legacy_trades() -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if not {"trades_legacy", "users", "quotes"}.issubset(tables):
        return

    users = {column["name"] for column in inspector.get_columns("users")}
    old_trades = {column["name"] for column in inspector.get_columns("trades_legacy")}
    quotes = {column["name"] for column in inspector.get_columns("quotes")}
    expected = (
        "wallet_address" in users
        and {"user_id", "tx_hash", "quote_id", "created_at"}.issubset(old_trades)
        and {"id", "from_token", "to_token", "amount_in", "amount_out"}.issubset(quotes)
    )
    if not expected:
        return

    from sqlalchemy import MetaData, Table

    metadata = MetaData()
    legacy_trades = Table("trades_legacy", metadata, autoload_with=engine)
    legacy_users = Table("users", metadata, autoload_with=engine)
    legacy_quotes = Table("quotes", metadata, autoload_with=engine)
    statement = (
        select(
            legacy_users.c.wallet_address,
            legacy_trades.c.tx_hash,
            legacy_trades.c.created_at,
            legacy_quotes.c.from_token,
            legacy_quotes.c.to_token,
            legacy_quotes.c.amount_in,
            legacy_quotes.c.amount_out,
        )
        .select_from(
            legacy_trades.join(
                legacy_users, legacy_users.c.id == legacy_trades.c.user_id
            ).outerjoin(
                legacy_quotes, legacy_quotes.c.id == legacy_trades.c.quote_id
            )
        )
        .where(
            legacy_users.c.wallet_address.is_not(None),
            legacy_trades.c.tx_hash.is_not(None),
        )
    )

    with SessionLocal() as db:
        existing_hashes = set(db.scalars(select(Trade.tx_hash)).all())
        for row in db.execute(statement).mappings():
            tx_hash = row["tx_hash"]
            if tx_hash in existing_hashes:
                continue
            db.add(
                Trade(
                    wallet=str(row["wallet_address"]).lower(),
                    tx_hash=tx_hash,
                    explorer=f"https://basescan.org/tx/{tx_hash}",
                    kind=row["from_token"],
                    route=None,
                    from_symbol=row["from_token"],
                    to_symbol=row["to_token"],
                    from_amount=row["amount_in"],
                    to_amount=row["amount_out"],
                    created_at=row["created_at"],
                )
            )
            existing_hashes.add(tx_hash)
        db.commit()
