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
