"""Fetcher de curvas de tipos via yfinance
(Treasury yields US)."""

import yfinance as yf
from sqlalchemy import and_

import stonks.models  # noqa: F401
from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.fixed_income import YieldCurve
from stonks.models.meta import DataSource

# Tickers de Treasury yields en yfinance
# maturity_months -> ticker
US_TREASURY_TICKERS = {
    1: "^IRX",  # 13-week (3 month approx)
    3: "^IRX",  # 13-week T-Bill
    6: None,  # no ticker directo
    12: None,
    24: "^FVX",  # 5-year (aprox, usaremos 2Y real)
    60: "^FVX",  # 5-Year Treasury Yield
    120: "^TNX",  # 10-Year Treasury Yield
    360: "^TYX",  # 30-Year Treasury Yield
}

# Usamos los tickers reales disponibles
YIELD_TICKERS = [
    ("^IRX", 3, "USA"),  # 3-month T-Bill
    ("^FVX", 60, "USA"),  # 5-year Treasury
    ("^TNX", 120, "USA"),  # 10-year Treasury
    ("^TYX", 360, "USA"),  # 30-year Treasury
]


class YieldCurveFetcher(BaseFetcher):
    """Descarga yields de bonos del tesoro US."""

    SOURCE_NAME = "yfinance"
    DOMAIN = "fi"
    RATE_LIMIT = 0.5

    def fetch_us_yields(self, period: str = "5y") -> dict[str, int]:
        """Descargar yields del Treasury US."""
        run_id = self._start_run(
            params={
                "type": "us_treasury",
                "period": period,
            }
        )
        stats = {
            "fetched": 0,
            "inserted": 0,
            "updated": 0,
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

            for ticker, maturity, country in YIELD_TICKERS:
                logger.info(
                    "  Yield %s (%d meses)...",
                    ticker,
                    maturity,
                )
                try:
                    t = yf.Ticker(ticker)
                    df = t.history(period=period)
                except Exception as e:
                    logger.warning("  Error %s: %s", ticker, e)
                    stats["errors"] += 1
                    continue

                if df.empty:
                    continue

                for idx, row in df.iterrows():
                    dt = idx.date()
                    close_val = row.get("Close")
                    if close_val is None or (close_val != close_val):
                        continue

                    stats["fetched"] += 1
                    exists = (
                        session.query(YieldCurve)
                        .filter(
                            and_(
                                YieldCurve.country_code == country,
                                YieldCurve.date == dt,
                                YieldCurve.maturity_months == maturity,
                            )
                        )
                        .first()
                    )

                    if exists:
                        continue

                    session.add(
                        YieldCurve(
                            country_code=country,
                            date=dt,
                            maturity_months=maturity,
                            yield_pct=float(close_val),
                            source_id=src_id,
                        )
                    )
                    stats["inserted"] += 1

                session.commit()

            self._finish_run(run_id, "success", **stats)
        except Exception as e:
            session.rollback()
            stats["errors"] += 1
            logger.error("Error yields: %s", e)
            self._finish_run(
                run_id,
                "failed",
                **stats,
                error_log={"msg": str(e)},
            )
        finally:
            session.close()

        return stats
