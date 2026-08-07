"""Calendario económico: publicaciones de datos macro.

El esquema `calendar` estaba declarado en `stonks.db.SCHEMAS` pero
nunca llegó a tener tablas. Se modela con la API de *releases* de FRED,
que es gratuita y publica tanto el catálogo de publicaciones (nóminas
no agrícolas, IPC, PIB, decisiones de la Fed…) como sus fechas pasadas
y futuras.

Saber **cuándo** se publica un dato es tan importante como el dato: es
lo que permite alinear una serie macro con el momento en que el mercado
la conoció, y evitar el sesgo look-ahead que ya corrige
`macro.data_point.is_forecast`.
"""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from stonks.db import Base
from stonks.models.linaje import Linaje, LinajeEjecucion


class Release(Base, LinajeEjecucion):
    """Publicación periódica de un organismo estadístico."""

    __tablename__ = "release"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id"),
        Index("ix_cal_release_country", "country_code"),
        {"schema": "calendar"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Identificador en la fuente (release_id de FRED, por ejemplo).
    external_id: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    country_code: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("ref.country.code")
    )
    # Organismo que publica (BLS, BEA, Federal Reserve, Eurostat...)
    agency: Mapped[str | None] = mapped_column(String(200))
    link: Mapped[str | None] = mapped_column(String(500))
    source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("meta.data_source.id")
    )


class ReleaseDate(Base, Linaje):
    """Fecha concreta en que una publicación sale o saldrá."""

    __tablename__ = "release_date"
    __table_args__ = (
        UniqueConstraint("release_id", "date"),
        Index("ix_cal_reldate_date", "date"),
        {"schema": "calendar"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    release_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("calendar.release.id"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    # True mientras la fecha esté anunciada pero no haya llegado.
    is_scheduled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now
    )
