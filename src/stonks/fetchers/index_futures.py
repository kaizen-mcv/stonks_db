"""Fetcher de futuros sobre índices, bonos y divisas
via yfinance."""

import yfinance as yf
from sqlalchemy import and_

import stonks.models  # noqa: F401
from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.deriv import (
    FuturesContract,
    FuturesDaily,
)
from stonks.models.meta import DataSource

# (código, nombre, subyacente, categoría, ticker_yf)
INDEX_FUTURES = [
    # Equity
    (
        "ES",
        "E-Mini S&P 500",
        "S&P 500",
        "equity",
        "ES=F",
    ),
    (
        "NQ",
        "E-Mini NASDAQ 100",
        "NASDAQ 100",
        "equity",
        "NQ=F",
    ),
    (
        "YM",
        "E-Mini Dow Jones",
        "Dow Jones",
        "equity",
        "YM=F",
    ),
    (
        "RTY",
        "E-Mini Russell 2000",
        "Russell 2000",
        "equity",
        "RTY=F",
    ),
    (
        "NKD",
        "Nikkei 225 Dollar",
        "Nikkei 225",
        "equity",
        "NKD=F",
    ),
    # Renta fija
    (
        "ZN",
        "10-Year Treasury Note",
        "UST 10Y",
        "fixed_income",
        "ZN=F",
    ),
    (
        "ZB",
        "30-Year Treasury Bond",
        "UST 30Y",
        "fixed_income",
        "ZB=F",
    ),
    (
        "ZF",
        "5-Year Treasury Note",
        "UST 5Y",
        "fixed_income",
        "ZF=F",
    ),
    (
        "ZT",
        "2-Year Treasury Note",
        "UST 2Y",
        "fixed_income",
        "ZT=F",
    ),
    # Divisas
    (
        "DX",
        "US Dollar Index",
        "USD",
        "currency",
        "DX=F",
    ),
    (
        "6E",
        "Euro FX Future",
        "EUR/USD",
        "currency",
        "6E=F",
    ),
    (
        "6J",
        "Japanese Yen Future",
        "USD/JPY",
        "currency",
        "6J=F",
    ),
    (
        "6B",
        "British Pound Future",
        "GBP/USD",
        "currency",
        "6B=F",
    ),
    (
        "6A",
        "Australian Dollar Future",
        "AUD/USD",
        "currency",
        "6A=F",
    ),
    (
        "6C",
        "Canadian Dollar Future",
        "USD/CAD",
        "currency",
        "6C=F",
    ),
    (
        "6S",
        "Swiss Franc Future",
        "USD/CHF",
        "currency",
        "6S=F",
    ),
]


class IndexFuturesFetcher(BaseFetcher):
    """Descarga precios de futuros."""

    SOURCE_NAME = "yfinance"
    DOMAIN = "deriv"
    RATE_LIMIT = 0.5

    def seed_contracts(self) -> int:
        """Insertar contratos de futuros."""
        session = get_session()
        count = 0
        try:
            for code, name, under, cat, yf_tk in INDEX_FUTURES:
                if session.query(FuturesContract).filter_by(code=code).first():
                    continue
                session.add(
                    FuturesContract(
                        code=code,
                        name=name,
                        underlying=under,
                        category=cat,
                        yfinance_ticker=yf_tk,
                    )
                )
                count += 1
            session.commit()
        finally:
            session.close()
        return count

    def fetch_prices(
        self,
        code: str | None = None,
        period: str = "max",
    ) -> dict[str, int]:
        """Descargar precios de futuros."""
        run_id = self._start_run(params={"code": code, "period": period})
        stats = {
            "fetched": 0,
            "inserted": 0,
            "errors": 0,
        }
        session = get_session()

        try:
            src = (
                session.query(DataSource)
                .filter_by(name=self.SOURCE_NAME)
                .first()
            )
            src_id = src.id if src else None

            if code:
                contracts = [
                    session.query(FuturesContract).filter_by(code=code).first()
                ]
            else:
                contracts = session.query(FuturesContract).all()

            for contract in contracts:
                if not contract or not contract.yfinance_ticker:
                    continue

                logger.info(
                    "  Futures: %s (%s)...",
                    contract.name,
                    contract.yfinance_ticker,
                )
                try:
                    t = yf.Ticker(contract.yfinance_ticker)
                    df = t.history(period=period)
                except Exception as e:
                    logger.warning(
                        "  Error %s: %s",
                        contract.code,
                        e,
                    )
                    stats["errors"] += 1
                    continue

                if df.empty:
                    continue

                for ts, row in df.iterrows():
                    dt = ts.date()
                    close = row.get("Close")
                    if close is None or close != close:
                        continue

                    stats["fetched"] += 1
                    exists = (
                        session.query(FuturesDaily)
                        .filter(
                            and_(
                                FuturesDaily.contract_id == contract.id,
                                FuturesDaily.date == dt,
                            )
                        )
                        .first()
                    )
                    if exists:
                        continue

                    vol = row.get("Volume")
                    session.add(
                        FuturesDaily(
                            contract_id=contract.id,
                            date=dt,
                            open=row.get("Open"),
                            high=row.get("High"),
                            low=row.get("Low"),
                            close=float(close),
                            volume=(
                                int(float(vol)) if vol and vol == vol else None
                            ),
                            source_id=src_id,
                        )
                    )
                    stats["inserted"] += 1

                session.commit()

            self._finish_run(run_id, "success", **stats)
        except Exception as e:
            session.rollback()
            stats["errors"] += 1
            logger.error("Error futures: %s", e)
            self._finish_run(
                run_id,
                "failed",
                **stats,
                error_log={"msg": str(e)},
            )
        finally:
            session.close()

        return stats
