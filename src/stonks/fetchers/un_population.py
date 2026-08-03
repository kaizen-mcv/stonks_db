"""Fetcher UN DESA World Population Prospects 2024.

Descarga indicadores demográficos por país desde
UN DESA WPP 2024 (237 países/regiones, 1950-2100).
Se filtran solo países (no agregados) y años 1950-2030.
Los datos se almacenan en macro como indicadores anuales.

Fuente: United Nations, DESA, Population Division.
Licencia: libre acceso.
"""

import gzip
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
    "https://population.un.org/wpp/assets/"
    "Excel%20Files/1_Indicator%20(Standard)/"
    "CSV_FILES/"
    "WPP2024_Demographic_Indicators_Medium"
    ".csv.gz"
)

# Año máximo a importar (excluir proyecciones lejanas)
MAX_YEAR = 2030
MIN_YEAR = 1950
BATCH_SIZE = 10_000

# Variables a extraer: (columna_csv, code, nombre, cat)
VARIABLES = [
    (
        "TPopulation1July",
        "UNDESA_POP_TOTAL",
        "Total population mid-year (thousands)",
        "demography",
    ),
    (
        "MedianAgePop",
        "UNDESA_MEDIAN_AGE",
        "Median age of population",
        "demography",
    ),
    (
        "PopOldDependRatio1",
        "UNDESA_DEPEND_OLD",
        "Old-age dependency ratio (%)",
        "demography",
    ),
    (
        "PopYoungDependRatio1",
        "UNDESA_DEPEND_YOUNG",
        "Young dependency ratio (%)",
        "demography",
    ),
    (
        "TFR",
        "UNDESA_FERTILITY",
        "Total fertility rate",
        "demography",
    ),
]


class UNPopulationFetcher(BaseFetcher):
    """UN DESA World Population Prospects 2024."""

    SOURCE_NAME = "un_population"
    DOMAIN = "macro"
    RATE_LIMIT = 0

    def fetch(self) -> dict:
        """Descargar y almacenar WPP 2024."""
        run_id = self._start_run(params={"version": "WPP2024"})
        logger.info("UN Population: descargando CSV demográfico...")
        self._rate_limit()
        resp = self._session.get(CSV_URL, timeout=300)
        resp.raise_for_status()

        raw = gzip.decompress(resp.content)
        df = pd.read_csv(
            io.BytesIO(raw),
            low_memory=False,
        )
        logger.info(
            "UN Population: %d filas × %d columnas",
            len(df),
            len(df.columns),
        )

        # Filtrar solo países (excluir regiones)
        if "LocTypeName" in df.columns:
            df = df[df["LocTypeName"] == "Country/Area"]
        else:
            logger.warning(
                "UN Population: columna LocTypeName "
                "no encontrada, se importan todas"
            )

        # Filtrar rango de años
        df = df[(df["Time"] >= MIN_YEAR) & (df["Time"] <= MAX_YEAR)]
        logger.info(
            "UN Population: %d filas tras filtrar países y años %d-%d",
            len(df),
            MIN_YEAR,
            MAX_YEAR,
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
                    logger.warning("UN Population: columna %s no existe", col)
                    continue
                ind_id = self._ensure_indicator(
                    session, code, name, cat, src_id
                )
                sub = df[["ISO3_code", "Time", col]].dropna(subset=[col])
                batch = []
                for _, row in sub.iterrows():
                    iso3 = str(row["ISO3_code"])
                    if iso3 not in valid:
                        continue
                    sid = self._get_series(session, ind_id, iso3)
                    batch.append(
                        {
                            "series_id": sid,
                            "date": date(int(row["Time"]), 7, 1),
                            "value": float(row[col]),
                            "source_id": src_id,
                        }
                    )
                    # Insertar en lotes de BATCH_SIZE
                    if len(batch) >= BATCH_SIZE:
                        self._upsert_batch(session, batch)
                        total += len(batch)
                        batch = []

                if batch:
                    self._upsert_batch(session, batch)
                    total += len(batch)
                logger.info(
                    "UN Population %s: %d puntos",
                    code,
                    sub[sub["ISO3_code"].isin(valid)].shape[0],
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
            logger.error("UN Population: %s", e)
            return {"error": str(e)}
        finally:
            session.close()

    @staticmethod
    def _upsert_batch(session, batch: list) -> None:
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
                display_name=("UN DESA World Population Prospects 2024"),
                base_url=("https://population.un.org/wpp/"),
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
