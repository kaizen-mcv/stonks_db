"""Derivados: snapshots de cadenas de opciones (silver).

yfinance solo da la cadena actual (sin histórico), así que el histórico
se acumula capturando una foto por día. Un registro = un contrato
(empresa × fecha × vencimiento × tipo × strike) en un snapshot.
"""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from stonks.db import Base
from stonks.models.linaje import Linaje, LinajeEjecucion


class OptionSnapshot(Base, Linaje):
    """Foto de un contrato de opción (call/put)."""

    __tablename__ = "option_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "snapshot_date", "expiry", "option_type", "strike"
        ),
        Index("ix_deriv_opt_company", "company_id", "snapshot_date"),
        {"schema": "deriv"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("equity.company.id"), nullable=False
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry: Mapped[date] = mapped_column(Date, nullable=False)
    option_type: Mapped[str] = mapped_column(String(1), nullable=False)  # C/P
    strike: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    last_price: Mapped[float | None] = mapped_column(Numeric(14, 4))
    bid: Mapped[float | None] = mapped_column(Numeric(14, 4))
    ask: Mapped[float | None] = mapped_column(Numeric(14, 4))
    # BigInteger por la misma razon que en `fund.nav_daily`: un dia de
    # panico puede pasar de 2.147 millones de contratos.
    volume: Mapped[int | None] = mapped_column(BigInteger)
    open_interest: Mapped[int | None] = mapped_column(Integer)
    implied_vol: Mapped[float | None] = mapped_column(Numeric(10, 6))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now
    )


class VolatilityIndex(Base, Linaje):
    """Índice de volatilidad de referencia."""

    __tablename__ = "volatility_index"
    __table_args__ = {"schema": "deriv"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    underlying: Mapped[str | None] = mapped_column(String(50))
    yfinance_ticker: Mapped[str] = mapped_column(String(30), nullable=False)


class VolatilityDaily(Base, LinajeEjecucion):
    """Precio diario de índice de volatilidad."""

    __tablename__ = "volatility_daily"
    __table_args__ = (
        UniqueConstraint("index_id", "date"),
        Index(
            "ix_deriv_vol_idx_date",
            "index_id",
            "date",
        ),
        Index("ix_deriv_vol_source", "source_id"),
        {"schema": "deriv"},
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    index_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("deriv.volatility_index.id"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[float | None] = mapped_column(Numeric(10, 4))
    high: Mapped[float | None] = mapped_column(Numeric(10, 4))
    low: Mapped[float | None] = mapped_column(Numeric(10, 4))
    close: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("meta.data_source.id")
    )


class FuturesContract(Base, Linaje):
    """Contrato de futuros (índice, bono, divisa)."""

    __tablename__ = "futures_contract"
    __table_args__ = {"schema": "deriv"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    underlying: Mapped[str | None] = mapped_column(String(50))
    category: Mapped[str | None] = mapped_column(String(30))
    yfinance_ticker: Mapped[str] = mapped_column(String(30), nullable=False)


class FuturesDaily(Base, LinajeEjecucion):
    """Precio diario de futuros."""

    __tablename__ = "futures_daily"
    __table_args__ = (
        UniqueConstraint("contract_id", "date"),
        Index(
            "ix_deriv_fut_contract_date",
            "contract_id",
            "date",
        ),
        Index("ix_deriv_fut_source", "source_id"),
        {"schema": "deriv"},
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    contract_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("deriv.futures_contract.id"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[float | None] = mapped_column(Numeric(20, 10))
    high: Mapped[float | None] = mapped_column(Numeric(20, 10))
    low: Mapped[float | None] = mapped_column(Numeric(20, 10))
    close: Mapped[float] = mapped_column(Numeric(20, 10), nullable=False)
    volume: Mapped[int | None] = mapped_column(BigInteger)
    source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("meta.data_source.id")
    )


class CotContract(Base, Linaje):
    """Contrato de futuros del informe COT de la CFTC.

    Catálogo de los contratos sobre los que la CFTC publica el
    Commitments of Traders. La clave natural es el código de mercado
    que asigna la propia CFTC.
    """

    __tablename__ = "cot_contract"
    __table_args__ = (
        Index("ix_deriv_cot_grupo", "commodity_group"),
        {"schema": "deriv"},
    )

    code: Mapped[str] = mapped_column(String(12), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    exchange: Mapped[str | None] = mapped_column(String(20))
    commodity_group: Mapped[str | None] = mapped_column(String(60))
    commodity_subgroup: Mapped[str | None] = mapped_column(String(80))
    contract_units: Mapped[str | None] = mapped_column(String(120))


class CotReport(Base, LinajeEjecucion):
    """Posicionamiento semanal declarado a la CFTC.

    Un registro = contrato × semana. Se guardan las posiciones
    "combinadas" (futuros y opciones agregados), que son las que se
    usan habitualmente para medir posicionamiento.

    Categorías: `comm` son coberturistas comerciales (productores y
    consumidores del subyacente), `noncomm` especuladores declarantes
    (fondos), y `nonrept` los pequeños operadores por debajo del umbral
    de declaración.
    """

    __tablename__ = "cot_report"
    __table_args__ = (
        UniqueConstraint("contract_code", "report_date"),
        Index("ix_deriv_cot_fecha", "report_date"),
        Index("ix_deriv_cot_source", "source_id"),
        {"schema": "deriv"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    contract_code: Mapped[str] = mapped_column(
        String(12),
        ForeignKey("deriv.cot_contract.code"),
        nullable=False,
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    open_interest: Mapped[int | None] = mapped_column(BigInteger)
    comm_long: Mapped[int | None] = mapped_column(BigInteger)
    comm_short: Mapped[int | None] = mapped_column(BigInteger)
    noncomm_long: Mapped[int | None] = mapped_column(BigInteger)
    noncomm_short: Mapped[int | None] = mapped_column(BigInteger)
    noncomm_spread: Mapped[int | None] = mapped_column(BigInteger)
    nonrept_long: Mapped[int | None] = mapped_column(BigInteger)
    nonrept_short: Mapped[int | None] = mapped_column(BigInteger)
    traders_total: Mapped[int | None] = mapped_column(Integer)
    source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("meta.data_source.id")
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now
    )
