"""Modelos de criptomonedas."""

from datetime import date

from sqlalchemy import (
    Date,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from stonks.db import Base


class Coin(Base):
    """Criptomoneda."""

    __tablename__ = "coin"
    __table_args__ = {"schema": "crypto"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coingecko_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str | None] = mapped_column(String(50))
    market_cap_rank: Mapped[int | None] = mapped_column(SmallInteger)


class CryptoPrice(Base):
    """Precio diario de criptomoneda."""

    __tablename__ = "price_daily"
    __table_args__ = (
        UniqueConstraint("coin_id", "date"),
        Index(
            "ix_crypto_price_coin_date",
            "coin_id",
            "date",
        ),
        {"schema": "crypto"},
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    coin_id: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[float | None] = mapped_column(Numeric(18, 8))
    high: Mapped[float | None] = mapped_column(Numeric(18, 8))
    low: Mapped[float | None] = mapped_column(Numeric(18, 8))
    close: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    volume_usd: Mapped[float | None] = mapped_column(Numeric(18, 2))
    market_cap_usd: Mapped[float | None] = mapped_column(Numeric(18, 2))


class MarketDominance(Base):
    """Snapshot diario del mercado crypto."""

    __tablename__ = "market_dominance"
    __table_args__ = {"schema": "crypto"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    total_market_cap_usd: Mapped[float | None] = mapped_column(Numeric(18, 2))
    btc_dominance_pct: Mapped[float | None] = mapped_column(Numeric(6, 3))
    eth_dominance_pct: Mapped[float | None] = mapped_column(Numeric(6, 3))
