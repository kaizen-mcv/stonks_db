"""Modelos de divisas / forex."""

from datetime import date

from sqlalchemy import (
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from stonks.db import Base


class CurrencyPair(Base):
    """Par de divisas."""

    __tablename__ = "currency_pair"
    __table_args__ = (
        UniqueConstraint("base_currency", "quote_currency"),
        {"schema": "forex"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    base_currency: Mapped[str] = mapped_column(
        String(3),
        ForeignKey("ref.currency.code"),
        nullable=False,
    )
    quote_currency: Mapped[str] = mapped_column(
        String(3),
        ForeignKey("ref.currency.code"),
        nullable=False,
    )
    pair_code: Mapped[str] = mapped_column(
        String(7), unique=True, nullable=False
    )
    category: Mapped[str | None] = mapped_column(String(20))


class ForexRate(Base):
    """Tipo de cambio diario."""

    __tablename__ = "rate_daily"
    __table_args__ = (
        UniqueConstraint("pair_id", "date"),
        Index(
            "ix_forex_rate_pair_date",
            "pair_id",
            "date",
        ),
        {"schema": "forex"},
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    pair_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("forex.currency_pair.id"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[float | None] = mapped_column(Numeric(14, 8))
    high: Mapped[float | None] = mapped_column(Numeric(14, 8))
    low: Mapped[float | None] = mapped_column(Numeric(14, 8))
    close: Mapped[float] = mapped_column(Numeric(14, 8), nullable=False)
    source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("meta.data_source.id")
    )
