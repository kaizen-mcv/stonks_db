"""Modelos de metadatos: fuentes de datos y auditoría."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from stonks.db import Base


class DataSource(Base):
    """Registro de fuentes de datos (APIs)."""

    __tablename__ = "data_source"
    __table_args__ = {"schema": "meta"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200))
    base_url: Mapped[str | None] = mapped_column(String(500))
    api_key_env_var: Mapped[str | None] = mapped_column(String(100))
    rate_limit_per_second: Mapped[float | None] = mapped_column(Numeric(6, 3))
    daily_request_limit: Mapped[int | None] = mapped_column(Integer)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)


class FetchRun(Base):
    """Auditoría de cada ejecución de descarga."""

    __tablename__ = "fetch_run"
    __table_args__ = (
        Index("ix_meta_fetch_run_source", "source_id"),
        {"schema": "meta"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("meta.data_source.id"),
    )
    domain: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    status: Mapped[str] = mapped_column(String(20), default="running")
    records_fetched: Mapped[int] = mapped_column(Integer, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    params: Mapped[dict | None] = mapped_column(JSONB)
    error_log: Mapped[dict | None] = mapped_column(JSONB)


class TransformRun(Base):
    """Auditoría de cada transformación (bronze→silver, →gold)."""

    __tablename__ = "transform_run"
    __table_args__ = {"schema": "meta"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    domain: Mapped[str] = mapped_column(String(50), index=True)
    # Capa destino: silver o gold
    target_layer: Mapped[str] = mapped_column(String(20), default="silver")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    status: Mapped[str] = mapped_column(String(20), default="running")
    records_read: Mapped[int] = mapped_column(Integer, default=0)
    records_written: Mapped[int] = mapped_column(Integer, default=0)
    records_invalid: Mapped[int] = mapped_column(Integer, default=0)
    params: Mapped[dict | None] = mapped_column(JSONB)
    error_log: Mapped[dict | None] = mapped_column(JSONB)


class DataQuality(Base):
    """Puntuación de calidad por entidad/dominio."""

    __tablename__ = "data_quality"
    __table_args__ = ({"schema": "meta"},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    domain: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(200), nullable=False)
    completeness_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    freshness_days: Mapped[int | None] = mapped_column(Integer)
    source_count: Mapped[int | None] = mapped_column(Integer)
    last_assessed: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now
    )


class TableCertification(Base):
    """Cómo se ha verificado cada tabla de datos.

    Con datos de terceros no se puede garantizar que cada cifra sea
    cierta: si el World Bank publica mal un PIB, la base lo reproduce
    fielmente. Lo que sí se puede garantizar, y es lo que registra esta
    tabla, es que **de cada tabla conste cómo se ha verificado, o que
    conste explícitamente que no se puede verificar y por qué**.

    Estados posibles:

    - `contrastada_externamente`: hay al menos un valor de
      `tests/referencias.yml` que compara una fila suya contra una
      cifra publicada fuera del proyecto.
    - `coherente_sin_referencia`: no hay cifra externa que contrastar,
      pero sí comprobaciones estructurales que pasa (OHLC posible,
      unidades plausibles, mínimos de volumen, frescura).
    - `no_verificable`: se ha mirado y no hay forma razonable de
      comprobarla. Lleva motivo escrito.
    - `sin_certificar`: nadie ha declarado nada. Es el estado que hace
      fallar el test de certificación.
    """

    __tablename__ = "table_certification"
    __table_args__ = ({"schema": "meta"},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schema_name: Mapped[str] = mapped_column(String(63), nullable=False)
    table_name: Mapped[str] = mapped_column(String(63), nullable=False)
    estado: Mapped[str] = mapped_column(String(40), nullable=False)
    metodo: Mapped[str | None] = mapped_column(String(500))
    motivo: Mapped[str | None] = mapped_column(String(500))
    filas: Mapped[int | None] = mapped_column(BigInteger)
    referencias: Mapped[int] = mapped_column(Integer, default=0)
    certificado_por: Mapped[str | None] = mapped_column(String(60))
    certified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now
    )
