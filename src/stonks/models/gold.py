"""Capa gold: modelo analítico point-in-time (hechos + dimensiones).

Construida a partir de la capa silver (esquemas de dominio) y de bronze.
Su objetivo es servir análisis cuantitativo honesto: universo
point-in-time (index_membership), fundamentales con fecha de publicación
(fact_fundamentals_pit) y factores ya neutralizados por sector
(fact_factor_scores). Las dimensiones y hechos se pueblan de forma
idempotente desde stonks.gold.build. La vista materializada
gold.mart_benchmark_returns se crea por SQL en ese módulo (no es ORM).
"""

from datetime import date

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
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


class DimDate(Base):
    """Dimensión de fecha (1 fila por día calendario)."""

    __tablename__ = "dim_date"
    __table_args__ = {"schema": "gold"}

    date_key: Mapped[date] = mapped_column(Date, primary_key=True)
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    quarter: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    month: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_month_end: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # Best-effort: día con cotización del SPY
    is_trading_day: Mapped[bool | None] = mapped_column(Boolean)


class DimCompany(Base):
    """Dimensión de empresa (SCD-1; sector desnormalizado)."""

    __tablename__ = "dim_company"
    __table_args__ = (
        Index("ix_gold_dimco_sector", "sector_id"),
        {"schema": "gold"},
    )

    company_key: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("equity.company.id"), unique=True, nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(500))
    sector_id: Mapped[int | None] = mapped_column(Integer)
    sector_name: Mapped[str | None] = mapped_column(String(200))
    industry_id: Mapped[int | None] = mapped_column(Integer)
    country_code: Mapped[str | None] = mapped_column(String(3))
    currency_code: Mapped[str | None] = mapped_column(String(3))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    delisted_date: Mapped[date | None] = mapped_column(Date)


class IndexMembership(Base):
    """Pertenencia point-in-time de una empresa a un índice.

    Un registro = un periodo de pertenencia. Miembro en la fecha t ⇔
    start_date <= t AND (end_date IS NULL OR t < end_date). Es la base
    del universo invertible sin sesgo de supervivencia.
    """

    __tablename__ = "index_membership"
    __table_args__ = (
        UniqueConstraint("index_id", "company_id", "start_date"),
        Index(
            "ix_gold_member_idx_dates", "index_id", "start_date", "end_date"
        ),
        {"schema": "gold"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    index_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("equity.market_index.id"), nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("equity.company.id"), nullable=False
    )
    # Ticker tal como estaba en la fecha (puede diferir del actual)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    source_id: Mapped[int | None] = mapped_column(Integer)


class FactFundamentalsPit(Base):
    """Hecho fundamental point-in-time (formato long, una métrica/fila).

    El grano incluye filed_date: una misma fiscal_period puede tener
    varias filas si hubo restatement (cada publicación con su fecha).
    Una consulta PIT toma el último filed_date <= fecha de análisis.
    """

    __tablename__ = "fact_fundamentals_pit"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "statement_type",
            "fiscal_year",
            "fiscal_quarter",
            "filed_date",
            "metric",
            # fiscal_quarter es NULL en anuales: trátalos como iguales
            # para que ON CONFLICT funcione (PG15+).
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_gold_pit_co_metric", "company_id", "metric", "filed_date"),
        {"schema": "gold"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("equity.company.id"), nullable=False
    )
    statement_type: Mapped[str] = mapped_column(String(10), nullable=False)
    fiscal_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    fiscal_quarter: Mapped[int | None] = mapped_column(SmallInteger)
    period_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    filed_date: Mapped[date] = mapped_column(Date, nullable=False)
    publish_date: Mapped[date | None] = mapped_column(Date)
    metric: Mapped[str] = mapped_column(String(60), nullable=False)
    value: Mapped[float | None] = mapped_column(Numeric(20, 4))
    currency_code: Mapped[str | None] = mapped_column(String(3))
    form: Mapped[str | None] = mapped_column(String(10))
    source_id: Mapped[int | None] = mapped_column(Integer)


class FactFactorScores(Base):
    """Scores de factores cross-section, neutralizados por sector.

    Un registro = (company_id, as_of_date, factor, universe). z_score es
    el z-score en todo el universo; z_sector_neutral, dentro del sector
    GICS (anti-sesgo sectorial). Listo para el ranking de kairos_bot.
    """

    __tablename__ = "fact_factor_scores"
    __table_args__ = (
        UniqueConstraint("company_id", "as_of_date", "factor", "universe"),
        Index("ix_gold_factor_date", "as_of_date", "factor", "universe"),
        {"schema": "gold"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("equity.company.id"), nullable=False
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    factor: Mapped[str] = mapped_column(String(30), nullable=False)
    universe: Mapped[str] = mapped_column(String(30), nullable=False)
    raw_value: Mapped[float | None] = mapped_column(Numeric(18, 6))
    z_score: Mapped[float | None] = mapped_column(Numeric(10, 6))
    z_sector_neutral: Mapped[float | None] = mapped_column(Numeric(10, 6))
    percentile: Mapped[float | None] = mapped_column(Numeric(6, 4))
    source_id: Mapped[int | None] = mapped_column(Integer)
