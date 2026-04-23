"""Modelos de perfiles de país."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from stonks.db import Base


class CountryProfile(Base):
    """Perfil económico de un país."""

    __tablename__ = "profile"
    __table_args__ = {"schema": "country"}

    country_code: Mapped[str] = mapped_column(
        String(3),
        ForeignKey("ref.country.code"),
        primary_key=True,
    )
    population: Mapped[int | None] = mapped_column(BigInteger)
    population_year: Mapped[int | None] = mapped_column(SmallInteger)
    gdp_usd: Mapped[float | None] = mapped_column(Numeric(18, 2))
    gdp_per_capita_usd: Mapped[float | None] = mapped_column(Numeric(12, 2))
    hdi: Mapped[float | None] = mapped_column(Numeric(5, 4))
    gini_index: Mapped[float | None] = mapped_column(Numeric(5, 2))
    ease_of_business_rank: Mapped[int | None] = mapped_column(SmallInteger)
    political_stability_index: Mapped[float | None] = mapped_column(
        Numeric(6, 4)
    )
    last_updated: Mapped[datetime | None] = mapped_column(DateTime)


class TaxRate(Base):
    """Tipos impositivos por país y año."""

    __tablename__ = "tax_rate"
    __table_args__ = (
        UniqueConstraint("country_code", "year"),
        {"schema": "country"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country_code: Mapped[str] = mapped_column(
        String(3),
        ForeignKey("ref.country.code"),
        nullable=False,
    )
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    corporate_tax_rate: Mapped[float | None] = mapped_column(Numeric(6, 3))
    top_income_tax_rate: Mapped[float | None] = mapped_column(Numeric(6, 3))
    vat_rate: Mapped[float | None] = mapped_column(Numeric(6, 3))
    capital_gains_tax_rate: Mapped[float | None] = mapped_column(Numeric(6, 3))


class Demographics(Base):
    """Datos demográficos por país y año."""

    __tablename__ = "demographics"
    __table_args__ = (
        UniqueConstraint("country_code", "year"),
        {"schema": "country"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country_code: Mapped[str] = mapped_column(
        String(3),
        ForeignKey("ref.country.code"),
        nullable=False,
    )
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    total_population: Mapped[int | None] = mapped_column(BigInteger)
    median_age: Mapped[float | None] = mapped_column(Numeric(5, 2))
    urban_population_pct: Mapped[float | None] = mapped_column(Numeric(6, 3))
    life_expectancy: Mapped[float | None] = mapped_column(Numeric(5, 2))
    fertility_rate: Mapped[float | None] = mapped_column(Numeric(4, 2))
    labor_force: Mapped[int | None] = mapped_column(BigInteger)
