"""Fetcher Penn World Table 11.0 (Dataverse, Stata).

Descarga TFP y productividad por país desde PWT 11.0 (185 países,
1950-2023). Los datos se almacenan en macro como indicadores anuales.

Fuente: Feenstra, Inklaar & Timmer (2015), AER 105(10).
Licencia: CC BY 4.0.
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

STATA_URL = "https://dataverse.nl/api/access/datafile/554030"

# Variables PWT a extraer:
# (columna, code, nombre, categoría, unidad)
#
# La unidad la documenta PWT y no se puede deducir del nombre:
# `rkna` y `rtfpna` son índices con base 2017=1, no importes, y
# `labsh` e `irr` son fracciones (0,52 y 0,11), no porcentajes.
VARIABLES = [
    (
        "ctfp",
        "PWT_TFP_LEVEL",
        "TFP level at current PPPs (USA=1)",
        "productivity",
        "index",
    ),
    (
        "rtfpna",
        "PWT_TFP_NATIONAL",
        "TFP at constant national prices",
        "productivity",
        "index",
    ),
    (
        "labsh",
        "PWT_LABOR_SHARE",
        "Labour share of GDP",
        "productivity",
        "ratio",
    ),
    (
        "hc",
        "PWT_HUMAN_CAPITAL",
        "Human capital index",
        "education",
        "index",
    ),
    (
        "rgdpna",
        "PWT_REAL_GDP",
        "Real GDP at constant nat. prices",
        "national_accounts",
        "usd_millions",
    ),
    (
        "rkna",
        "PWT_CAPITAL_STOCK",
        "Capital stock at const. nat. prices",
        "national_accounts",
        "index",
    ),
    (
        "irr",
        "PWT_IRR",
        "Internal rate of return on capital",
        "productivity",
        "ratio",
    ),
    (
        "avh",
        "PWT_AVG_HOURS",
        "Average annual hours worked",
        "labor",
        "hours",
    ),
]


class PWTFetcher(BaseFetcher):
    """Penn World Table 11.0: TFP y productividad."""

    SOURCE_NAME = "pwt"
    DOMAIN = "macro"
    RATE_LIMIT = 0

    def fetch(self) -> dict:
        """Descargar y almacenar PWT 11.0."""
        run_id = self._start_run(params={"version": "11.0"})
        logger.info("PWT: descargando Stata file...")
        self._rate_limit()
        resp = self._session.get(STATA_URL, timeout=120)
        resp.raise_for_status()

        df = pd.read_stata(io.BytesIO(resp.content))
        logger.info(
            "PWT: %d filas × %d columnas",
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
            for col, code, name, cat, unidad in VARIABLES:
                if col not in df.columns:
                    logger.warning("PWT: columna %s no existe", col)
                    continue
                ind_id = self._ensure_indicator(
                    session, code, name, cat, src_id, unidad
                )
                sub = df[["countrycode", "year", col]].dropna(subset=[col])
                batch = []
                for _, row in sub.iterrows():
                    iso3 = str(row["countrycode"])
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

                if batch:
                    stmt = insert(DataPoint).values(batch)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["series_id", "date"],
                        set_={"value": stmt.excluded.value},
                    )
                    session.execute(stmt)
                    session.commit()
                    total += len(batch)
                    logger.info(
                        "PWT %s: %d puntos",
                        code,
                        len(batch),
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
            logger.error("PWT: %s", e)
            return {"error": str(e)}
        finally:
            session.close()

    def _ensure_source(self, session) -> int:
        src = (
            session.query(DataSource).filter_by(name=self.SOURCE_NAME).first()
        )
        if not src:
            src = DataSource(
                name=self.SOURCE_NAME,
                display_name=("Penn World Table 11.0"),
                base_url=("https://www.rug.nl/ggdc/productivity/pwt/"),
            )
            session.add(src)
            session.commit()
        return src.id

    @staticmethod
    def _ensure_indicator(
        session, code, name, cat, src_id, unidad=None
    ) -> int:
        ind = session.query(Indicator).filter_by(code=code).first()
        if ind is None:
            ind = Indicator(
                code=code,
                name=name[:300],
                category=cat,
                frequency="annual",
                unit=unidad,
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
