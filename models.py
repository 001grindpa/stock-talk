from __future__ import annotations

from sqlalchemy import Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Token(Base):
    __tablename__ = "tokens"
    __table_args__ = (UniqueConstraint("address"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    decimals: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    aliases: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'[]'"))


class Trade(Base):
    __tablename__ = "trades"
    __table_args__ = (Index("ix_trades_wallet_created_at", "wallet", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet: Mapped[str] = mapped_column(Text, nullable=False)
    tx_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    explorer: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str | None] = mapped_column(Text)
    route: Mapped[str | None] = mapped_column(Text)
    from_symbol: Mapped[str | None] = mapped_column(Text)
    to_symbol: Mapped[str | None] = mapped_column(Text)
    from_amount: Mapped[str | None] = mapped_column(Text)
    to_amount: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str | None] = mapped_column(
        Text, nullable=True, server_default=text("CURRENT_TIMESTAMP")
    )

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "wallet": self.wallet,
            "tx_hash": self.tx_hash,
            "explorer": self.explorer,
            "kind": self.kind,
            "route": self.route,
            "from_symbol": self.from_symbol,
            "to_symbol": self.to_symbol,
            "from_amount": self.from_amount,
            "to_amount": self.to_amount,
            "created_at": self.created_at,
        }
