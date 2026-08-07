"""Modelos macroeconómicos: indicadores y series temporales."""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from stonks.db import Base
from stonks.models.linaje import Linaje, LinajeEjecucion


class Indicator(Base, Linaje):
    """Definición de un indicador macroeconómico."""

    __tablename__ = "indicator"
    __table_args__ = {"schema": "macro"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))
    subcategory: Mapped[str | None] = mapped_column(String(100))
    unit: Mapped[str | None] = mapped_column(String(50))
    frequency: Mapped[str | None] = mapped_column(String(20))
    seasonal_adjustment: Mapped[str | None] = mapped_column(String(20))
    description: Mapped[str | None] = mapped_column(Text)


class IndicatorSource(Base, LinajeEjecucion):
    """Mapeo indicador → código en fuente externa."""

    __tablename__ = "indicator_source"
    __table_args__ = (
        UniqueConstraint("indicator_id", "source_id"),
        Index("ix_macro_indsrc_source", "source_id"),
        {"schema": "macro"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    indicator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("macro.indicator.id"),
        nullable=False,
    )
    source_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("meta.data_source.id"),
        nullable=False,
    )
    external_code: Mapped[str] = mapped_column(String(200), nullable=False)
    external_name: Mapped[str | None] = mapped_column(String(500))
    priority: Mapped[int] = mapped_column(SmallInteger, default=1)


class Series(Base, Linaje):
    """Serie temporal: indicador + país."""

    __tablename__ = "series"
    __table_args__ = (
        UniqueConstraint(
            "indicator_id",
            "country_code",
            "region_code",
        ),
        Index("ix_macro_series_country", "country_code"),
        {"schema": "macro"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    indicator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("macro.indicator.id"),
        nullable=False,
    )
    country_code: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("ref.country.code")
    )
    region_code: Mapped[str | None] = mapped_column(String(20))
    last_value: Mapped[float | None] = mapped_column(Numeric(20, 6))
    last_date: Mapped[date | None] = mapped_column(Date)
    point_count: Mapped[int] = mapped_column(Integer, default=0)


class DataPoint(Base, LinajeEjecucion):
    """Punto de datos de una serie temporal."""

    __tablename__ = "data_point"
    __table_args__ = (
        UniqueConstraint("series_id", "date"),
        Index(
            "ix_macro_dp_series_date",
            "series_id",
            "date",
        ),
        Index("ix_macro_dp_source", "source_id"),
        {"schema": "macro"},
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    series_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("macro.series.id"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    # Las fuentes mezclan observaciones con proyecciones: el WEO del FMI
    # y las WPP de la ONU publican series que llegan hasta 2030+. Sin
    # esta marca, cualquier backtest que consulte la tabla usa datos del
    # futuro (sesgo look-ahead).
    is_forecast: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("meta.data_source.id")
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now
    )


class DataPointVintage(Base, Linaje):
    """Valor point-in-time de una serie (ALFRED): qué se sabía y cuándo.

    Cada fila registra el valor de una observación (`obs_date`) tal como
    se conocía a partir de una fecha de publicación (`vintage_date`). Así
    se pueden reconstruir los datos disponibles en cualquier momento del
    pasado (backtests macro sin sesgo de revisión).
    """

    __tablename__ = "data_point_vintage"
    __table_args__ = (
        UniqueConstraint("series_id", "obs_date", "vintage_date"),
        Index(
            "ix_macro_dpv_series_obs",
            "series_id",
            "obs_date",
        ),
        {"schema": "macro"},
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    series_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("macro.series.id"),
        nullable=False,
    )
    obs_date: Mapped[date] = mapped_column(Date, nullable=False)
    vintage_date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
