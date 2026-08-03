"""Fetcher UNDP Human Development Index (HDR 2025).

Descarga los índices compuestos de desarrollo humano desde
el portal HDR de Naciones Unidas. Cubre 190+ países,
1990-2023 con cuatro indicadores: HDI, GDI, GII y MPI.

Fuente: UNDP Human Development Report Office.
Licencia: datos públicos.
"""

import io
from datetime import date

import pandas as pd
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

CSV_URL = (
    "https://hdr.undp.org/sites/default/files/"
    "2025_HDR/HDR25_Composite_indices"
    "_complete_time_series.csv"
)

# Prefijo CSV → (código indicador, nombre, categoría)
VARIABLES = [
    (
        "hdi",
        "UNDP_HDI",
        "Human Development Index (0-1)",
        "development",
    ),
    (
        "gdi",
        "UNDP_GDI",
        "Gender Development Index",
        "development",
    ),
    (
        "gii",
        "UNDP_GII",
        "Gender Inequality Index (0-1)",
        "development",
    ),
    (
        "mpi",
        "UNDP_MPI",
        "Multidimensional Poverty Index",
        "poverty",
    ),
]

# Tamaño máximo de lote para INSERT
_BATCH_SIZE = 10_000


class UNDPFetcher(BaseFetcher):
    """UNDP Human Development Report: HDI, GDI, GII, MPI."""

    SOURCE_NAME = "undp"
    DOMAIN = "macro"
    RATE_LIMIT = 0

    def fetch(self) -> dict:
        """Descargar y almacenar índices UNDP."""
        run_id = self._start_run(params={"edition": "2025"})
        logger.info("UNDP: descargando CSV HDR...")
        self._rate_limit()
        resp = self._session.get(CSV_URL, timeout=120)
        resp.raise_for_status()

        df = pd.read_csv(
            io.StringIO(resp.text),
            na_values=["", ".."],
        )
        # Normalizar nombres de columna a minúsculas
        df.columns = [c.strip().lower() for c in df.columns]
        logger.info(
            "UNDP: %d filas × %d columnas",
            len(df),
            len(df.columns),
        )

        session = get_session()
        try:
            src_id = self._ensure_source(session)
            valid = {
                r[0]
                for r in session.execute(text("SELECT code FROM ref.country"))
            }

            total = 0
            for prefix, code, name, cat in VARIABLES:
                ind_id = self._ensure_indicator(
                    session, code, name, cat, src_id
                )
                melted = self._melt_indicator(df, prefix)
                if melted.empty:
                    logger.warning("UNDP: sin datos para %s", code)
                    continue

                batch: list[dict] = []
                for _, row in melted.iterrows():
                    iso3 = str(row["iso3"])
                    if iso3 not in valid:
                        continue
                    sid = self._get_series(session, ind_id, iso3)
                    batch.append(
                        {
                            "series_id": sid,
                            "date": date(int(row["year"]), 12, 31),
                            "value": float(row["value"]),
                            "source_id": src_id,
                        }
                    )

                    # Insertar en lotes de _BATCH_SIZE
                    if len(batch) >= _BATCH_SIZE:
                        self._upsert_batch(session, batch)
                        total += len(batch)
                        batch = []

                # Lote final
                if batch:
                    self._upsert_batch(session, batch)
                    total += len(batch)

                logger.info(
                    "UNDP %s: %d puntos",
                    code,
                    total,
                )

            self._finish_run(
                run_id,
                "success",
                fetched=total,
                inserted=total,
            )
            return {
                "variables": len(VARIABLES),
                "puntos": total,
            }
        except Exception as e:  # noqa: BLE001
            session.rollback()
            self._finish_run(
                run_id,
                "failed",
                error_log={"msg": str(e)},
            )
            logger.error("UNDP: %s", e)
            return {"error": str(e)}
        finally:
            session.close()

    # ── Helpers privados ─────────────────────────

    @staticmethod
    def _melt_indicator(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
        """Convertir columnas anchas (prefix_YYYY) a
        formato largo con columnas [iso3, year, value]."""
        # Seleccionar columnas del indicador
        year_cols = [
            c
            for c in df.columns
            if c.startswith(f"{prefix}_") and c.split("_")[-1].isdigit()
        ]
        if not year_cols:
            return pd.DataFrame()

        melted = df[["iso3"] + year_cols].melt(
            id_vars=["iso3"],
            value_vars=year_cols,
            var_name="col",
            value_name="value",
        )
        # Extraer año del nombre de columna
        melted["year"] = melted["col"].str.split("_").str[-1].astype(int)
        melted = melted.drop(columns=["col"])
        melted = melted.dropna(subset=["value"])
        return melted.reset_index(drop=True)

    @staticmethod
    def _upsert_batch(session, batch: list[dict]):
        """Insertar lote con upsert por
        (series_id, date). Deduplica dentro del lote."""
        seen: dict[tuple, dict] = {}
        for rec in batch:
            k = (rec["series_id"], rec["date"])
            seen[k] = rec
        deduped = list(seen.values())
        if not deduped:
            return
        stmt = insert(DataPoint).values(deduped)
        stmt = stmt.on_conflict_do_update(
            index_elements=["series_id", "date"],
            set_={"value": stmt.excluded.value},
        )
        session.execute(stmt)
        session.commit()

    def _ensure_source(self, session) -> int:
        src = (
            session.query(DataSource).filter_by(name=self.SOURCE_NAME).first()
        )
        if not src:
            src = DataSource(
                name=self.SOURCE_NAME,
                display_name=("UNDP Human Development Report"),
                base_url="https://hdr.undp.org/",
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

    _series_cache: dict[tuple, int] = {}

    def _get_series(self, session, ind_id, iso3) -> int:
        key = (ind_id, iso3)
        if key in self._series_cache:
            return self._series_cache[key]
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
        self._series_cache[key] = s.id
        return s.id
