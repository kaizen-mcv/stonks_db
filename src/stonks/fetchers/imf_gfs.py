"""Fetcher IMF GFS (Government Finance Statistics)
— SDMX 3.0 CSV.

Descarga datos fiscales detallados de dos dataflows
api.imf.org (SDMX 3.0):
- GFS_COFOG v11.0.0: gasto por función (defensa,
  salud, educación, protección social) en % PIB.
- GFS_SOO v12.0.0: ingresos fiscales (impuestos por
  tipo) en % PIB.

Valores como porcentaje del PIB (POGDP_PT), sector
gobierno general (S13), frecuencia anual.

Nota: Sustituye al antiguo dataflow GFSR/1.0 desde la
migración SDMX 3.0. Los agregados G11_T (total income
tax) no tienen datos en la API; se suman sub-partidas
G111*_T manualmente.
"""

import csv
import io
from collections import defaultdict
from datetime import date

import requests as _req
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.macro import (
    DataPoint,
    Indicator,
    IndicatorSource,
    Series,
)
from stonks.models.meta import DataSource

BASE_SOO = (
    "https://api.imf.org/external/sdmx/3.0/"
    "data/dataflow/IMF.STA/GFS_SOO/12.0.0"
)
BASE_COFOG = (
    "https://api.imf.org/external/sdmx/3.0/"
    "data/dataflow/IMF.STA/GFS_COFOG/11.0.0"
)

# (código interno, nombre, categoría)
GFS_SERIES = [
    (
        "IMF_GFS_TAX_TOTAL",
        "Total tax revenue (% GDP)",
        "fiscal",
    ),
    (
        "IMF_GFS_TAX_INCOME",
        "Income tax revenue (% GDP)",
        "fiscal",
    ),
    (
        "IMF_GFS_SPEND_DEFENSE",
        "Defense spending (% GDP)",
        "fiscal",
    ),
    (
        "IMF_GFS_SPEND_HEALTH",
        "Health spending (% GDP)",
        "fiscal",
    ),
    (
        "IMF_GFS_SPEND_EDUCATION",
        "Education spending (% GDP)",
        "fiscal",
    ),
    (
        "IMF_GFS_SPEND_SOCIAL",
        "Social protection spending (% GDP)",
        "fiscal",
    ),
]

# COFOG: indicador API → código interno
_COFOG_MAP = {
    "GF02_T": "IMF_GFS_SPEND_DEFENSE",
    "GF07_T": "IMF_GFS_SPEND_HEALTH",
    "GF09_T": "IMF_GFS_SPEND_EDUCATION",
    "GF10_T": "IMF_GFS_SPEND_SOCIAL",
}

# Categorías impositivas (nivel agregado)
_TAX_CATS = {
    "G112_T",
    "G113_T",
    "G114_T",
    "G115_T",
    "G116_T",
}

BATCH_SIZE = 40
CHUNK = 10_000


class IMFGFSFetcher(BaseFetcher):
    """IMF GFS: datos fiscales anuales por país."""

    SOURCE_NAME = "imf_gfs"
    DOMAIN = "macro"
    RATE_LIMIT = 3.0

    def fetch(self) -> dict:
        run_id = self._start_run(params={"series": len(GFS_SERIES)})

        session = get_session()
        try:
            src_id = self._ensure_source(session)
            valid = {
                r[0]
                for r in session.execute(text("SELECT code FROM ref.country"))
            }
            countries = sorted(valid)

            ind_ids: dict[str, int] = {}
            for code, name, cat in GFS_SERIES:
                ind_ids[code] = self._ensure_indicator(
                    session,
                    code,
                    name,
                    cat,
                    src_id,
                )
            session.commit()

            total = 0
            batches = [
                countries[i : i + BATCH_SIZE]
                for i in range(0, len(countries), BATCH_SIZE)
            ]

            # Fase 1: COFOG (gasto por función)
            logger.info(
                "GFS COFOG: %d batches",
                len(batches),
            )
            for bi, bc in enumerate(batches):
                n = self._fetch_cofog_batch(
                    bc,
                    session,
                    src_id,
                    ind_ids,
                    valid,
                )
                total += n
                if n > 0:
                    logger.info(
                        "GFS COFOG %d/%d: %d pts",
                        bi + 1,
                        len(batches),
                        n,
                    )

            # Fase 2: SOO revenue (impuestos)
            logger.info(
                "GFS SOO: %d batches",
                len(batches),
            )
            for bi, bc in enumerate(batches):
                n = self._fetch_soo_batch(
                    bc,
                    session,
                    src_id,
                    ind_ids,
                    valid,
                )
                total += n
                if n > 0:
                    logger.info(
                        "GFS SOO %d/%d: %d pts",
                        bi + 1,
                        len(batches),
                        n,
                    )

            self._finish_run(
                run_id,
                "success",
                fetched=total,
                inserted=total,
            )
            logger.info("IMF GFS total: %d puntos", total)
        except Exception as e:
            self._finish_run(
                run_id,
                "failed",
                error_log={"msg": str(e)},
            )
            logger.error("IMF GFS falló: %s", e)
            raise
        finally:
            session.close()

        return {
            "series": len(GFS_SERIES),
            "puntos": total,
        }

    # --------------------------------------------------
    # Descargas por batch
    # --------------------------------------------------

    def _fetch_cofog_batch(
        self,
        batch_ctrs,
        session,
        src_id,
        ind_ids,
        valid,
    ) -> int:
        country_str = "+".join(batch_ctrs)
        # COUNTRY.SECTOR.GFS_GRP.INDICATOR.UNIT.FREQ
        key = f"{country_str}.S13.G2MF.*.POGDP_PT.A"
        url = f"{BASE_COFOG}/{key}"

        self._rate_limit()
        try:
            resp = _req.get(
                url,
                headers={"Accept": "text/csv"},
                timeout=300,
            )
            resp.raise_for_status()
        except _req.RequestException as e:
            logger.warning("GFS COFOG: %s", e)
            return 0

        return self._process_cofog(
            resp.text,
            session,
            src_id,
            ind_ids,
            valid,
        )

    def _fetch_soo_batch(
        self,
        batch_ctrs,
        session,
        src_id,
        ind_ids,
        valid,
    ) -> int:
        country_str = "+".join(batch_ctrs)
        key = f"{country_str}.S13.G1.*.POGDP_PT.A"
        url = f"{BASE_SOO}/{key}"

        self._rate_limit()
        try:
            resp = _req.get(
                url,
                headers={"Accept": "text/csv"},
                timeout=300,
            )
            resp.raise_for_status()
        except _req.RequestException as e:
            logger.warning("GFS SOO: %s", e)
            return 0

        return self._process_soo(
            resp.text,
            session,
            src_id,
            ind_ids,
            valid,
        )

    # --------------------------------------------------
    # Procesado COFOG
    # --------------------------------------------------

    def _process_cofog(
        self,
        csv_text,
        session,
        src_id,
        ind_ids,
        valid,
    ) -> int:
        """Gasto por función (COFOG) en % PIB."""
        reader = csv.DictReader(io.StringIO(csv_text))
        cache: dict[tuple, int] = {}
        batch: list[dict] = []

        for row in reader:
            country = row.get("COUNTRY", "")
            indicator = row.get("INDICATOR", "")
            period = row.get("TIME_PERIOD", "")
            val_s = row.get("OBS_VALUE", "")

            if not all([country, indicator, period, val_s]):
                continue

            code = _COFOG_MAP.get(indicator)
            if code is None or country not in valid:
                continue

            try:
                val = float(val_s)
            except (ValueError, TypeError):
                continue
            if abs(val) > 200:
                continue

            dt = self._parse_year(period)
            if dt is None:
                continue

            key = (code, country)
            sid = cache.get(key)
            if sid is None:
                sid = self._get_series(
                    session,
                    ind_ids[code],
                    country,
                )
                cache[key] = sid

            batch.append(
                {
                    "series_id": sid,
                    "date": dt,
                    "value": round(val, 4),
                    "source_id": src_id,
                }
            )

        self._upsert(session, batch)
        return len(batch)

    # --------------------------------------------------
    # Procesado SOO (ingresos fiscales)
    # --------------------------------------------------

    def _process_soo(
        self,
        csv_text,
        session,
        src_id,
        ind_ids,
        valid,
    ) -> int:
        """Ingresos fiscales en % PIB.

        Suma sub-partidas porque los agregados
        G11_T / G1_T no tienen datos en la API.
        """
        reader = csv.DictReader(io.StringIO(csv_text))

        # Niveles de agregación income tax
        inc_l1: dict[tuple, float] = {}
        inc_l2: dict[tuple, float] = {}
        inc_l3: dict[tuple, float] = defaultdict(float)
        # Otras categorías impositivas
        tax_cats: dict[tuple, float] = defaultdict(float)

        for row in reader:
            country = row.get("COUNTRY", "")
            indicator = row.get("INDICATOR", "")
            period = row.get("TIME_PERIOD", "")
            val_s = row.get("OBS_VALUE", "")

            if not all([country, indicator, period, val_s]):
                continue
            if country not in valid:
                continue

            try:
                val = float(val_s)
            except (ValueError, TypeError):
                continue
            if abs(val) > 500:
                continue

            dt = self._parse_year(period)
            if dt is None:
                continue

            key = (country, dt)

            # G11_T: agregado total (raro)
            if indicator == "G11_T":
                inc_l1[key] = val
            # G111_T: subtotal income tax
            elif indicator == "G111_T":
                inc_l2[key] = val
            # G1111_T, G1112_T, etc: hojas
            elif indicator.startswith("G111") and indicator.endswith("_T"):
                inc_l3[key] += val

            # G112_T…G116_T: otras categorías
            if indicator in _TAX_CATS:
                tax_cats[key] += val

        # Generar puntos de datos
        all_keys = set(inc_l1) | set(inc_l2) | set(inc_l3) | set(tax_cats)
        cache: dict[tuple, int] = {}
        batch: list[dict] = []

        for key in all_keys:
            country, dt = key

            # Preferir nivel más agregado
            income = inc_l1.get(key)
            if income is None:
                income = inc_l2.get(key)
            if income is None:
                income = inc_l3.get(key, 0)

            if income > 0:
                code = "IMF_GFS_TAX_INCOME"
                sk = (code, country)
                if sk not in cache:
                    cache[sk] = self._get_series(
                        session,
                        ind_ids[code],
                        country,
                    )
                batch.append(
                    {
                        "series_id": cache[sk],
                        "date": dt,
                        "value": round(income, 4),
                        "source_id": src_id,
                    }
                )

            total = income + tax_cats.get(key, 0)
            if total > 0:
                code = "IMF_GFS_TAX_TOTAL"
                sk = (code, country)
                if sk not in cache:
                    cache[sk] = self._get_series(
                        session,
                        ind_ids[code],
                        country,
                    )
                batch.append(
                    {
                        "series_id": cache[sk],
                        "date": dt,
                        "value": round(total, 4),
                        "source_id": src_id,
                    }
                )

        self._upsert(session, batch)
        return len(batch)

    # --------------------------------------------------
    # Utilidades comunes
    # --------------------------------------------------

    @staticmethod
    def _upsert(session, batch: list[dict]) -> None:
        """Upsert por chunks de CHUNK filas."""
        for i in range(0, len(batch), CHUNK):
            chunk = batch[i : i + CHUNK]
            stmt = insert(DataPoint).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=[
                    "series_id",
                    "date",
                ],
                set_={
                    "value": stmt.excluded.value,
                },
            )
            session.execute(stmt)
        if batch:
            session.commit()

    @staticmethod
    def _parse_year(p: str) -> date | None:
        """'2020' → date(2020, 12, 31)."""
        try:
            y = int(p.strip())
            if 1900 <= y <= 2100:
                return date(y, 12, 31)
        except (ValueError, TypeError):
            pass
        return None

    def _ensure_source(self, session) -> int:
        src = (
            session.query(DataSource).filter_by(name=self.SOURCE_NAME).first()
        )
        if not src:
            src = DataSource(
                name=self.SOURCE_NAME,
                display_name=("IMF Government Finance Statistics (GFS)"),
                base_url="https://data.imf.org/",
            )
            session.add(src)
            session.commit()
        return src.id

    @staticmethod
    def _ensure_indicator(session, code, name, cat, src_id) -> int:
        ind = session.query(Indicator).filter_by(code=code).first()
        if ind is None:
            ind = Indicator(
                code=code,
                name=name[:300],
                category=cat,
                frequency="annual",
            )
            session.add(ind)
            session.flush()
            session.add(
                IndicatorSource(
                    indicator_id=ind.id,
                    source_id=src_id,
                    external_code=code,
                    external_name=name[:500],
                )
            )
        return ind.id

    @staticmethod
    def _get_series(session, ind_id, country) -> int:
        s = (
            session.query(Series)
            .filter_by(
                indicator_id=ind_id,
                country_code=country,
                region_code=None,
            )
            .first()
        )
        if s is None:
            s = Series(
                indicator_id=ind_id,
                country_code=country,
                point_count=0,
            )
            session.add(s)
            session.flush()
        return s.id
