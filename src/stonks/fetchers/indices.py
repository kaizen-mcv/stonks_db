"""Fetcher de índices de mercado via yfinance."""

import yfinance as yf
from sqlalchemy import and_

import stonks.models  # noqa: F401
from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.equity import (
    IndexPrice,
    MarketIndex,
)
from stonks.models.meta import DataSource

# Índices principales
INDICES = [
    ("SPX", "^GSPC", "S&P 500", "USA", "USD"),
    ("DJI", "^DJI", "Dow Jones Industrial", "USA", "USD"),
    ("IXIC", "^IXIC", "NASDAQ Composite", "USA", "USD"),
    ("RUT", "^RUT", "Russell 2000", "USA", "USD"),
    ("FTSE100", "^FTSE", "FTSE 100", "GBR", "GBP"),
    ("DAX", "^GDAXI", "DAX", "DEU", "EUR"),
    ("CAC40", "^FCHI", "CAC 40", "FRA", "EUR"),
    ("IBEX35", "^IBEX", "IBEX 35", "ESP", "EUR"),
    ("FTSEMIB", "FTSEMIB.MI", "FTSE MIB", "ITA", "EUR"),
    ("SMI", "^SSMI", "Swiss Market Index", "CHE", "CHF"),
    ("AEX", "^AEX", "AEX", "NLD", "EUR"),
    ("NIKKEI", "^N225", "Nikkei 225", "JPN", "JPY"),
    ("HSI", "^HSI", "Hang Seng", "HKG", "HKD"),
    ("SSEC", "000001.SS", "Shanghai Composite", "CHN", "CNY"),
    ("KOSPI", "^KS11", "KOSPI", "KOR", "KRW"),
    ("ASX200", "^AXJO", "S&P/ASX 200", "AUS", "AUD"),
    ("TSX", "^GSPTSE", "S&P/TSX Composite", "CAN", "CAD"),
    ("BOVESPA", "^BVSP", "Bovespa", "BRA", "BRL"),
    ("SENSEX", "^BSESN", "BSE SENSEX", "IND", "INR"),
    ("STOXX50", "^STOXX50E", "Euro Stoxx 50", None, "EUR"),
]


class IndexFetcher(BaseFetcher):
    """Descarga precios de índices de mercado."""

    SOURCE_NAME = "yfinance"
    DOMAIN = "equity"
    RATE_LIMIT = 0.5

    def seed_indices(self) -> int:
        """Insertar índices de referencia."""
        session = get_session()
        count = 0
        try:
            for code, _, name, country, currency in INDICES:
                if session.query(MarketIndex).filter_by(code=code).first():
                    continue
                session.add(
                    MarketIndex(
                        code=code,
                        name=name,
                        country_code=country,
                        currency_code=currency,
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
        period: str = "5y",
    ) -> dict[str, int]:
        """Descargar precios de índices."""
        run_id = self._start_run(
            params={
                "code": code,
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
            _ = src.id if src else None  # para auditoria futura

            # Mapa code -> yfinance ticker
            ticker_map = {i[0]: i[1] for i in INDICES}

            if code:
                indices = [
                    session.query(MarketIndex).filter_by(code=code).first()
                ]
            else:
                indices = session.query(MarketIndex).all()

            for idx in indices:
                if not idx:
                    continue

                yf_ticker = ticker_map.get(idx.code)
                if not yf_ticker:
                    continue

                logger.info(
                    "  Índice: %s (%s)...",
                    idx.code,
                    yf_ticker,
                )
                try:
                    t = yf.Ticker(yf_ticker)
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

                for row_idx, row in df.iterrows():
                    dt = row_idx.date()
                    stats["fetched"] += 1

                    exists = (
                        session.query(IndexPrice)
                        .filter(
                            and_(
                                IndexPrice.index_id == idx.id,
                                IndexPrice.date == dt,
                            )
                        )
                        .first()
                    )

                    if exists:
                        continue

                    session.add(
                        IndexPrice(
                            index_id=idx.id,
                            date=dt,
                            open=row.get("Open"),
                            high=row.get("High"),
                            low=row.get("Low"),
                            close=row["Close"],
                            volume=int(row.get("Volume", 0)) or None,
                        )
                    )
                    stats["inserted"] += 1

                session.commit()

            self._finish_run(run_id, "success", **stats)
        except Exception as e:
            session.rollback()
            stats["errors"] += 1
            logger.error("Error indices: %s", e)
            self._finish_run(
                run_id,
                "failed",
                **stats,
                error_log={"msg": str(e)},
            )
        finally:
            session.close()

        return stats
