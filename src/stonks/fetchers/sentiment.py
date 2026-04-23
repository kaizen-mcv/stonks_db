"""Fetcher de indicadores de sentimiento (VIX)
via yfinance."""

import yfinance as yf
from sqlalchemy import and_

import stonks.models  # noqa: F401
from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.alternative import (
    SentimentIndicator,
    SentimentValue,
)

# Indicadores de sentimiento disponibles via yfinance
SENTIMENT_TICKERS = [
    ("VIX", "^VIX", "CBOE Volatility Index"),
    ("VIX9D", "^VIX9D", "CBOE S&P 500 9-Day VI"),
    ("VVIX", "^VVIX", "CBOE VIX of VIX"),
    ("MOVE", "^MOVE", "ICE BofA MOVE Index (Bond Vol)"),
]


class SentimentFetcher(BaseFetcher):
    """Descarga indicadores de sentimiento."""

    SOURCE_NAME = "yfinance"
    DOMAIN = "alt"
    RATE_LIMIT = 0.5

    def _ensure_indicators(self, session) -> dict[str, int]:
        """Crear indicadores si no existen."""
        cache: dict[str, int] = {}
        for code, _, desc in SENTIMENT_TICKERS:
            ind = (
                session.query(SentimentIndicator).filter_by(code=code).first()
            )
            if not ind:
                ind = SentimentIndicator(
                    code=code,
                    name=desc,
                )
                session.add(ind)
                session.flush()
            cache[code] = ind.id
        session.commit()
        return cache

    def fetch_sentiment(self, period: str = "5y") -> dict[str, int]:
        """Descargar VIX y otros indicadores."""
        run_id = self._start_run(
            params={
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
            ind_cache = self._ensure_indicators(session)

            for code, ticker, _ in SENTIMENT_TICKERS:
                logger.info(
                    "  Sentimiento: %s (%s)...",
                    code,
                    ticker,
                )
                try:
                    t = yf.Ticker(ticker)
                    df = t.history(period=period)
                except Exception as e:
                    logger.warning("  Error %s: %s", code, e)
                    stats["errors"] += 1
                    continue

                if df.empty:
                    continue

                ind_id = ind_cache[code]

                for idx, row in df.iterrows():
                    dt = idx.date()
                    close = row.get("Close")
                    if close is None or close != close:
                        continue

                    stats["fetched"] += 1
                    exists = (
                        session.query(SentimentValue)
                        .filter(
                            and_(
                                SentimentValue.indicator_id == ind_id,
                                SentimentValue.date == dt,
                            )
                        )
                        .first()
                    )

                    if exists:
                        continue

                    session.add(
                        SentimentValue(
                            indicator_id=ind_id,
                            date=dt,
                            value=float(close),
                        )
                    )
                    stats["inserted"] += 1

                session.commit()

            self._finish_run(run_id, "success", **stats)
        except Exception as e:
            session.rollback()
            stats["errors"] += 1
            logger.error("Error sentiment: %s", e)
            self._finish_run(
                run_id,
                "failed",
                **stats,
                error_log={"msg": str(e)},
            )
        finally:
            session.close()

        return stats
