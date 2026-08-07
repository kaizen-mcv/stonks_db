"""Modelos de criptomonedas."""

from datetime import date

from sqlalchemy import (
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from stonks.db import Base
from stonks.models.linaje import Linaje


class Coin(Base, Linaje):
    """Criptomoneda."""

    __tablename__ = "coin"
    __table_args__ = (
        # Dentro de este universo curado de majors, el simbolo
        # identifica la moneda. Sin esta restriccion, CoinGecko
        # publica el mismo activo con un id antiguo y otro nuevo
        # (SNX aparecia como 'havven' y 'synthetix-network-token'),
        # se cargaban las dos filas y gold.mart_crypto_overview no
        # podia refrescarse por conflicto en su indice unico.
        UniqueConstraint("symbol"),
        {"schema": "crypto"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coingecko_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str | None] = mapped_column(String(50))
    market_cap_rank: Mapped[int | None] = mapped_column(SmallInteger)


class CryptoPrice(Base, Linaje):
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
    coin_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("crypto.coin.id"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[float | None] = mapped_column(Numeric(20, 10))
    high: Mapped[float | None] = mapped_column(Numeric(20, 10))
    low: Mapped[float | None] = mapped_column(Numeric(20, 10))
    close: Mapped[float] = mapped_column(Numeric(20, 10), nullable=False)
    volume_usd: Mapped[float | None] = mapped_column(Numeric(18, 2))
    market_cap_usd: Mapped[float | None] = mapped_column(Numeric(18, 2))


class MarketDominance(Base, Linaje):
    """Snapshot diario del mercado crypto."""

    __tablename__ = "market_dominance"
    __table_args__ = {"schema": "crypto"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    total_market_cap_usd: Mapped[float | None] = mapped_column(Numeric(18, 2))
    btc_dominance_pct: Mapped[float | None] = mapped_column(Numeric(6, 3))
    eth_dominance_pct: Mapped[float | None] = mapped_column(Numeric(6, 3))


class CryptoPriceIntraday(Base):
    """Precio intraday crypto (particionado por ts)."""

    __tablename__ = "price_intraday"
    __table_args__ = (
        Index(
            "ix_crypto_intraday_interval_ts",
            "interval",
            "ts",
        ),
        {
            "schema": "crypto",
            "postgresql_partition_by": "RANGE (ts)",
        },
    )

    coin_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("crypto.coin.id"),
        primary_key=True,
    )
    ts: Mapped[date] = mapped_column(
        TIMESTAMP(timezone=True), primary_key=True
    )
    interval: Mapped[str] = mapped_column(String(3), primary_key=True)
    open: Mapped[float | None] = mapped_column(Numeric(20, 10))
    high: Mapped[float | None] = mapped_column(Numeric(20, 10))
    low: Mapped[float | None] = mapped_column(Numeric(20, 10))
    close: Mapped[float | None] = mapped_column(Numeric(20, 10))
    volume_usd: Mapped[float | None] = mapped_column(Numeric(18, 2))
