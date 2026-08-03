"""Fetcher UNESCO Institute for Statistics (UIS).

Descarga indicadores de educación desde UIS: tasa de
alfabetización, años medios de escolaridad y ratio
alumno-profesor (primaria). Datos por país/año.

Fuente: UNESCO Institute for Statistics.
Licencia: Open Data.
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

_BASE_DL = "https://download.uis.unesco.org/bdds/202602/"
_ZIPS = [
    ("SDG.zip", "SDG_DATA_NATIONAL.csv"),
    ("OPRI.zip", "OPRI_DATA_NATIONAL.csv"),
]

# Variables UIS a extraer:
# (código UIS, code interno, nombre, categoría)
VARIABLES = [
    (
        "LR.AG15T99",
        "UNESCO_LITERACY",
        "Adult literacy rate (%)",
        "education",
    ),
    (
        "MYS.1T8.AG25T99",
        "UNESCO_MEAN_SCHOOL_YEARS",
        "Mean years of schooling (25+)",
        "education",
    ),
    (
        "PTRHC.1.TRAINED",
        "UNESCO_PUPIL_TEACHER",
        "Pupil-trained teacher ratio primary",
        "education",
    ),
]

BATCH_SIZE = 10_000


class UNESCOFetcher(BaseFetcher):
    """UNESCO UIS: indicadores de educación."""

    SOURCE_NAME = "unesco"
    DOMAIN = "macro"
    RATE_LIMIT = 0

    def fetch(self) -> dict:
        """Descargar y almacenar datos UIS."""
        run_id = self._start_run(params={"dataset": "BDDS-202602"})
        uis_codes = {v[0] for v in VARIABLES}
        frames: list[pd.DataFrame] = []
        for zip_name, csv_name in _ZIPS:
            url = _BASE_DL + zip_name
            logger.info("UNESCO: descargando %s...", zip_name)
            self._rate_limit()
            resp = self._session.get(url, timeout=300)
            resp.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                with zf.open(csv_name) as f:
                    chunk = pd.read_csv(
                        f,
                        low_memory=False,
                        usecols=[
                            "INDICATOR_ID",
                            "COUNTRY_ID",
                            "YEAR",
                            "VALUE",
                        ],
                        dtype={
                            "INDICATOR_ID": str,
                        },
                    )
                # Filtrar solo indicadores deseados
                chunk = chunk[chunk["INDICATOR_ID"].isin(uis_codes)]
                logger.info(
                    "UNESCO %s: %d filas relevantes",
                    zip_name,
                    len(chunk),
                )
                frames.append(chunk)

        df = pd.concat(frames, ignore_index=True)
        logger.info(
            "UNESCO: %d filas × %d columnas",
            len(df),
            len(df.columns),
        )

        col_indicator = "INDICATOR_ID"
        col_country = "COUNTRY_ID"
        col_time = "YEAR"
        col_value = "VALUE"

        session = get_session()
        try:
            src_id = self._ensure_source(session)
            valid = {
                r[0]
                for r in session.execute(text("SELECT code FROM ref.country"))
            }

            df_filtered = df

            total = 0
            for uis_code, code, name, cat in VARIABLES:
                ind_id = self._ensure_indicator(
                    session, code, name, cat, src_id
                )
                sub = df_filtered.loc[
                    df_filtered[col_indicator] == uis_code
                ].copy()
                sub = sub.dropna(subset=[col_value])

                batch: list[dict] = []
                for _, row in sub.iterrows():
                    iso3 = str(row[col_country]).strip().upper()
                    if iso3 not in valid:
                        continue
                    try:
                        year = int(float(row[col_time]))
                        val = float(row[col_value])
                    except (ValueError, TypeError):
                        continue

                    sid = self._get_series(session, ind_id, iso3)
                    batch.append(
                        {
                            "series_id": sid,
                            "date": date(year, 12, 31),
                            "value": val,
                            "source_id": src_id,
                        }
                    )

                    # Insertar por lotes
                    if len(batch) >= BATCH_SIZE:
                        self._flush(session, batch)
                        total += len(batch)
                        batch = []

                if batch:
                    self._flush(session, batch)
                    total += len(batch)

                logger.info(
                    "UNESCO %s: %d puntos",
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
            logger.error("UNESCO: %s", e)
            return {"error": str(e)}
        finally:
            session.close()

    @staticmethod
    def _flush(session, batch: list[dict]) -> None:
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
                display_name=("UNESCO Institute for Statistics"),
                base_url=("https://uis.unesco.org/"),
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
