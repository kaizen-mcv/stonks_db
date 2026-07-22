"""Fetcher de FAOSTAT: producción agrícola (bulk CSV, sin clave).

Descarga el ZIP normalizado de Producción de Cultivos y Ganadería y lo
vuelca a agri.production. Mapea el país por código M49 → ISO-3. Escribe
directo a silver (como world_bank/owid), con auditoría en fetch_run.
"""

import csv
import io
import zipfile

import pycountry
from sqlalchemy.dialects.postgresql import insert

from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.agri import Production
from stonks.models.meta import DataSource

BASE = "https://bulks-faostat.fao.org/production/"
DATASET = "Production_Crops_Livestock_E_All_Data_(Normalized).zip"


def _m49_to_iso3() -> dict[str, str]:
    """Mapa código numérico M49 (3 dígitos) → ISO-3."""
    out = {}
    for c in pycountry.countries:
        num = getattr(c, "numeric", None)
        if num:
            out[num] = c.alpha_3
    return out


class FaostatFetcher(BaseFetcher):
    """Descarga producción agrícola de FAOSTAT."""

    SOURCE_NAME = "faostat"
    DOMAIN = "agri"
    RATE_LIMIT = 1.0

    def fetch(self) -> dict:
        """Descargar y volcar la producción agrícola."""
        run_id = self._start_run(params={"dataset": "production"})
        stats = {"fetched": 0, "inserted": 0}
        try:
            self._rate_limit()
            resp = self._session.get(BASE + DATASET, timeout=300)
            resp.raise_for_status()
            z = zipfile.ZipFile(io.BytesIO(resp.content))
            name = next(
                n for n in z.namelist() if n.endswith("(Normalized).csv")
            )
            src_id = self._source_id()
            m49 = _m49_to_iso3()
            valid = self._valid_countries()
            batch: list[dict] = []
            with z.open(name) as f:
                reader = csv.DictReader(
                    io.TextIOWrapper(f, encoding="latin-1")
                )
                for row in reader:
                    fila = self._parse(row, m49, valid, src_id)
                    if fila is None:
                        continue
                    batch.append(fila)
                    stats["fetched"] += 1
                    if len(batch) >= 4000:
                        stats["inserted"] += self._flush(batch)
                        batch = []
            stats["inserted"] += self._flush(batch)
            self._finish_run(run_id, "success", **stats)
            logger.info("FAOSTAT: %d filas", stats["inserted"])
        except Exception as e:  # noqa: BLE001
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
            logger.error("FAOSTAT falló: %s", e)
        return stats

    @staticmethod
    def _parse(row, m49, valid, src_id) -> dict | None:
        """Fila CSV → dict de agri.production (o None)."""
        raw = row.get("Area Code (M49)") or ""
        code = "".join(ch for ch in raw if ch.isdigit()).zfill(3)
        iso = m49.get(code)
        if iso is None or iso not in valid:
            return None
        val = row.get("Value")
        if val in (None, ""):
            return None
        try:
            year = int(row["Year"])
            value = float(val)
        except (ValueError, TypeError):
            return None
        return {
            "country_code": iso,
            "item_code": str(row.get("Item Code") or "")[:20],
            "item_name": str(row.get("Item") or "")[:200] or None,
            "element": str(row.get("Element") or "")[:60],
            "period": year,
            "value": value,
            "unit": str(row.get("Unit") or "")[:40] or None,
            "source_id": src_id,
        }

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
        """Upsert idempotente troceado (dedup intra-lote)."""
        if not batch:
            return 0
        dedup = {
            (f["country_code"], f["item_code"], f["element"], f["period"]): f
            for f in batch
        }
        rows = list(dedup.values())
        session = get_session()
        try:
            stmt = insert(Production).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=[
                    "country_code",
                    "item_code",
                    "element",
                    "period",
                ],
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
