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
from stonks.models.linaje import LinajeEjecucion


class Flow(Base, LinajeEjecucion):
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
        Index("ix_trade_flow_product", "product_code"),
        Index("ix_trade_flow_source", "source_id"),
        {"schema": "trade"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # Declarante y socio referencian `ref.area`, no `ref.country`: las
    # fuentes usan tambien agregados ('WLD') y entidades historicas
    # ('CSK'). Asi ambos extremos quedan validados por igual.
    reporter_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("ref.area.code"), nullable=False
    )
    partner_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("ref.area.code"), nullable=False
    )
    product_code: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("ref.hs_product.code"),
        nullable=False,
        default="Total",
    )
    flow: Mapped[str] = mapped_column(String(1), nullable=False)  # X | M
    period: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    value_usd_k: Mapped[float | None] = mapped_column(Numeric(20, 3))
    source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("meta.data_source.id")
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now
    )
