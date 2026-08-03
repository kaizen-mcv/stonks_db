"""Fetcher EDGAR v8.0 (emisiones GEI por país y sector).

Descarga emisiones de gases de efecto invernadero desde
EDGAR (Emissions Database for Global Atmospheric Research)
del JRC de la Comisión Europea. Cubre 200+ países,
1970-2022. Los datos se almacenan en macro como
indicadores anuales.

Fuente: European Commission, JRC, EDGAR v8.0_FT2022.
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

XLSX_URL = (
    "https://edgar.jrc.ec.europa.eu/booklet/EDGAR_2025_GHG_booklet_2025.xlsx"
)

# Variables EDGAR: (sector/gas, code, nombre, categoría)
VARIABLES = [
    (
        "co2_energy",
        "EDGAR_CO2_ENERGY",
        "CO2 emissions from energy sector (Mt)",
        "environment",
    ),
    (
        "co2_industry",
        "EDGAR_CO2_INDUSTRY",
        "CO2 emissions from industry (Mt)",
        "environment",
    ),
    (
        "ch4",
        "EDGAR_CH4",
        "Methane emissions (Mt CO2eq)",
        "environment",
    ),
    (
        "n2o",
        "EDGAR_N2O",
        "Nitrous oxide emissions (Mt CO2eq)",
        "environment",
    ),
]

BATCH_SIZE = 10_000


class EDGAREmissionsFetcher(BaseFetcher):
    """EDGAR v8.0: emisiones GEI por país."""

    SOURCE_NAME = "edgar"
    DOMAIN = "macro"
    RATE_LIMIT = 0

    def fetch(self) -> dict:
        """Descargar y almacenar EDGAR v8.0."""
        run_id = self._start_run(params={"version": "v8.0_FT2022"})
        logger.info("EDGAR: descargando XLSX...")
        self._rate_limit()
        resp = self._session.get(XLSX_URL, timeout=180)
        resp.raise_for_status()

        raw = self._parse_xlsx(resp.content)

        logger.info(
            "EDGAR: %d filas parseadas",
            len(raw),
        )

        session = get_session()
        try:
            src_id = self._ensure_source(session)
            valid = {
                r[0]
                for r in session.execute(text("SELECT code FROM ref.country"))
            }

            total = 0
            for var_key, code, name, cat in VARIABLES:
                ind_id = self._ensure_indicator(
                    session, code, name, cat, src_id
                )
                sub = raw.loc[
                    raw["variable"] == var_key,
                    ["iso3", "year", "value"],
                ].dropna(subset=["value"])

                batch: list[dict] = []
                for _, row in sub.iterrows():
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
                    # Insertar por lotes de BATCH_SIZE
                    if len(batch) >= BATCH_SIZE:
                        self._upsert_batch(session, batch)
                        total += len(batch)
                        batch = []

                if batch:
                    self._upsert_batch(session, batch)
                    total += len(batch)

                logger.info(
                    "EDGAR %s: %d puntos",
                    code,
                    sub[sub["iso3"].isin(valid)].shape[0],
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
            logger.error("EDGAR: %s", e)
            return {"error": str(e)}
        finally:
            session.close()

    # --------------------------------------------------
    # Parseo de datos
    # --------------------------------------------------

    # Sectores energéticos vs industriales
    _ENERGY_SECTORS = {
        "Power Industry",
        "Buildings",
        "Transport",
        "Fuel Exploitation",
    }
    _INDUSTRY_SECTORS = {
        "Industrial Combustion",
        "Processes",
    }

    def _parse_xlsx(self, content: bytes) -> pd.DataFrame:
        """Parsea EDGAR 2025 XLSX (by sector)."""
        try:
            xls = pd.ExcelFile(
                io.BytesIO(content),
                engine="openpyxl",
            )
        except Exception:
            logger.warning("EDGAR: no se pudo abrir XLSX")
            return pd.DataFrame()

        # Buscar hoja con datos por sector
        sheet = None
        for s in xls.sheet_names:
            if "sector" in s.lower():
                sheet = s
                break
        if sheet is None:
            logger.warning("EDGAR: hoja sector no encontrada")
            return pd.DataFrame()

        df = pd.read_excel(xls, sheet_name=sheet)
        iso_col = next(
            (c for c in df.columns if "country code" in str(c).lower()),
            None,
        )
        if iso_col is None:
            return pd.DataFrame()

        year_cols = [c for c in df.columns if _is_year_col(c)]

        frames: list[pd.DataFrame] = []
        # CO2 energía
        mask_e = (df["Substance"] == "CO2") & df["Sector"].isin(
            self._ENERGY_SECTORS
        )
        frames.append(
            self._agg_melt(
                df[mask_e],
                iso_col,
                year_cols,
                "co2_energy",
            )
        )
        # CO2 industria
        mask_i = (df["Substance"] == "CO2") & df["Sector"].isin(
            self._INDUSTRY_SECTORS
        )
        frames.append(
            self._agg_melt(
                df[mask_i],
                iso_col,
                year_cols,
                "co2_industry",
            )
        )
        # CH4
        mask_ch4 = df["Substance"].str.contains("CH4", na=False)
        frames.append(
            self._agg_melt(
                df[mask_ch4],
                iso_col,
                year_cols,
                "ch4",
            )
        )
        # N2O
        mask_n2o = df["Substance"].str.contains("N2O", na=False)
        frames.append(
            self._agg_melt(
                df[mask_n2o],
                iso_col,
                year_cols,
                "n2o",
            )
        )

        result = pd.concat(
            [f for f in frames if not f.empty],
            ignore_index=True,
        )
        return result

    @staticmethod
    def _agg_melt(
        df: pd.DataFrame,
        iso_col: str,
        year_cols: list,
        var_key: str,
    ) -> pd.DataFrame:
        """Suma sectores por país y melt a largo."""
        if df.empty:
            return pd.DataFrame()
        agg = df.groupby(iso_col)[year_cols].sum().reset_index()
        melted = agg.melt(
            id_vars=[iso_col],
            value_vars=year_cols,
            var_name="year",
            value_name="value",
        )
        melted = melted.rename(columns={iso_col: "iso3"})
        melted["year"] = pd.to_numeric(melted["year"], errors="coerce")
        melted["value"] = pd.to_numeric(melted["value"], errors="coerce")
        melted["variable"] = var_key
        return melted.dropna(subset=["year", "value"])

    # --------------------------------------------------
    # Inserción y metadatos
    # --------------------------------------------------

    @staticmethod
    def _upsert_batch(session, batch: list[dict]) -> None:
        """Inserta un lote con upsert."""
        stmt = insert(DataPoint).values(batch)
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

    def _ensure_source(self, session) -> int:
        src = (
            session.query(DataSource).filter_by(name=self.SOURCE_NAME).first()
        )
        if not src:
            src = DataSource(
                name=self.SOURCE_NAME,
                display_name=("EDGAR v8.0 (JRC, European Commission)"),
                base_url=XLSX_URL,
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


def _is_year_col(col) -> bool:
    """Comprueba si una columna es un año."""
    try:
        val = int(col)
        return 1950 <= val <= 2100
    except (ValueError, TypeError):
        return False
