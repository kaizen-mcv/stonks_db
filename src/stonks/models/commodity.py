"""Modelos de materias primas."""

from datetime import date

from sqlalchemy import (
    BigInteger,
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


class Commodity(Base):
    """Materia prima."""

    __tablename__ = "commodity"
    __table_args__ = {"schema": "commodity"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str | None] = mapped_column(String(50))
    subcategory: Mapped[str | None] = mapped_column(String(50))
    unit: Mapped[str | None] = mapped_column(String(50))
    currency_code: Mapped[str | None] = mapped_column(String(3), default="USD")
    exchange: Mapped[str | None] = mapped_column(String(50))
    yfinance_ticker: Mapped[str | None] = mapped_column(String(20))


class CommodityPrice(Base):
    """Precio diario de materia prima."""

    __tablename__ = "price_daily"
    __table_args__ = (
        UniqueConstraint("commodity_id", "date"),
        Index(
            "ix_comm_price_id_date",
            "commodity_id",
            "date",
        ),
        {"schema": "commodity"},
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    commodity_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("commodity.commodity.id"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[float | None] = mapped_column(Numeric(14, 4))
    high: Mapped[float | None] = mapped_column(Numeric(14, 4))
    low: Mapped[float | None] = mapped_column(Numeric(14, 4))
    close: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    volume: Mapped[int | None] = mapped_column(BigInteger)
    source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("meta.data_source.id")
    )
