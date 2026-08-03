"""Fetcher de índices de volatilidad via yfinance.

VIX, VVIX, VXN, MOVE y variantes.
"""

import yfinance as yf
from sqlalchemy import and_

import stonks.models  # noqa: F401
from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.deriv import (
    VolatilityDaily,
    VolatilityIndex,
)
from stonks.models.meta import DataSource

# (código, nombre, subyacente, ticker_yfinance)
VOLATILITY_INDICES = [
    ("VIX", "CBOE Volatility Index", "S&P 500", "^VIX"),
    ("VVIX", "CBOE VVIX", "VIX", "^VVIX"),
    (
        "VXN",
        "CBOE NASDAQ Volatility",
        "NASDAQ 100",
        "^VXN",
    ),
    (
        "RVX",
        "CBOE Russell 2000 Volatility",
        "Russell 2000",
        "^RVX",
    ),
    (
        "OVX",
        "CBOE Crude Oil Volatility",
        "Crude Oil",
        "^OVX",
    ),
    (
        "GVZ",
        "CBOE Gold Volatility",
        "Gold",
        "^GVZ",
    ),
    (
        "EVZ",
        "CBOE Euro Currency Volatility",
        "EUR/USD",
        "^EVZ",
    ),
    (
        "VIX9D",
        "CBOE VIX 9-Day",
        "S&P 500",
        "^VIX9D",
    ),
    (
        "VIX3M",
        "CBOE VIX 3-Month",
        "S&P 500",
        "^VIX3M",
    ),
    (
        "VIX6M",
        "CBOE VIX 6-Month",
        "S&P 500",
        "^VIX6M",
    ),
    (
        "SKEW",
        "CBOE SKEW Index",
        "S&P 500",
        "^SKEW",
    ),
    (
        "VIX_FUT",
        "VIX Futures Front Month",
        "VIX",
        "VX=F",
    ),
]


class VolatilityFetcher(BaseFetcher):
    """Descarga índices de volatilidad."""

    SOURCE_NAME = "yfinance"
    DOMAIN = "deriv"
    RATE_LIMIT = 0.5

    def seed_indices(self) -> int:
        """Insertar índices de volatilidad."""
        session = get_session()
        count = 0
        try:
            for code, name, underlying, yf_tk in VOLATILITY_INDICES:
                if session.query(VolatilityIndex).filter_by(code=code).first():
                    continue
                session.add(
                    VolatilityIndex(
                        code=code,
                        name=name,
                        underlying=underlying,
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
        """Descargar precios de volatilidad."""
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
                indices = [
                    session.query(VolatilityIndex).filter_by(code=code).first()
                ]
            else:
                indices = session.query(VolatilityIndex).all()

            for idx in indices:
                if not idx or not idx.yfinance_ticker:
                    continue

                logger.info(
                    "  Vol: %s (%s)...",
                    idx.name,
                    idx.yfinance_ticker,
                )
                try:
                    t = yf.Ticker(idx.yfinance_ticker)
                    df = t.history(period=period)
                except Exception as e:
                    logger.warning(
                        "  Error %s: %s",
                        idx.code,
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
                        session.query(VolatilityDaily)
                        .filter(
                            and_(
                                VolatilityDaily.index_id == idx.id,
                                VolatilityDaily.date == dt,
                            )
                        )
                        .first()
                    )
                    if exists:
                        continue

                    session.add(
                        VolatilityDaily(
                            index_id=idx.id,
                            date=dt,
                            open=row.get("Open"),
                            high=row.get("High"),
                            low=row.get("Low"),
                            close=float(close),
                            source_id=src_id,
                        )
                    )
                    stats["inserted"] += 1

                session.commit()

            self._finish_run(run_id, "success", **stats)
        except Exception as e:
            session.rollback()
            stats["errors"] += 1
            logger.error("Error volatilidad: %s", e)
            self._finish_run(
                run_id,
                "failed",
                **stats,
                error_log={"msg": str(e)},
            )
        finally:
            session.close()

        return stats
