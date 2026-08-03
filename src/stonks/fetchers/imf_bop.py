"""Fetcher IMF BOP (Balance of Payments) — SDMX 3.0 CSV.

Descarga componentes trimestrales de balanza de pagos del endpoint
api.imf.org (SDMX 3.0). Cobertura: ~200 países, datos desde 1948
en algunos casos. Complementa los datos anuales de World Bank con
granularidad trimestral.

Países se agrupan en batches de 40 (concatenados con +) porque la
API no soporta wildcards en la dimensión país.
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

BASE = "https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/BOP/21.0.0"

# (code, bop_entry, bop_indicator, name, category)
BOP_SERIES = [
    (
        "IMF_BOP_CAB_Q",
        "NETCD_T",
        "CAB",
        "Current account balance, quarterly",
        "external",
    ),
    (
        "IMF_BOP_GOODS_X_Q",
        "CD_T",
        "G",
        "Goods exports (credit), quarterly",
        "trade",
    ),
    (
        "IMF_BOP_GOODS_M_Q",
        "DB_T",
        "G",
        "Goods imports (debit), quarterly",
        "trade",
    ),
    (
        "IMF_BOP_SVCS_X_Q",
        "CD_T",
        "S",
        "Services exports (credit), quarterly",
        "trade",
    ),
    (
        "IMF_BOP_SVCS_M_Q",
        "DB_T",
        "S",
        "Services imports (debit), quarterly",
        "trade",
    ),
    (
        "IMF_BOP_INCOME1_Q",
        "NETCD_T",
        "IN1",
        "Primary income net, quarterly",
        "external",
    ),
    (
        "IMF_BOP_INCOME2_Q",
        "NETCD_T",
        "IN2",
        "Secondary income net, quarterly",
        "external",
    ),
    (
        "IMF_BOP_FDI_Q",
        "NETCD_T",
        "D",
        "Direct investment net, quarterly",
        "external",
    ),
    (
        "IMF_BOP_FA_Q",
        "NETCD_T",
        "FAB",
        "Financial account balance, quarterly",
        "external",
    ),
]

# Mapa (entry, indicator) → nuestro código
_KEY_MAP = {(entry, ind): code for code, entry, ind, _, _ in BOP_SERIES}

BATCH_SIZE = 40
CHUNK = 10_000


class IMFBOPFetcher(BaseFetcher):
    """IMF BOP: componentes trimestrales de balanza de pagos."""

    SOURCE_NAME = "imf_bop"
    DOMAIN = "macro"
    RATE_LIMIT = 3.0

    def fetch(self) -> dict:
        run_id = self._start_run(params={"series": len(BOP_SERIES)})

        session = get_session()
        try:
            src_id = self._ensure_source(session)
            valid = {
                r[0]
                for r in session.execute(text("SELECT code FROM ref.country"))
            }
            countries = sorted(valid)

            # Crear indicadores
            ind_ids = {}
            for code, _, _, name, cat in BOP_SERIES:
                ind_ids[code] = self._ensure_indicator(
                    session, code, name, cat, src_id
                )
            session.commit()

            # Construir los filtros de la API
            entries = "+".join(sorted({e for _, e, _, _, _ in BOP_SERIES}))
            indicators = "+".join(sorted({i for _, _, i, _, _ in BOP_SERIES}))

            total = 0
            batches = [
                countries[i : i + BATCH_SIZE]
                for i in range(0, len(countries), BATCH_SIZE)
            ]

            for bi, batch_countries in enumerate(batches):
                country_str = "+".join(batch_countries)
                key = f"{country_str}.{entries}.{indicators}.USD.Q"
                url = f"{BASE}/{key}"

                self._rate_limit()
                try:
                    resp = _req.get(
                        url,
                        headers={"Accept": "text/csv"},
                        timeout=180,
                    )
                    resp.raise_for_status()
                except _req.RequestException as e:
                    logger.warning(
                        "BOP batch %d/%d falló: %s",
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
                    "BOP batch %d/%d: %d puntos",
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
            logger.info("IMF BOP total: %d puntos", total)
        except Exception as e:
            self._finish_run(
                run_id,
                "failed",
                error_log={"msg": str(e)},
            )
            logger.error("IMF BOP falló: %s", e)
            raise
        finally:
            session.close()

        return {
            "series": len(BOP_SERIES),
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
            entry = row.get("BOP_ACCOUNTING_ENTRY", "")
            indicator = row.get("INDICATOR", "")
            period = row.get("TIME_PERIOD", "")
            val_s = row.get("OBS_VALUE", "")

            if not all([country, entry, indicator, period, val_s]):
                continue

            code = _KEY_MAP.get((entry, indicator))
            if code is None or country not in valid:
                continue

            try:
                val = float(val_s)
            except (ValueError, TypeError):
                continue

            if abs(val) >= max_val:
                continue

            # Convertir a miles de millones USD
            val_bn = val / 1e9

            dt = self._parse_quarter(period)
            if dt is None:
                continue

            key = (code, country)
            sid = cache.get(key)
            if sid is None:
                sid = self._get_series(session, ind_ids[code], country)
                cache[key] = sid

            batch.append(
                {
                    "series_id": sid,
                    "date": dt,
                    "value": round(val_bn, 4),
                    "source_id": src_id,
                }
            )

        # Upsert por chunks
        for i in range(0, len(batch), CHUNK):
            chunk = batch[i : i + CHUNK]
            stmt = insert(DataPoint).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=["series_id", "date"],
                set_={"value": stmt.excluded.value},
            )
            session.execute(stmt)
        session.commit()
        return len(batch)

    @staticmethod
    def _parse_quarter(p: str) -> date | None:
        """'2025-Q1' → date(2025, 3, 31)."""
        try:
            if "-Q" in p:
                y, q = p.split("-Q")
                q_end = {
                    "1": (3, 31),
                    "2": (6, 30),
                    "3": (9, 30),
                    "4": (12, 31),
                }
                m, d = q_end.get(q, (12, 31))
                return date(int(y), m, d)
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
                display_name=("IMF Balance of Payments (BOP)"),
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
                frequency="quarterly",
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
    def _get_series(session, ind_id, iso3) -> int:
        s = (
            session.query(Series)
            .filter_by(
                indicator_id=ind_id,
                country_code=iso3,
                region_code=None,
            )
            .first()
        )
        if s is None:
            s = Series(
                indicator_id=ind_id,
                country_code=iso3,
                point_count=0,
            )
            session.add(s)
            session.flush()
        return s.id
