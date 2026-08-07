"""Modelos de referencia: países, divisas, bolsas, sectores,
catálogo HS."""

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column

from stonks.db import Base


class Area(Base):
    """Entidad geográfica: superset de `ref.country`.

    Las fuentes de comercio internacional (UN Comtrade, WITS, IMF DOTS)
    no informan solo países ISO: usan agregados regionales ("WLD" mundo,
    "ECS" Europa y Asia Central) y entidades históricas desaparecidas
    ("CSK" Checoslovaquia, "DDR" RDA, "YUG" Yugoslavia).

    Este catálogo permite que `trade.flow` valide tanto el declarante
    como el socio contra una clave foránea real, en lugar de dejar el
    socio como texto libre. `country_code` enlaza con `ref.country`
    cuando el área es un país ISO vigente.
    """

    __tablename__ = "area"
    __table_args__ = (
        Index("ix_ref_area_country", "country_code"),
        {"schema": "ref"},
    )

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # country | aggregate | historical | unknown
    area_type: Mapped[str] = mapped_column(String(20), nullable=False)
    country_code: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("ref.country.code")
    )
    notes: Mapped[str | None] = mapped_column(String(300))


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
    __table_args__ = (
        Index("ix_ref_exchange_country", "country_code"),
        Index("ix_ref_exchange_currency", "currency_code"),
        {"schema": "ref"},
    )

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
    __table_args__ = (
        Index("ix_ref_sector_parent", "parent_id"),
        {"schema": "ref"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gics_code: Mapped[str | None] = mapped_column(String(10), unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ref.sector.id")
    )
    level: Mapped[int | None] = mapped_column(SmallInteger)


class HsProduct(Base):
    """Catálogo de códigos HS (Sistema Armonizado).

    Códigos de 2-4-6 dígitos con su descripción. Sirve
    para dar nombre a `trade.flow.product_code` cuando se
    carga comercio por producto (UN Comtrade).
    `level` = número de dígitos.
    """

    __tablename__ = "hs_product"
    __table_args__ = {"schema": "ref"}

    code: Mapped[str] = mapped_column(String(6), primary_key=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    parent_code: Mapped[str | None] = mapped_column(String(6))


class LegalEntity(Base):
    """Entidad legal identificada por LEI (GLEIF).

    El LEI (Legal Entity Identifier, ISO 17442) es el único
    identificador global, público y gratuito de entidades jurídicas.
    Resuelve el problema de identidad que tenía el modelo, donde las
    empresas se cruzaban por `ticker`, que no es único entre mercados
    ni estable en el tiempo.

    También es la clave para cruzar `stonks_db` con otras bases del
    servidor (borme_db, supliers_db), que comparten el mismo estándar.
    """

    __tablename__ = "legal_entity"
    __table_args__ = (
        Index("ix_ref_lei_country", "country_code"),
        Index("ix_ref_lei_name", "legal_name"),
        {"schema": "ref"},
    )

    lei: Mapped[str] = mapped_column(String(20), primary_key=True)
    legal_name: Mapped[str] = mapped_column(String(500), nullable=False)
    country_code: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("ref.country.code")
    )
    legal_jurisdiction: Mapped[str | None] = mapped_column(String(10))
    entity_status: Mapped[str | None] = mapped_column(String(20))
    entity_category: Mapped[str | None] = mapped_column(String(40))
    # LEI de la matriz directa, cuando GLEIF lo publica.
    parent_lei: Mapped[str | None] = mapped_column(String(20))
    registration_status: Mapped[str | None] = mapped_column(String(30))
    city: Mapped[str | None] = mapped_column(String(120))
