"""Capa bronze: aterrizaje crudo (append-only, JSONB).

Solo se usa para las fuentes NUEVAS del proyecto medallion (SEC EDGAR,
constituyentes de índices y snapshots de analistas). Las fuentes ya
existentes siguen escribiendo directamente en sus esquemas de dominio
("silver"). El payload se guarda tal cual llega; la normalización se
hace en la capa transform.
"""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from stonks.db import Base


class ApiResponse(Base):
    """Respuesta cruda de una API macro (genérica, append-only).

    Aterrizaje común para las fuentes de economía mundial (IMF, World
    Bank, Eurostat, OECD, ILO, WHO, EIA, OWID...). La normalización a
    macro.series/data_point la hace transform/macro_indicators.py.
    """

    __tablename__ = "api_response"
    __table_args__ = {"schema": "bronze"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    fetch_run_id: Mapped[int | None] = mapped_column(Integer)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, index=True
    )
    source_name: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    dataset: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    params: Mapped[dict | None] = mapped_column(JSONB)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)


class YfProfile(Base):
    """Volcado completo del `.info` de yfinance por empresa (foto)."""

    __tablename__ = "yf_profile"
    __table_args__ = (
        UniqueConstraint("ticker", "snapshot_date"),
        {"schema": "bronze"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    fetch_run_id: Mapped[int | None] = mapped_column(Integer)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now
    )
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)


class SecCompanyFacts(Base):
    """JSON crudo de la API companyfacts de SEC EDGAR (por empresa).

    Append-only: cada descarga añade una fila nueva. La transform lee
    el último payload por CIK.
    """

    __tablename__ = "sec_companyfacts"
    __table_args__ = {"schema": "bronze"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    fetch_run_id: Mapped[int | None] = mapped_column(Integer)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, index=True
    )
    cik: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    ticker: Mapped[str | None] = mapped_column(String(20))
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)


class ConstituentsSnapshot(Base):
    """Foto cruda de constituyentes de un índice (Wikipedia/GitHub).

    source_kind distingue la procedencia: 'wikipedia_current',
    'wikipedia_changelog' o 'github_csv'.
    """

    __tablename__ = "constituents_snapshot"
    __table_args__ = {"schema": "bronze"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    fetch_run_id: Mapped[int | None] = mapped_column(Integer)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, index=True
    )
    index_code: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    source_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)


class AnalystSnapshot(Base):
    """Foto diaria de datos de analistas de yfinance (por ticker).

    El histórico de revisiones se construye acumulando una foto por día
    hacia adelante (yfinance no da serie retroactiva). UNIQUE por
    (ticker, snapshot_date) evita duplicar la foto del mismo día.
    """

    __tablename__ = "analyst_snapshot"
    __table_args__ = (
        UniqueConstraint("ticker", "snapshot_date"),
        {"schema": "bronze"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    fetch_run_id: Mapped[int | None] = mapped_column(Integer)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now
    )
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
