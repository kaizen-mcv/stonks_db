"""Modelos de renta variable: empresas, precios, fundamentales."""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
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


class Company(Base):
    """Empresa cotizada."""

    __tablename__ = "company"
    __table_args__ = (
        UniqueConstraint("ticker", "exchange_id"),
        Index("ix_eq_company_ticker", "ticker"),
        Index("ix_eq_company_isin", "isin"),
        Index("ix_eq_company_country", "country_code"),
        Index("ix_eq_company_sector", "sector_id"),
        {"schema": "equity"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    isin: Mapped[str | None] = mapped_column(String(12))
    exchange_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ref.exchange.id")
    )
    sector_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ref.sector.id")
    )
    country_code: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("ref.country.code")
    )
    currency_code: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("ref.currency.code")
    )
    market_cap_usd: Mapped[float | None] = mapped_column(Numeric(18, 2))
    shares_outstanding: Mapped[int | None] = mapped_column(BigInteger)
    ipo_date: Mapped[date | None] = mapped_column(Date)
    delisted_date: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    website: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    employees: Mapped[int | None] = mapped_column(Integer)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now
    )


class PriceDaily(Base):
    """Precio diario OHLCV."""

    __tablename__ = "price_daily"
    __table_args__ = (
        UniqueConstraint("company_id", "date"),
        Index(
            "ix_eq_price_company_date",
            "company_id",
            "date",
        ),
        {"schema": "equity"},
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("equity.company.id"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[float | None] = mapped_column(Numeric(14, 4))
    high: Mapped[float | None] = mapped_column(Numeric(14, 4))
    low: Mapped[float | None] = mapped_column(Numeric(14, 4))
    close: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    adj_close: Mapped[float | None] = mapped_column(Numeric(14, 4))
    volume: Mapped[int | None] = mapped_column(BigInteger)
    source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("meta.data_source.id")
    )


class IncomeStatement(Base):
    """Cuenta de resultados."""

    __tablename__ = "income_statement"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "fiscal_year",
            "fiscal_quarter",
        ),
        {"schema": "equity"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("equity.company.id"),
        nullable=False,
    )
    fiscal_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    fiscal_quarter: Mapped[int | None] = mapped_column(SmallInteger)
    period_end_date: Mapped[date | None] = mapped_column(Date)
    currency_code: Mapped[str | None] = mapped_column(String(3))
    revenue: Mapped[float | None] = mapped_column(Numeric(18, 2))
    cost_of_revenue: Mapped[float | None] = mapped_column(Numeric(18, 2))
    gross_profit: Mapped[float | None] = mapped_column(Numeric(18, 2))
    operating_expenses: Mapped[float | None] = mapped_column(Numeric(18, 2))
    operating_income: Mapped[float | None] = mapped_column(Numeric(18, 2))
    interest_expense: Mapped[float | None] = mapped_column(Numeric(18, 2))
    pretax_income: Mapped[float | None] = mapped_column(Numeric(18, 2))
    income_tax: Mapped[float | None] = mapped_column(Numeric(18, 2))
    net_income: Mapped[float | None] = mapped_column(Numeric(18, 2))
    eps_basic: Mapped[float | None] = mapped_column(Numeric(10, 4))
    eps_diluted: Mapped[float | None] = mapped_column(Numeric(10, 4))
    shares_basic: Mapped[int | None] = mapped_column(BigInteger)
    shares_diluted: Mapped[int | None] = mapped_column(BigInteger)
    ebitda: Mapped[float | None] = mapped_column(Numeric(18, 2))
    source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("meta.data_source.id")
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now
    )


class BalanceSheet(Base):
    """Balance de situación."""

    __tablename__ = "balance_sheet"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "fiscal_year",
            "fiscal_quarter",
        ),
        {"schema": "equity"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("equity.company.id"),
        nullable=False,
    )
    fiscal_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    fiscal_quarter: Mapped[int | None] = mapped_column(SmallInteger)
    period_end_date: Mapped[date | None] = mapped_column(Date)
    currency_code: Mapped[str | None] = mapped_column(String(3))
    cash_and_equivalents: Mapped[float | None] = mapped_column(Numeric(18, 2))
    short_term_investments: Mapped[float | None] = mapped_column(
        Numeric(18, 2)
    )
    total_current_assets: Mapped[float | None] = mapped_column(Numeric(18, 2))
    property_plant_equipment: Mapped[float | None] = mapped_column(
        Numeric(18, 2)
    )
    goodwill: Mapped[float | None] = mapped_column(Numeric(18, 2))
    intangible_assets: Mapped[float | None] = mapped_column(Numeric(18, 2))
    total_assets: Mapped[float | None] = mapped_column(Numeric(18, 2))
    accounts_payable: Mapped[float | None] = mapped_column(Numeric(18, 2))
    short_term_debt: Mapped[float | None] = mapped_column(Numeric(18, 2))
    total_current_liabilities: Mapped[float | None] = mapped_column(
        Numeric(18, 2)
    )
    long_term_debt: Mapped[float | None] = mapped_column(Numeric(18, 2))
    total_liabilities: Mapped[float | None] = mapped_column(Numeric(18, 2))
    total_stockholders_equity: Mapped[float | None] = mapped_column(
        Numeric(18, 2)
    )
    retained_earnings: Mapped[float | None] = mapped_column(Numeric(18, 2))
    total_equity: Mapped[float | None] = mapped_column(Numeric(18, 2))
    source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("meta.data_source.id")
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now
    )


class CashFlow(Base):
    """Estado de flujos de efectivo."""

    __tablename__ = "cash_flow"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "fiscal_year",
            "fiscal_quarter",
        ),
        {"schema": "equity"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("equity.company.id"),
        nullable=False,
    )
    fiscal_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    fiscal_quarter: Mapped[int | None] = mapped_column(SmallInteger)
    period_end_date: Mapped[date | None] = mapped_column(Date)
    currency_code: Mapped[str | None] = mapped_column(String(3))
    operating_cash_flow: Mapped[float | None] = mapped_column(Numeric(18, 2))
    capital_expenditure: Mapped[float | None] = mapped_column(Numeric(18, 2))
    free_cash_flow: Mapped[float | None] = mapped_column(Numeric(18, 2))
    dividends_paid: Mapped[float | None] = mapped_column(Numeric(18, 2))
    share_buyback: Mapped[float | None] = mapped_column(Numeric(18, 2))
    debt_issued: Mapped[float | None] = mapped_column(Numeric(18, 2))
    debt_repaid: Mapped[float | None] = mapped_column(Numeric(18, 2))
    investing_cash_flow: Mapped[float | None] = mapped_column(Numeric(18, 2))
    financing_cash_flow: Mapped[float | None] = mapped_column(Numeric(18, 2))
    net_change_cash: Mapped[float | None] = mapped_column(Numeric(18, 2))
    source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("meta.data_source.id")
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now
    )


class Dividend(Base):
    """Dividendos."""

    __tablename__ = "dividend"
    __table_args__ = (
        UniqueConstraint("company_id", "ex_date", "dividend_type"),
        {"schema": "equity"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("equity.company.id"),
        nullable=False,
    )
    ex_date: Mapped[date] = mapped_column(Date, nullable=False)
    pay_date: Mapped[date | None] = mapped_column(Date)
    record_date: Mapped[date | None] = mapped_column(Date)
    amount: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False)
    currency_code: Mapped[str | None] = mapped_column(String(3))
    dividend_type: Mapped[str | None] = mapped_column(String(20))


class Split(Base):
    """Stock splits."""

    __tablename__ = "split"
    __table_args__ = (
        UniqueConstraint("company_id", "date"),
        {"schema": "equity"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("equity.company.id"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    ratio_from: Mapped[float | None] = mapped_column(Numeric(10, 4))
    ratio_to: Mapped[float | None] = mapped_column(Numeric(10, 4))


class MarketIndex(Base):
    """Índice de mercado."""

    __tablename__ = "market_index"
    __table_args__ = {"schema": "equity"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    country_code: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("ref.country.code")
    )
    exchange_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ref.exchange.id")
    )
    currency_code: Mapped[str | None] = mapped_column(String(3))
    description: Mapped[str | None] = mapped_column(Text)


class IndexPrice(Base):
    """Precio diario de un índice."""

    __tablename__ = "index_price"
    __table_args__ = (
        UniqueConstraint("index_id", "date"),
        Index(
            "ix_eq_idxprice_idx_date",
            "index_id",
            "date",
        ),
        {"schema": "equity"},
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    index_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("equity.market_index.id"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[float | None] = mapped_column(Numeric(14, 4))
    high: Mapped[float | None] = mapped_column(Numeric(14, 4))
    low: Mapped[float | None] = mapped_column(Numeric(14, 4))
    close: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    volume: Mapped[int | None] = mapped_column(BigInteger)
