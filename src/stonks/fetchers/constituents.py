"""Constituyentes de índices: histórico S&P 500 (survivorship-free).

Fuentes gratuitas:
- GitHub fja05680/sp500: `sp500_ticker_start_end.csv`, intervalos
  (ticker, start_date, end_date) ya calculados. Fuente PRIMARIA del
  histórico point-in-time.
- Wikipedia: tabla de constituyentes ACTUALES (cross-check / snapshot).

Ambas aterrizan crudas en bronze.constituents_snapshot. La
reconstrucción del universo la hace transform/constituents.py.
"""

import csv
import io

from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.bronze import ConstituentsSnapshot

GITHUB_BASE = "https://raw.githubusercontent.com/fja05680/sp500/master/"
INTERVALS_CSV = "sp500_ticker_start_end.csv"
WIKI_SP500 = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


class ConstituentsFetcher(BaseFetcher):
    """Descarga constituyentes de índices (S&P 500)."""

    SOURCE_NAME = "github_fja05680"
    DOMAIN = "equity"
    RATE_LIMIT = 1.0

    def fetch_sp500_intervals(self) -> dict:
        """Descargar intervalos de pertenencia al S&P 500 (GitHub)."""
        run_id = self._start_run(params={"file": INTERVALS_CSV})
        stats = {"fetched": 0, "inserted": 0}
        try:
            self._rate_limit()
            resp = self._session.get(GITHUB_BASE + INTERVALS_CSV, timeout=60)
            resp.raise_for_status()
            reader = csv.DictReader(io.StringIO(resp.text))
            rows = [
                [r["ticker"], r["start_date"], r.get("end_date") or None]
                for r in reader
            ]
            stats["fetched"] = len(rows)
            self._land("SP500", "github_intervals", {"rows": rows}, run_id)
            stats["inserted"] = 1
            self._finish_run(run_id, "success", **stats)
            logger.info("S&P500 intervalos: %d filas", len(rows))
        except Exception as e:  # noqa: BLE001
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
            logger.error("Fallo descargando intervalos S&P500: %s", e)
        return stats

    def fetch_sp500_current(self) -> dict:
        """Descargar la tabla actual de constituyentes (Wikipedia)."""
        import pandas as pd

        run_id = self._start_run(params={"url": WIKI_SP500})
        stats = {"fetched": 0, "inserted": 0}
        try:
            self._rate_limit()
            resp = self._session.get(WIKI_SP500, timeout=60)
            resp.raise_for_status()
            tablas = pd.read_html(io.StringIO(resp.text))
            # La primera tabla es la de constituyentes actuales.
            df = tablas[0]
            df.columns = [str(c).lower() for c in df.columns]
            rows = df.to_dict(orient="records")
            stats["fetched"] = len(rows)
            self._land("SP500", "wikipedia_current", {"rows": rows}, run_id)
            stats["inserted"] = 1
            self._finish_run(run_id, "success", **stats)
            logger.info("S&P500 actual (Wikipedia): %d filas", len(rows))
        except Exception as e:  # noqa: BLE001
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
            logger.error("Fallo descargando Wikipedia S&P500: %s", e)
        return stats

    def fetch(self) -> dict:
        """Descargar ambas fuentes (para el pipeline)."""
        inter = self.fetch_sp500_intervals()
        curr = self.fetch_sp500_current()
        return {"intervals": inter, "current": curr}

    def fetch_missing_member_prices(self, limit: int | None = None) -> dict:
        """Descargar precios de miembros del índice que no tienen ninguno.

        Sobre todo las empresas deslistadas creadas por
        MembershipTransform: sin sus precios, el benchmark equiponderado
        sigue parcialmente sesgado en el pasado. yfinance suele conservar
        históricos de deslistadas; las que no resuelvan se omiten.
        """
        from sqlalchemy import text

        from stonks.fetchers.yfinance_ import YFinanceFetcher

        session = get_session()
        try:
            sql = text(
                "SELECT DISTINCT c.id, c.ticker FROM equity.company c "
                "JOIN gold.index_membership m ON m.company_id = c.id "
                "WHERE NOT EXISTS (SELECT 1 FROM equity.price_daily p "
                "                  WHERE p.company_id = c.id)"
            )
            faltan = list(session.execute(sql))
        finally:
            session.close()
        if limit:
            faltan = faltan[:limit]

        yf_fetcher = YFinanceFetcher()
        stats = {"intentadas": 0, "con_precios": 0}
        for company_id, ticker in faltan:
            stats["intentadas"] += 1
            res = yf_fetcher.fetch_prices(
                ticker, period="max", company_id=company_id
            )
            if res.get("inserted", 0) > 0:
                stats["con_precios"] += 1
        logger.info(
            "Precios deslistadas: %d/%d con datos",
            stats["con_precios"],
            stats["intentadas"],
        )
        return stats

    @staticmethod
    def _land(
        index_code: str, source_kind: str, payload: dict, run_id: int
    ) -> None:
        """Insertar el payload crudo en bronze."""
        session = get_session()
        try:
            session.add(
                ConstituentsSnapshot(
                    fetch_run_id=run_id,
                    index_code=index_code,
                    source_kind=source_kind,
                    payload=payload,
                )
            )
            session.commit()
        finally:
            session.close()
