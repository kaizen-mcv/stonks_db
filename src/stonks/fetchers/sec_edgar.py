"""Fetcher de SEC EDGAR: fundamentales point-in-time (API companyfacts).

Cada hecho XBRL trae su fecha de publicación ('filed'), lo que permite
fundamentales point-in-time reales para emisores US (lo que yfinance no
da). Aterriza el JSON crudo en bronze.sec_companyfacts; la normalización
la hace transform/fundamentals_pit.py.

SEC exige un User-Agent con email de contacto y limita a 10 req/s.
"""

from stonks.config import settings
from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.bronze import SecCompanyFacts

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


class SecEdgarFetcher(BaseFetcher):
    """Descarga companyfacts de SEC EDGAR para emisores US."""

    SOURCE_NAME = "sec_edgar"
    DOMAIN = "equity"
    RATE_LIMIT = 0.11  # ~9 req/s, bajo el límite de 10/s de SEC

    def __init__(self) -> None:
        super().__init__()
        # SEC requiere identificarse o devuelve 403.
        self._session.headers["User-Agent"] = (
            f"stonks/0.2 {settings.sec_contact_email}"
        )
        self._cik_map: dict[str, str] | None = None

    def _load_cik_map(self) -> dict[str, str]:
        """Mapa ticker (mayúsculas) → CIK con relleno a 10 dígitos."""
        if self._cik_map is not None:
            return self._cik_map
        self._rate_limit()
        data = self._session.get(TICKERS_URL, timeout=60).json()
        self._cik_map = {
            row["ticker"].upper(): f"{int(row['cik_str']):010d}"
            for row in data.values()
        }
        return self._cik_map

    def _resolve_cik(self, ticker: str) -> str | None:
        """CIK de un ticker (None si no es emisor SEC)."""
        return self._load_cik_map().get(ticker.upper())

    def fetch_companyfacts(
        self, ticker: str, company_id: int | None = None
    ) -> dict:
        """Descargar companyfacts de un ticker y aterrizar en bronze."""
        run_id = self._start_run(params={"ticker": ticker})
        stats = {"fetched": 0, "inserted": 0}
        cik = self._resolve_cik(ticker)
        if cik is None:
            self._finish_run(run_id, "skipped", error_log={"msg": "sin CIK"})
            return stats
        try:
            self._rate_limit()
            resp = self._session.get(FACTS_URL.format(cik=cik), timeout=60)
            if resp.status_code == 404:
                self._finish_run(run_id, "skipped")
                return stats
            resp.raise_for_status()
            payload = resp.json()
            self._land(cik, ticker, payload, run_id)
            stats = {"fetched": 1, "inserted": 1}
            self._finish_run(run_id, "success", **stats)
        except Exception as e:  # noqa: BLE001
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
            logger.error("SEC companyfacts %s: %s", ticker, e)
        return stats

    def fetch_batch(self, tickers: list[str] | None = None) -> dict:
        """Descargar companyfacts para varios tickers."""
        if tickers is None:
            tickers = self._us_company_tickers()
        stats = {"intentadas": 0, "con_datos": 0}
        total = len(tickers)
        for i, ticker in enumerate(tickers, 1):
            stats["intentadas"] += 1
            res = self.fetch_companyfacts(ticker)
            if res.get("inserted"):
                stats["con_datos"] += 1
            if i % 50 == 0:
                logger.info("SEC %d/%d", i, total)
        logger.info("SEC EDGAR: %d/%d con datos", stats["con_datos"], total)
        return stats

    @staticmethod
    def _us_company_tickers() -> list[str]:
        """Tickers de empresas US activas (probables emisores SEC)."""
        from sqlalchemy import text

        session = get_session()
        try:
            rows = session.execute(
                text(
                    "SELECT ticker FROM equity.company "
                    "WHERE country_code = 'USA' AND is_active = true"
                )
            )
            return [r[0] for r in rows]
        finally:
            session.close()

    @staticmethod
    def _land(cik: str, ticker: str, payload: dict, run_id: int) -> None:
        """Insertar el companyfacts crudo en bronze."""
        session = get_session()
        try:
            session.add(
                SecCompanyFacts(
                    fetch_run_id=run_id,
                    cik=cik,
                    ticker=ticker,
                    payload=payload,
                )
            )
            session.commit()
        finally:
            session.close()
