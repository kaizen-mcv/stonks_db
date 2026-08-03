"""Comercio internacional: flujos bilaterales (silver).

Modelo multidimensional que no cabe en el motor de series escalar
(macro): un flujo = reporter × partner × producto × flujo (X/M) × año.
Fuente gratuita: World Bank WITS. De momento a nivel producto 'Total'
(matriz bilateral país×país); el detalle HS se puede añadir después.
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


class Flow(Base):
    """Flujo comercial bilateral (exportación/importación)."""

    __tablename__ = "flow"
    __table_args__ = (
        UniqueConstraint(
            "reporter_code",
            "partner_code",
            "product_code",
            "flow",
            "period",
        ),
        Index("ix_trade_flow_reporter", "reporter_code", "period"),
        Index("ix_trade_flow_partner", "partner_code", "period"),
        {"schema": "trade"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    reporter_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("ref.country.code"), nullable=False
    )
    # Socio: ISO3 o agregado ('WLD'); sin FK para permitir agregados.
    partner_code: Mapped[str] = mapped_column(String(3), nullable=False)
    product_code: Mapped[str] = mapped_column(
        String(20), nullable=False, default="Total"
    )
    flow: Mapped[str] = mapped_column(String(1), nullable=False)  # X | M
    period: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    value_usd_k: Mapped[float | None] = mapped_column(Numeric(20, 3))
    source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("meta.data_source.id")
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now
    )
