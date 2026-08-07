"""Agricultura: producción por país, item y elemento (silver).

Multidimensional (no cabe en el motor de series escalar). Fuente
gratuita: FAOSTAT (bulk CSV normalizado). item = cultivo/ganado,
element = producción/rendimiento/área cosechada.
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


class Production(Base, LinajeEjecucion):
    """Producción agrícola por país, item y elemento."""

    __tablename__ = "production"
    __table_args__ = (
        UniqueConstraint("country_code", "item_code", "element", "period"),
        Index("ix_agri_prod_country", "country_code", "period"),
        Index("ix_agri_prod_source", "source_id"),
        {"schema": "agri"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    country_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("ref.country.code"), nullable=False
    )
    item_code: Mapped[str] = mapped_column(String(20), nullable=False)
    item_name: Mapped[str | None] = mapped_column(String(200))
    element: Mapped[str] = mapped_column(String(60), nullable=False)
    period: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    value: Mapped[float | None] = mapped_column(Numeric(24, 3))
    unit: Mapped[str | None] = mapped_column(String(40))
    source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("meta.data_source.id")
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now
    )
