"""Modelos de fondos y ETFs."""

from datetime import date

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from stonks.db import Base


class Fund(Base):
    """Fondo / ETF."""

    __tablename__ = "fund"
    __table_args__ = (
        UniqueConstraint("ticker", "exchange_id"),
        {"schema": "fund"},
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )
    ticker: Mapped[str | None] = mapped_column(
        String(20)
    )
    name: Mapped[str] = mapped_column(
        String(500), nullable=False
    )
    fund_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    asset_class: Mapped[str | None] = mapped_column(
        String(50)
    )
    geography: Mapped[str | None] = mapped_column(
        String(100)
    )
    strategy: Mapped[str | None] = mapped_column(
        String(100)
    )
    provider: Mapped[str | None] = mapped_column(
        String(100)
    )
    expense_ratio: Mapped[float | None] = (
        mapped_column(Numeric(6, 4))
    )
    aum_usd: Mapped[float | None] = mapped_column(
        Numeric(18, 2)
    )
    inception_date: Mapped[date | None] = (
        mapped_column(Date)
    )
    currency_code: Mapped[str | None] = mapped_column(
        String(3)
    )
    exchange_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ref.exchange.id")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True
    )


class NavDaily(Base):
    """NAV diario del fondo."""

    __tablename__ = "nav_daily"
    __table_args__ = (
        UniqueConstraint("fund_id", "date"),
        {"schema": "fund"},
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    fund_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("fund.fund.id"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(
        Date, nullable=False
    )
    nav: Mapped[float] = mapped_column(
        Numeric(14, 6), nullable=False
    )
    volume: Mapped[int | None] = mapped_column(
        Integer
    )
