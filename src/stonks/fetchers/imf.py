"""Fetcher del IMF DataMapper (World Economic Outlook y otros).

API de JSON simple (no SDMX): cobertura mundial de cuentas nacionales,
precios, fiscal, externo y trabajo, con histórico desde 1980 y
proyecciones. Aterriza crudo en bronze.api_response y auto-registra el
catálogo de indicadores en macro.indicator/indicator_source (así no hay
que mantener 130+ indicadores a mano).
"""

from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.bronze import ApiResponse
from stonks.models.macro import Indicator, IndicatorSource
from stonks.models.meta import DataSource

BASE = "https://www.imf.org/external/datamapper/api/v1"

# Clasificación de indicadores por dominio (por prefijo de código).
_CATEGORY = [
    ("NGDP", "national_accounts"),
    ("PPPGDP", "national_accounts"),
    ("PPPPC", "national_accounts"),
    ("PPPSH", "national_accounts"),
    ("NID", "national_accounts"),
    ("NGSD", "national_accounts"),
    ("PCPI", "prices"),
    ("PALLFNF", "prices"),
    ("LUR", "labor"),
    ("LE", "labor"),
    ("LP", "demography"),
    ("GGX", "fiscal"),
    ("GGR", "fiscal"),
    ("GGSB", "fiscal"),
    ("GGXWD", "fiscal"),
    ("BCA", "external"),
    ("BX", "external"),
    ("BM", "external"),
    ("D_", "external"),
    ("TX", "external"),
    ("TM", "external"),
]


def _category(code: str) -> str:
    """Dominio del indicador a partir del código IMF."""
    for prefijo, cat in _CATEGORY:
        if code.startswith(prefijo):
            return cat
    return "macro"


class IMFDataMapperFetcher(BaseFetcher):
    """Descarga indicadores del IMF DataMapper."""

    SOURCE_NAME = "imf"
    DOMAIN = "macro"
    RATE_LIMIT = 0.5

    def fetch_catalog(self) -> dict:
        """Descargar la lista de indicadores y registrarla en macro."""
        run_id = self._start_run(params={"dataset": "indicators"})
        try:
            data = self._get(f"{BASE}/indicators")
            indicators = data.get("indicators", {})
            self._land("indicators", None, data, run_id)
            n = self._register_catalog(indicators)
            self._finish_run(
                run_id, "success", fetched=len(indicators), inserted=n
            )
            logger.info(
                "IMF catálogo: %d indicadores, %d nuevos", len(indicators), n
            )
            return {"indicators": len(indicators), "registrados": n}
        except Exception as e:  # noqa: BLE001
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
            logger.error("IMF catálogo falló: %s", e)
            return {}

    def fetch_indicator(self, code: str) -> dict:
        """Descargar un indicador para todos los países → bronze."""
        run_id = self._start_run(params={"dataset": code})
        try:
            data = self._get(f"{BASE}/{code}")
            self._land(code, None, data, run_id)
            vals = data.get("values", {}).get(code, {})
            self._finish_run(run_id, "success", fetched=len(vals), inserted=1)
            return {"code": code, "countries": len(vals)}
        except Exception as e:  # noqa: BLE001
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
            logger.error("IMF %s falló: %s", code, e)
            return {"code": code, "countries": 0}

    def fetch_all(self, codes: list[str] | None = None) -> dict:
        """Descargar todos los indicadores del catálogo (o los dados)."""
        if codes is None:
            codes = self._catalog_codes()
        total = len(codes)
        ok = 0
        for i, code in enumerate(codes, 1):
            if self.fetch_indicator(code).get("countries"):
                ok += 1
            if i % 25 == 0:
                logger.info("IMF %d/%d", i, total)
        logger.info("IMF: %d/%d indicadores con datos", ok, total)
        return {"indicadores": total, "con_datos": ok}

    def fetch(self) -> dict:
        """Para el pipeline: catálogo + todos los indicadores."""
        self.fetch_catalog()
        return self.fetch_all()

    # ── helpers ──────────────────────────────────────

    def _register_catalog(self, indicators: dict) -> int:
        """Crear macro.indicator + indicator_source para cada código."""
        session = get_session()
        n = 0
        try:
            src = (
                session.query(DataSource)
                .filter_by(name=self.SOURCE_NAME)
                .first()
            )
            src_id = src.id if src else None
            for code, meta in indicators.items():
                label = (meta or {}).get("label") or code
                unit = (meta or {}).get("unit")
                ind = (
                    session.query(Indicator)
                    .filter_by(code=f"IMF_{code}")
                    .first()
                )
                if ind is None:
                    ind = Indicator(
                        code=f"IMF_{code}",
                        name=label[:300],
                        category=_category(code),
                        unit=(unit or "")[:50] or None,
                        frequency="annual",
                    )
                    session.add(ind)
                    session.flush()
                    n += 1
                if src_id and not (
                    session.query(IndicatorSource)
                    .filter_by(indicator_id=ind.id, source_id=src_id)
                    .first()
                ):
                    session.add(
                        IndicatorSource(
                            indicator_id=ind.id,
                            source_id=src_id,
                            external_code=code,
                            external_name=label[:500],
                        )
                    )
            session.commit()
        finally:
            session.close()
        return n

    def _catalog_codes(self) -> list[str]:
        """Códigos externos IMF ya registrados en macro."""
        session = get_session()
        try:
            src = (
                session.query(DataSource)
                .filter_by(name=self.SOURCE_NAME)
                .first()
            )
            if not src:
                return []
            rows = (
                session.query(IndicatorSource.external_code)
                .filter_by(source_id=src.id)
                .all()
            )
            return [r[0] for r in rows]
        finally:
            session.close()

    def _land(self, dataset, params, payload, run_id) -> None:
        """Insertar la respuesta cruda en bronze.api_response."""
        session = get_session()
        try:
            session.add(
                ApiResponse(
                    fetch_run_id=run_id,
                    source_name=self.SOURCE_NAME,
                    dataset=dataset,
                    params=params,
                    payload=payload,
                )
            )
            session.commit()
        finally:
            session.close()
