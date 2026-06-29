"""Fetcher de datos de analistas (yfinance): foto diaria → bronze.

yfinance solo da la foto actual de estimaciones/revisiones (no hay serie
retroactiva gratuita), así que el histórico se construye capturando una
foto por día hacia adelante. Cada atributo se envuelve en try/except: la
API de analistas de yfinance es frágil y cambia de forma.
"""

import json
from datetime import date

import yfinance as yf
from sqlalchemy.dialects.postgresql import insert

from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.bronze import AnalystSnapshot

# Atributos de yfinance que capturamos (tablas indexadas por horizonte)
ATTRS = ("earnings_estimate", "revenue_estimate", "eps_trend", "eps_revisions")


class AnalystFetcher(BaseFetcher):
    """Captura la foto diaria de analistas por ticker."""

    SOURCE_NAME = "yfinance"
    DOMAIN = "equity"
    RATE_LIMIT = 0.5

    def fetch_snapshot(self, ticker: str) -> dict:
        """Capturar la foto de analistas de un ticker → bronze."""
        payload: dict[str, dict] = {}
        t = yf.Ticker(ticker)
        for attr in ATTRS:
            try:
                df = getattr(t, attr)
                if df is not None and not df.empty:
                    payload[attr] = json.loads(df.to_json(orient="index"))
            except Exception as e:  # noqa: BLE001
                logger.warning("%s %s sin datos: %s", ticker, attr, e)
        if not payload:
            return {"inserted": 0}
        self._land(ticker, payload)
        return {"inserted": 1}

    def fetch_batch(self, tickers: list[str] | None = None) -> dict:
        """Capturar la foto para varios tickers."""
        if tickers is None:
            tickers = self._active_us_tickers()
        stats = {"intentadas": 0, "con_datos": 0}
        for i, ticker in enumerate(tickers, 1):
            self._rate_limit()
            stats["intentadas"] += 1
            if self.fetch_snapshot(ticker).get("inserted"):
                stats["con_datos"] += 1
            if i % 50 == 0:
                logger.info("Analistas %d/%d", i, len(tickers))
        logger.info(
            "Analistas: %d/%d con datos",
            stats["con_datos"],
            len(tickers),
        )
        return stats

    def fetch(self, tickers: list[str] | None = None) -> dict:
        """Alias para el pipeline."""
        return self.fetch_batch(tickers)

    @staticmethod
    def _active_us_tickers() -> list[str]:
        """Tickers activos (universo de captura diaria)."""
        from sqlalchemy import text

        session = get_session()
        try:
            rows = session.execute(
                text(
                    "SELECT ticker FROM equity.company WHERE is_active = true"
                )
            )
            return [r[0] for r in rows]
        finally:
            session.close()

    def _land(self, ticker: str, payload: dict) -> None:
        """Upsert idempotente de la foto del día en bronze."""
        run_id = self._start_run(params={"ticker": ticker})
        session = get_session()
        try:
            stmt = insert(AnalystSnapshot).values(
                fetch_run_id=run_id,
                ticker=ticker,
                snapshot_date=date.today(),
                payload=payload,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["ticker", "snapshot_date"],
                set_={"payload": stmt.excluded.payload},
            )
            session.execute(stmt)
            session.commit()
            self._finish_run(run_id, "success", inserted=1)
        except Exception as e:  # noqa: BLE001
            session.rollback()
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
        finally:
            session.close()
