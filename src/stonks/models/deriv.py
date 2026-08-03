"""Derivados: snapshots de cadenas de opciones (silver).

yfinance solo da la cadena actual (sin histórico), así que el histórico
se acumula capturando una foto por día. Un registro = un contrato
(empresa × fecha × vencimiento × tipo × strike) en un snapshot.
"""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from stonks.db import Base


class OptionSnapshot(Base):
    """Foto de un contrato de opción (call/put)."""

    __tablename__ = "option_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "snapshot_date", "expiry", "option_type", "strike"
        ),
        Index("ix_deriv_opt_company", "company_id", "snapshot_date"),
        {"schema": "deriv"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("equity.company.id"), nullable=False
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry: Mapped[date] = mapped_column(Date, nullable=False)
    option_type: Mapped[str] = mapped_column(String(1), nullable=False)  # C/P
    strike: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    last_price: Mapped[float | None] = mapped_column(Numeric(14, 4))
    bid: Mapped[float | None] = mapped_column(Numeric(14, 4))
    ask: Mapped[float | None] = mapped_column(Numeric(14, 4))
    volume: Mapped[int | None] = mapped_column(Integer)
    open_interest: Mapped[int | None] = mapped_column(Integer)
    implied_vol: Mapped[float | None] = mapped_column(Numeric(10, 6))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now
    )


class VolatilityIndex(Base):
    """Índice de volatilidad de referencia."""

    __tablename__ = "volatility_index"
    __table_args__ = {"schema": "deriv"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    underlying: Mapped[str | None] = mapped_column(String(50))
    yfinance_ticker: Mapped[str] = mapped_column(String(30), nullable=False)


class VolatilityDaily(Base):
    """Precio diario de índice de volatilidad."""

    __tablename__ = "volatility_daily"
    __table_args__ = (
        UniqueConstraint("index_id", "date"),
        Index(
            "ix_deriv_vol_idx_date",
            "index_id",
            "date",
        ),
        {"schema": "deriv"},
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    index_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("deriv.volatility_index.id"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[float | None] = mapped_column(Numeric(10, 4))
    high: Mapped[float | None] = mapped_column(Numeric(10, 4))
    low: Mapped[float | None] = mapped_column(Numeric(10, 4))
    close: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("meta.data_source.id")
    )


class FuturesContract(Base):
    """Contrato de futuros (índice, bono, divisa)."""

    __tablename__ = "futures_contract"
    __table_args__ = {"schema": "deriv"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    underlying: Mapped[str | None] = mapped_column(String(50))
    category: Mapped[str | None] = mapped_column(String(30))
    yfinance_ticker: Mapped[str] = mapped_column(String(30), nullable=False)


class FuturesDaily(Base):
    """Precio diario de futuros."""

    __tablename__ = "futures_daily"
    __table_args__ = (
        UniqueConstraint("contract_id", "date"),
        Index(
            "ix_deriv_fut_contract_date",
            "contract_id",
            "date",
        ),
        {"schema": "deriv"},
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    contract_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("deriv.futures_contract.id"),
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
