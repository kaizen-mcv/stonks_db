"""Fetcher IMF IMTS (International Merchandise Trade
Statistics) — SDMX 3.0 CSV.

Descarga datos anuales de comercio agregado del endpoint
api.imf.org (SDMX 3.0). Exportaciones FOB e importaciones
CIF totales por país (vs mundo G001). Cobertura: ~200
países, datos desde 1947 en algunos casos.

Países se agrupan en batches de 40 (concatenados con +)
porque la API no soporta wildcards en la dimensión país.

Nota: Este dataflow sustituye al antiguo DOT (Direction
of Trade Statistics) desde la migración SDMX 3.0.
"""

import csv
import io
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

BASE = "https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/IMTS/1.0.0"

# (code, imts_indicator, name, category)
IMTS_SERIES = [
    (
        "IMF_DOTS_EXPORTS",
        "XG_FOB_USD",
        "Total exports FOB (USD millions)",
        "trade",
    ),
    (
        "IMF_DOTS_IMPORTS",
        "MG_CIF_USD",
        "Total imports CIF (USD millions)",
        "trade",
    ),
]

_KEY_MAP = {ind: code for code, ind, _, _ in IMTS_SERIES}

BATCH_SIZE = 40
CHUNK = 10_000


class IMFDOTSFetcher(BaseFetcher):
    """IMF IMTS: comercio anual agregado por país."""

    SOURCE_NAME = "imf_dots"
    DOMAIN = "macro"
    RATE_LIMIT = 3.0

    def fetch(self) -> dict:
        run_id = self._start_run(params={"series": len(IMTS_SERIES)})

        session = get_session()
        try:
            src_id = self._ensure_source(session)
            valid = {
                r[0]
                for r in session.execute(text("SELECT code FROM ref.country"))
            }
            countries = sorted(valid)

            ind_ids = {}
            for code, _, name, cat in IMTS_SERIES:
                ind_ids[code] = self._ensure_indicator(
                    session, code, name, cat, src_id
                )
            session.commit()

            indicators = "+".join(ind for _, ind, _, _ in IMTS_SERIES)

            total = 0
            batches = [
                countries[i : i + BATCH_SIZE]
                for i in range(0, len(countries), BATCH_SIZE)
            ]

            for bi, batch_countries in enumerate(batches):
                country_str = "+".join(batch_countries)
                # Clave SDMX 3.0 IMTS:
                # COUNTRY.INDICATOR.COUNTERPART.FREQ
                key = f"{country_str}.{indicators}.G001.A"
                url = f"{BASE}/{key}"

                self._rate_limit()
                try:
                    resp = _req.get(
                        url,
                        headers={
                            "Accept": "text/csv",
                        },
                        timeout=180,
                    )
                    resp.raise_for_status()
                except _req.RequestException as e:
                    logger.warning(
                        "IMTS batch %d/%d falló: %s",
                        bi + 1,
                        len(batches),
                        e,
                    )
                    continue

                n = self._process_csv(
                    resp.text,
                    session,
                    src_id,
                    ind_ids,
                    valid,
                )
                total += n
                logger.info(
                    "IMTS batch %d/%d: %d puntos",
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
            logger.info("IMF IMTS total: %d puntos", total)
        except Exception as e:
            self._finish_run(
                run_id,
                "failed",
                error_log={"msg": str(e)},
            )
            logger.error("IMF IMTS falló: %s", e)
            raise
        finally:
            session.close()

        return {
            "series": len(IMTS_SERIES),
            "puntos": total,
        }

    def _process_csv(
        self,
        csv_text: str,
        session,
        src_id: int,
        ind_ids: dict[str, int],
        valid: set[str],
    ) -> int:
        reader = csv.DictReader(io.StringIO(csv_text))
        cache: dict[tuple[str, str], int] = {}
        batch: list[dict] = []
        max_val = 10**14 - 1

        for row in reader:
            country = row.get("COUNTRY", "")
            indicator = row.get("INDICATOR", "")
            period = row.get("TIME_PERIOD", "")
            val_s = row.get("OBS_VALUE", "")

            if not all([country, indicator, period, val_s]):
                continue

            code = _KEY_MAP.get(indicator)
            if code is None or country not in valid:
                continue

            try:
                val = float(val_s)
            except (ValueError, TypeError):
                continue

            if abs(val) >= max_val:
                continue

            # IMTS devuelve USD; convertir a millones
            val_mn = val / 1e6

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
                    "value": round(val_mn, 4),
                    "source_id": src_id,
                }
            )

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
        session.commit()
        return len(batch)

    @staticmethod
    def _parse_year(p: str) -> date | None:
        """'2023' → date(2023, 12, 31)."""
        try:
            y = int(p)
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
                display_name=(
                    "IMF International Merchandise Trade Statistics (IMTS)"
                ),
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
