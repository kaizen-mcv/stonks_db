"""Inmobiliario: índices de precios de vivienda por país.

El esquema `realestate` estaba declarado en `stonks.db.SCHEMAS` y
documentado, pero nunca llegó a crearse en la base de datos. Aquí se
modela con las tres fuentes gratuitas que cubren el dominio:

- **FRED**: House Price Index de Estados Unidos (series ALL-TRANSACTIONS
  y Case-Shiller).
- **OECD**: precios de vivienda nominales y reales de los países
  miembros.
- **Eurostat**: House Price Index de la Unión Europea.

Se separa el catálogo del índice (`price_index`) de su serie temporal
(`price_index_value`) para no repetir metadatos en cada observación.
"""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
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
from stonks.models.linaje import Linaje, LinajeEjecucion


class PriceIndex(Base, LinajeEjecucion):
    """Definición de un índice de precios inmobiliarios."""

    __tablename__ = "price_index"
    __table_args__ = (
        UniqueConstraint("code"),
        Index("ix_re_index_country", "country_code"),
        Index("ix_re_index_source", "source_id"),
        {"schema": "realestate"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    country_code: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("ref.country.code")
    )
    # residential | commercial
    segment: Mapped[str | None] = mapped_column(String(20))
    # nominal | real (deflactado)
    measure: Mapped[str | None] = mapped_column(String(20))
    frequency: Mapped[str | None] = mapped_column(String(20))
    base_period: Mapped[str | None] = mapped_column(String(20))
    unit: Mapped[str | None] = mapped_column(String(50))
    source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("meta.data_source.id")
    )


class PriceIndexValue(Base, Linaje):
    """Observación de un índice de precios inmobiliarios."""

    __tablename__ = "price_index_value"
    __table_args__ = (
        UniqueConstraint("index_id", "date"),
        Index("ix_re_value_index_date", "index_id", "date"),
        {"schema": "realestate"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    index_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("realestate.price_index.id"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    # Igual que en macro.data_point: las fuentes publican proyecciones
    # junto a observaciones y hay que poder distinguirlas.
    is_forecast: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now
    )
