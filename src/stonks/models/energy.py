"""Energía: balances país × fuente × flujo (silver).

Modelo multidimensional (no cabe en el motor de series escalar). Fuente
gratuita: Our World in Data (energy-data). product = fuente (coal, oil,
gas, nuclear, hydro, solar, wind, renewables, fossil...); flow =
consumption | production | electricity. Valores en TWh.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from stonks.db import Base
from stonks.models.linaje import LinajeEjecucion


class Balance(Base, LinajeEjecucion):
    """Balance energético por país, fuente y flujo."""

    __tablename__ = "balance"
    __table_args__ = (
        UniqueConstraint("country_code", "product_code", "flow", "period"),
        Index("ix_energy_balance_country", "country_code", "period"),
        Index("ix_energy_balance_source", "source_id"),
        {"schema": "energy"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    country_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("ref.country.code"), nullable=False
    )
    product_code: Mapped[str] = mapped_column(String(30), nullable=False)
    flow: Mapped[str] = mapped_column(String(20), nullable=False)
    period: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    value: Mapped[float | None] = mapped_column(Numeric(18, 4))
    unit: Mapped[str | None] = mapped_column(String(20), default="TWh")
    source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("meta.data_source.id")
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now
    )
