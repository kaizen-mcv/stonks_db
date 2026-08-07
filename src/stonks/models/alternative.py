"""Modelos de datos alternativos: sentimiento, VIX."""

from datetime import date

from sqlalchemy import (
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from stonks.db import Base
from stonks.models.linaje import Linaje


class SentimentIndicator(Base, Linaje):
    """Definición de indicador de sentimiento."""

    __tablename__ = "sentiment_indicator"
    __table_args__ = {"schema": "alt"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)


class SentimentValue(Base, Linaje):
    """Valor diario de indicador de sentimiento."""

    __tablename__ = "sentiment_value"
    __table_args__ = (
        UniqueConstraint("indicator_id", "date"),
        {"schema": "alt"},
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    indicator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("alt.sentiment_indicator.id"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
