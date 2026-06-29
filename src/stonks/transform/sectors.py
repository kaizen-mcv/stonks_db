"""Poblar equity.company.sector_id (GICS) desde yfinance.

yfinance usa su propia taxonomía de 11 sectores (p.ej. "Technology",
"Financial Services") distinta de los nombres GICS de ref.sector. Aquí
mapeamos esa taxonomía al código GICS de nivel 1 y actualizamos la
empresa. Desbloquea kairos_bot.build_sector_map (anti-concentración y
factores sector-neutral).
"""

import time
import unicodedata

import yfinance as yf

from stonks.db import get_session
from stonks.models.ref import Sector
from stonks.transform.base import BaseTransform, logger

# Sector de Yahoo (normalizado) → código GICS nivel 1 (ref.sector.gics_code)
YAHOO_TO_GICS: dict[str, str] = {
    "technology": "45",
    "financial services": "40",
    "financial": "40",
    "healthcare": "35",
    "consumer cyclical": "25",
    "consumer defensive": "30",
    "communication services": "50",
    "industrials": "20",
    "basic materials": "15",
    "energy": "10",
    "utilities": "55",
    "real estate": "60",
}


def _norm(text: str) -> str:
    """Normalizar: minúsculas y sin acentos."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sin_acentos.strip().lower()


class SectorTransform(BaseTransform):
    """Asigna sector_id GICS a las empresas a partir de yfinance."""

    DOMAIN = "equity_sector"
    TARGET_LAYER = "silver"
    RATE_LIMIT = 0.5  # segundos entre llamadas a yfinance

    def transform(
        self,
        tickers: list[str] | None = None,
        refresh: bool = False,
    ) -> None:
        """Mapear y guardar el sector de cada empresa.

        Args:
            tickers: subconjunto a procesar. None = todas las empresas.
            refresh: si True, reprocesa también las que ya tienen sector.
        """
        run_id = self._start_run(
            params={"refresh": refresh, "tickers": tickers}
        )
        code_to_id = self._gics_code_to_id()
        session = get_session()
        read = written = invalid = 0
        try:
            companies = self._target_companies(session, tickers, refresh)
            for ticker, company_id in companies:
                read += 1
                gics_id = self._resolve_sector_id(ticker, code_to_id)
                if gics_id is None:
                    invalid += 1
                    continue
                company = self._get_company(session, company_id)
                if company is not None:
                    company.sector_id = gics_id
                    written += 1
                if written and written % 50 == 0:
                    session.commit()
            session.commit()
            self._finish_run(
                run_id,
                "success",
                records_read=read,
                records_written=written,
                records_invalid=invalid,
            )
            logger.info(
                "Sectores: %d leídas, %d asignadas, %d sin mapear",
                read,
                written,
                invalid,
            )
        except Exception as e:  # noqa: BLE001
            session.rollback()
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
            logger.error("SectorTransform falló: %s", e)
        finally:
            session.close()

    def _gics_code_to_id(self) -> dict[str, int]:
        """Mapa gics_code (nivel 1) → id de ref.sector."""
        session = get_session()
        try:
            rows = session.query(Sector).filter(Sector.level == 1).all()
            return {s.gics_code: s.id for s in rows}
        finally:
            session.close()

    @staticmethod
    def _target_companies(session, tickers, refresh):
        """Lista de (ticker, id) a procesar."""
        from stonks.models.equity import Company

        query = session.query(Company.ticker, Company.id)
        if tickers:
            query = query.filter(Company.ticker.in_(tickers))
        if not refresh:
            query = query.filter(Company.sector_id.is_(None))
        return query.all()

    @staticmethod
    def _get_company(session, company_id: int):
        """Cargar empresa por id."""
        from stonks.models.equity import Company

        return session.query(Company).filter_by(id=company_id).first()

    def _resolve_sector_id(self, ticker, code_to_id):
        """Sector GICS id desde el .info de yfinance (o None)."""
        time.sleep(self.RATE_LIMIT)
        try:
            info = yf.Ticker(ticker).info
        except Exception as e:  # noqa: BLE001
            logger.warning("Sin info para %s: %s", ticker, e)
            return None
        gics_code = YAHOO_TO_GICS.get(_norm(info.get("sector", "")))
        if gics_code is None:
            return None
        return code_to_id.get(gics_code)
