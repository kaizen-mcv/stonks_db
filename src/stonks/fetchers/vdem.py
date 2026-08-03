"""Fetcher V-Dem (Varieties of Democracy) v15.

Descarga índices de democracia por país desde V-Dem
(202 países, 1789-2024). Solo se guardan datos desde 1960.
Indicadores: poliarquía, democracia liberal, corrupción,
libertad de prensa e independencia judicial.

Fuente: Coppedge et al. (2024), V-Dem Dataset v15.
Licencia: CC BY-SA 4.0.
"""

import io
import zipfile
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

ZIP_URL = "https://v-dem.net/media/datasets/V-Dem-CY-FullOthers-v16_csv.zip"

# Año mínimo a importar (antes hay datos dispersos)
MIN_YEAR = 1960
# Tamaño máximo de batch para inserts
BATCH_SIZE = 10_000

# Variables V-Dem: (columna_csv, code, nombre, categoría)
VARIABLES = [
    (
        "v2x_polyarchy",
        "VDEM_POLYARCHY",
        "Electoral democracy index (0-1)",
        "governance",
    ),
    (
        "v2x_libdem",
        "VDEM_LIBERAL",
        "Liberal democracy index (0-1)",
        "governance",
    ),
    (
        "v2x_corr",
        "VDEM_CORRUPTION",
        "Political corruption index (0-1)",
        "governance",
    ),
    (
        "v2x_freexp_altinf",
        "VDEM_MEDIA_FREEDOM",
        "Freedom of expression & alt info (0-1)",
        "governance",
    ),
    (
        "v2x_jucon",
        "VDEM_JUDICIAL_INDEP",
        "Judicial constraints on executive (0-1)",
        "governance",
    ),
]


class VDemFetcher(BaseFetcher):
    """V-Dem v15: índices de democracia."""

    SOURCE_NAME = "vdem"
    DOMAIN = "macro"
    RATE_LIMIT = 0

    def fetch(self) -> dict:
        """Descargar y almacenar V-Dem v16."""
        run_id = self._start_run(params={"version": "16"})
        logger.info("V-Dem: descargando ZIP...")
        self._rate_limit()

        resp = self._session.get(ZIP_URL, timeout=300)
        resp.raise_for_status()
        logger.info(
            "V-Dem: %d bytes descargados",
            len(resp.content),
        )

        # Extraer CSV del ZIP
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
        if not csv_names:
            raise ValueError("V-Dem: no se encontró CSV en ZIP")

        cols_needed = ["country_text_id", "year"] + [v[0] for v in VARIABLES]

        with zf.open(csv_names[0]) as f:
            df = pd.read_csv(
                f,
                usecols=lambda c: c in cols_needed,
                low_memory=False,
            )
        df = df[df["year"] >= MIN_YEAR]
        logger.info(
            "V-Dem: %d filas × %d columnas (>=%d)",
            len(df),
            len(df.columns),
            MIN_YEAR,
        )

        session = get_session()
        try:
            src_id = self._ensure_source(session)
            valid = {
                r[0]
                for r in session.execute(text("SELECT code FROM ref.country"))
            }

            total = 0
            for col, code, name, cat in VARIABLES:
                if col not in df.columns:
                    logger.warning(
                        "V-Dem: columna %s no existe",
                        col,
                    )
                    continue
                ind_id = self._ensure_indicator(
                    session, code, name, cat, src_id
                )
                sub = df[
                    [
                        "country_text_id",
                        "year",
                        col,
                    ]
                ].dropna(subset=[col])
                batch = []
                for _, row in sub.iterrows():
                    iso3 = str(row["country_text_id"])
                    if iso3 not in valid:
                        continue
                    sid = self._get_series(session, ind_id, iso3)
                    batch.append(
                        {
                            "series_id": sid,
                            "date": date(int(row["year"]), 12, 31),
                            "value": float(row[col]),
                            "source_id": src_id,
                        }
                    )
                    # Insertar por lotes de BATCH_SIZE
                    if len(batch) >= BATCH_SIZE:
                        self._flush_batch(session, batch)
                        total += len(batch)
                        batch = []

                # Insertar lote restante
                if batch:
                    self._flush_batch(session, batch)
                    total += len(batch)

                logger.info(
                    "V-Dem %s: completado",
                    code,
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
            logger.error("V-Dem: %s", e)
            return {"error": str(e)}
        finally:
            session.close()

    @staticmethod
    def _flush_batch(session, batch: list) -> None:
        """Insertar lote con upsert."""
        stmt = insert(DataPoint).values(batch)
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
                display_name=("V-Dem (Varieties of Democracy)"),
                base_url=("https://v-dem.net/data/the-v-dem-dataset/"),
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
