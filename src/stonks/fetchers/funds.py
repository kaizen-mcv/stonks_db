"""Fetcher de ETFs y fondos via yfinance."""

from datetime import date, datetime

import yfinance as yf
from sqlalchemy import and_

from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
import stonks.models  # noqa: F401
from stonks.models.fund import Fund, NavDaily
from stonks.models.meta import DataSource

# ETFs principales globales
ETFS = [
    # US Broad Market
    ("SPY", "SPDR S&P 500 ETF", "etf",
     "equity", "US", "index", "State Street"),
    ("QQQ", "Invesco QQQ Trust", "etf",
     "equity", "US", "index", "Invesco"),
    ("VTI", "Vanguard Total Stock Market", "etf",
     "equity", "US", "index", "Vanguard"),
    ("IWM", "iShares Russell 2000", "etf",
     "equity", "US", "index", "iShares"),
    ("VOO", "Vanguard S&P 500", "etf",
     "equity", "US", "index", "Vanguard"),
    # International
    ("EFA", "iShares MSCI EAFE", "etf",
     "equity", "Developed ex-US", "index",
     "iShares"),
    ("VWO", "Vanguard FTSE Emerging Markets", "etf",
     "equity", "Emerging Markets", "index",
     "Vanguard"),
    ("EEM", "iShares MSCI Emerging Markets", "etf",
     "equity", "Emerging Markets", "index",
     "iShares"),
    ("VEA", "Vanguard FTSE Developed Markets", "etf",
     "equity", "Developed ex-US", "index",
     "Vanguard"),
    # Fixed Income
    ("AGG", "iShares Core US Aggregate Bond", "etf",
     "fixed_income", "US", "index", "iShares"),
    ("TLT", "iShares 20+ Year Treasury Bond", "etf",
     "fixed_income", "US", "index", "iShares"),
    ("HYG", "iShares iBoxx High Yield Corp", "etf",
     "fixed_income", "US", "index", "iShares"),
    ("LQD", "iShares iBoxx IG Corporate Bond", "etf",
     "fixed_income", "US", "index", "iShares"),
    ("BND", "Vanguard Total Bond Market", "etf",
     "fixed_income", "US", "index", "Vanguard"),
    # Commodities
    ("GLD", "SPDR Gold Shares", "etf",
     "commodity", "Global", "index", "State Street"),
    ("SLV", "iShares Silver Trust", "etf",
     "commodity", "Global", "index", "iShares"),
    ("USO", "United States Oil Fund", "etf",
     "commodity", "Global", "index", "USCF"),
    # Sector
    ("XLK", "Technology Select Sector SPDR", "etf",
     "equity", "US", "sector", "State Street"),
    ("XLF", "Financial Select Sector SPDR", "etf",
     "equity", "US", "sector", "State Street"),
    ("XLE", "Energy Select Sector SPDR", "etf",
     "equity", "US", "sector", "State Street"),
    ("XLV", "Health Care Select Sector SPDR", "etf",
     "equity", "US", "sector", "State Street"),
    # Multi-asset / Global
    ("VT", "Vanguard Total World Stock", "etf",
     "equity", "Global", "index", "Vanguard"),
    ("ACWI", "iShares MSCI ACWI", "etf",
     "equity", "Global", "index", "iShares"),
    # Real Estate
    ("VNQ", "Vanguard Real Estate", "etf",
     "equity", "US", "sector", "Vanguard"),
    ("VNQI", "Vanguard Global ex-US RE", "etf",
     "equity", "Global ex-US", "sector",
     "Vanguard"),
]


class FundFetcher(BaseFetcher):
    """Descarga datos de ETFs/fondos."""

    SOURCE_NAME = "yfinance"
    DOMAIN = "fund"
    RATE_LIMIT = 0.5

    def seed_funds(self) -> int:
        """Insertar ETFs de referencia."""
        session = get_session()
        count = 0
        try:
            for (ticker, name, ftype, aclass,
                 geo, strategy, provider) in ETFS:
                if session.query(Fund).filter_by(
                    ticker=ticker
                ).first():
                    continue
                session.add(Fund(
                    ticker=ticker,
                    name=name,
                    fund_type=ftype,
                    asset_class=aclass,
                    geography=geo,
                    strategy=strategy,
                    provider=provider,
                ))
                count += 1
            session.commit()
        finally:
            session.close()
        return count

    def fetch_nav(
        self,
        ticker: str | None = None,
        period: str = "5y",
    ) -> dict[str, int]:
        """Descargar NAV histórico."""
        run_id = self._start_run(params={
            "ticker": ticker, "period": period,
        })
        stats = {
            "fetched": 0, "inserted": 0,
            "updated": 0, "errors": 0,
        }
        session = get_session()

        try:
            src = session.query(DataSource).filter_by(
                name=self.SOURCE_NAME
            ).first()
            src_id = src.id if src else None

            if ticker:
                funds = [
                    session.query(Fund).filter_by(
                        ticker=ticker
                    ).first()
                ]
            else:
                funds = session.query(Fund).all()

            for fund in funds:
                if not fund or not fund.ticker:
                    continue

                logger.info(
                    "  ETF: %s...", fund.ticker
                )
                try:
                    t = yf.Ticker(fund.ticker)
                    df = t.history(period=period)
                except Exception as e:
                    logger.warning(
                        "  Error %s: %s",
                        fund.ticker, e,
                    )
                    stats["errors"] += 1
                    continue

                if df.empty:
                    continue

                # Actualizar expense ratio si hay info
                try:
                    info = t.info
                    if info:
                        er = info.get(
                            "annualReportExpenseRatio"
                        )
                        if er:
                            fund.expense_ratio = er
                        aum = info.get("totalAssets")
                        if aum:
                            fund.aum_usd = aum
                except Exception:
                    pass

                for idx, row in df.iterrows():
                    dt = idx.date()
                    close = row.get("Close")
                    if close is None:
                        continue

                    stats["fetched"] += 1
                    exists = session.query(
                        NavDaily
                    ).filter(and_(
                        NavDaily.fund_id == fund.id,
                        NavDaily.date == dt,
                    )).first()

                    if exists:
                        continue

                    session.add(NavDaily(
                        fund_id=fund.id,
                        date=dt,
                        nav=float(close),
                        volume=int(
                            row.get("Volume", 0)
                        ) or None,
                    ))
                    stats["inserted"] += 1

                session.commit()

            self._finish_run(
                run_id, "success", **stats
            )
        except Exception as e:
            session.rollback()
            stats["errors"] += 1
            logger.error("Error funds: %s", e)
            self._finish_run(
                run_id, "failed", **stats,
                error_log={"msg": str(e)},
            )
        finally:
            session.close()

        return stats
