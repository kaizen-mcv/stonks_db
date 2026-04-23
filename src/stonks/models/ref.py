"""Modelos de referencia: países, divisas, bolsas, sectores."""

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column

from stonks.db import Base


class Country(Base):
    """País (ISO 3166-1)."""

    __tablename__ = "country"
    __table_args__ = {"schema": "ref"}

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    code_alpha2: Mapped[str | None] = mapped_column(String(2), unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    region: Mapped[str | None] = mapped_column(String(100))
    sub_region: Mapped[str | None] = mapped_column(String(100))
    income_group: Mapped[str | None] = mapped_column(String(50))
    currency_code: Mapped[str | None] = mapped_column(String(3))
    capital: Mapped[str | None] = mapped_column(String(100))
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))


class Currency(Base):
    """Divisa (ISO 4217)."""

    __tablename__ = "currency"
    __table_args__ = {"schema": "ref"}

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(100))
    symbol: Mapped[str | None] = mapped_column(String(10))
    is_major: Mapped[bool] = mapped_column(Boolean, default=False)
    decimal_places: Mapped[int] = mapped_column(SmallInteger, default=2)


class Exchange(Base):
    """Bolsa de valores."""

    __tablename__ = "exchange"
    __table_args__ = {"schema": "ref"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mic: Mapped[str | None] = mapped_column(String(10), unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(50))
    country_code: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("ref.country.code")
    )
    city: Mapped[str | None] = mapped_column(String(100))
    timezone: Mapped[str | None] = mapped_column(String(50))
    currency_code: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("ref.currency.code")
    )
    open_time: Mapped[str | None] = mapped_column(Time)
    close_time: Mapped[str | None] = mapped_column(Time)
    website: Mapped[str | None] = mapped_column(String(300))


class Sector(Base):
    """Clasificación GICS (sectores/industrias)."""

    __tablename__ = "sector"
    __table_args__ = {"schema": "ref"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gics_code: Mapped[str | None] = mapped_column(String(10), unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ref.sector.id")
    )
    level: Mapped[int | None] = mapped_column(SmallInteger)
