"""Modelos de renta fija: bonos, curvas, ratings."""

from datetime import date

from sqlalchemy import (
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


class BondIssuer(Base):
    """Emisor de bonos."""

    __tablename__ = "bond_issuer"
    __table_args__ = (
        UniqueConstraint("name", "country_code", "issuer_type"),
        {"schema": "fi"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(String(300))
    issuer_type: Mapped[str] = mapped_column(String(20), nullable=False)
    country_code: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("ref.country.code")
    )


class CreditRating(Base):
    """Rating crediticio."""

    __tablename__ = "credit_rating"
    __table_args__ = (
        UniqueConstraint("issuer_id", "agency", "rating_date"),
        {"schema": "fi"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issuer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("fi.bond_issuer.id"),
        nullable=False,
    )
    agency: Mapped[str] = mapped_column(String(20), nullable=False)
    rating: Mapped[str] = mapped_column(String(10), nullable=False)
    outlook: Mapped[str | None] = mapped_column(String(20))
    rating_date: Mapped[date] = mapped_column(Date, nullable=False)
    previous_rating: Mapped[str | None] = mapped_column(String(10))


class YieldCurve(Base):
    """Punto de curva de tipos por país y fecha."""

    __tablename__ = "yield_curve"
    __table_args__ = (
        UniqueConstraint(
            "country_code",
            "date",
            "maturity_months",
        ),
        Index(
            "ix_fi_yc_country_date",
            "country_code",
            "date",
        ),
        {"schema": "fi"},
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    country_code: Mapped[str] = mapped_column(
        String(3),
        ForeignKey("ref.country.code"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    maturity_months: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    yield_pct: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("meta.data_source.id")
    )


class Bond(Base):
    """Bono individual."""

    __tablename__ = "bond"
    __table_args__ = {"schema": "fi"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issuer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("fi.bond_issuer.id")
    )
    isin: Mapped[str | None] = mapped_column(String(12), unique=True)
    name: Mapped[str | None] = mapped_column(String(300))
    coupon_rate: Mapped[float | None] = mapped_column(Numeric(8, 4))
    coupon_frequency: Mapped[int | None] = mapped_column(SmallInteger)
    maturity_date: Mapped[date | None] = mapped_column(Date)
    issue_date: Mapped[date | None] = mapped_column(Date)
    face_value: Mapped[float | None] = mapped_column(Numeric(14, 2))
    currency_code: Mapped[str | None] = mapped_column(String(3))
    bond_type: Mapped[str | None] = mapped_column(String(30))
    is_callable: Mapped[bool] = mapped_column(Boolean, default=False)
