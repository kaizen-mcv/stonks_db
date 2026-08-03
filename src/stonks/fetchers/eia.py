"""Fetcher de EIA International Energy Data (api.eia.gov v2).

Descarga producción y consumo de petróleo por país a energy.balance.
Requiere clave gratuita (STONKS_EIA_KEY, eia.gov/opendata/register.php).

Nota: el endpoint v2 /international solo expone productos de petróleo.
Gas, carbón y electricidad ya están cubiertos por OWID; si se quisieran
de EIA habría que usar la ruta legacy /v2/seriesid/INTL.{id}.
"""

from sqlalchemy.dialects.postgresql import insert

from stonks.config import settings
from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.energy import Balance
from stonks.models.meta import DataSource

BASE = "https://api.eia.gov/v2/international/data/"

# (product_id, activity_id, product_code, flow, unit)
# El endpoint v2 solo soporta petróleo (productId 53/57).
SERIES = [
    (53, 1, "petroleum", "production", "kbd"),
    (53, 2, "petroleum", "consumption", "kbd"),
    (57, 1, "crude_oil", "production", "kbd"),
]


class EIAFetcher(BaseFetcher):
    """Descarga energía internacional de EIA."""

    SOURCE_NAME = "eia"
    DOMAIN = "energy"
    RATE_LIMIT = 1.0

    def __init__(self) -> None:
        super().__init__()
        self.api_key = settings.eia_key
        if not self.api_key:
            logger.warning(
                "EIA API key no configurada. "
                "Regístrate gratis en eia.gov/opendata"
            )

    def fetch(self) -> dict:
        """Descargar todas las series de energía."""
        if not self.api_key:
            logger.error("STONKS_EIA_KEY no configurada")
            return {}
        run_id = self._start_run(params={"type": "international"})
        stats = {"fetched": 0, "inserted": 0, "errors": 0}
        for prod_id, act_id, code, flow, unit in SERIES:
            logger.info("EIA: %s %s ...", code, flow)
            try:
                n = self._fetch_series(prod_id, act_id, code, flow, unit)
                stats["fetched"] += n
                stats["inserted"] += n
            except Exception as e:  # noqa: BLE001
                stats["errors"] += 1
                logger.error(
                    "EIA %s/%s: %s",
                    code,
                    flow,
                    e,
                )
        status = "success" if not stats["errors"] else "partial"
        self._finish_run(run_id, status, **stats)
        logger.info(
            "EIA: %d filas, %d errores",
            stats["inserted"],
            stats["errors"],
        )
        return stats

    def _fetch_series(
        self,
        product_id: int,
        activity_id: int,
        product_code: str,
        flow: str,
        unit: str,
    ) -> int:
        """Descargar una combinación producto×actividad."""
        valid = self._valid_countries()
        src_id = self._source_id()
        total = 0
        offset = 0
        page_size = 5000

        while True:
            params = {
                "api_key": self.api_key,
                "frequency": "annual",
                "data[0]": "value",
                "facets[productId][]": str(product_id),
                "facets[activityId][]": str(activity_id),
                "facets[countryRegionTypeId][]": "c",
                "start": "1980",
                "end": "2025",
                "sort[0][column]": "period",
                "sort[0][direction]": "asc",
                "offset": str(offset),
                "length": str(page_size),
            }
            data = self._get(BASE, params)
            rows = data.get("response", {}).get("data", [])
            if not rows:
                break

            batch = []
            for row in rows:
                # EIA usa ISO-3 como countryRegionId
                iso3 = row.get("countryRegionId", "")
                if iso3 not in valid:
                    continue
                val = row.get("value")
                if val is None:
                    continue
                try:
                    period = int(str(row.get("period", ""))[:4])
                    value = float(val)
                except (ValueError, TypeError):
                    continue
                batch.append(
                    {
                        "country_code": iso3,
                        "product_code": product_code,
                        "flow": flow,
                        "period": period,
                        "value": value,
                        "unit": unit,
                        "source_id": src_id,
                    }
                )

            if batch:
                total += self._flush(batch)

            if len(rows) < page_size:
                break
            offset += page_size

        return total

    def _source_id(self) -> int | None:
        session = get_session()
        try:
            src = (
                session.query(DataSource)
                .filter_by(name=self.SOURCE_NAME)
                .first()
            )
            return src.id if src else None
        finally:
            session.close()

    @staticmethod
    def _valid_countries() -> set[str]:
        from sqlalchemy import text

        session = get_session()
        try:
            return {
                r[0]
                for r in session.execute(text("SELECT code FROM ref.country"))
            }
        finally:
            session.close()

    @staticmethod
    def _flush(batch: list[dict]) -> int:
        """Upsert idempotente."""
        if not batch:
            return 0
        dedup = {
            (
                r["country_code"],
                r["product_code"],
                r["flow"],
                r["period"],
            ): r
            for r in batch
        }
        rows = list(dedup.values())
        session = get_session()
        try:
            stmt = insert(Balance).values(rows)
            stmt = stmt.on_conflict_do_update(
                constraint=(
                    "balance_country_code_product_code_flow_period_key"
                ),
                set_={
                    "value": stmt.excluded.value,
                    "unit": stmt.excluded.unit,
                },
            )
            session.execute(stmt)
            session.commit()
            return len(rows)
        finally:
            session.close()
