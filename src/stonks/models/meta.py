"""Modelos de metadatos: fuentes de datos y auditoría."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
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

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    display_name: Mapped[str | None] = mapped_column(
        String(200)
    )
    base_url: Mapped[str | None] = mapped_column(
        String(500)
    )
    api_key_env_var: Mapped[str | None] = mapped_column(
        String(100)
    )
    rate_limit_per_second: Mapped[float | None] = (
        mapped_column(Numeric(6, 3))
    )
    daily_request_limit: Mapped[int | None] = (
        mapped_column(Integer)
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True
    )
    notes: Mapped[str | None] = mapped_column(Text)


class FetchRun(Base):
    """Auditoría de cada ejecución de descarga."""

    __tablename__ = "fetch_run"
    __table_args__ = {"schema": "meta"}

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )
    source_id: Mapped[int | None] = mapped_column(
        Integer
    )
    domain: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime
    )
    status: Mapped[str] = mapped_column(
        String(20), default="running"
    )
    records_fetched: Mapped[int] = mapped_column(
        Integer, default=0
    )
    records_inserted: Mapped[int] = mapped_column(
        Integer, default=0
    )
    records_updated: Mapped[int] = mapped_column(
        Integer, default=0
    )
    errors: Mapped[int] = mapped_column(
        Integer, default=0
    )
    params: Mapped[dict | None] = mapped_column(JSONB)
    error_log: Mapped[dict | None] = mapped_column(JSONB)


class DataQuality(Base):
    """Puntuación de calidad por entidad/dominio."""

    __tablename__ = "data_quality"
    __table_args__ = (
        {"schema": "meta"},
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )
    domain: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    entity_id: Mapped[str] = mapped_column(
        String(200), nullable=False
    )
    completeness_score: Mapped[float | None] = (
        mapped_column(Numeric(5, 2))
    )
    freshness_days: Mapped[int | None] = mapped_column(
        Integer
    )
    source_count: Mapped[int | None] = mapped_column(
        Integer
    )
    last_assessed: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now
    )
