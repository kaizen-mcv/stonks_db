"""Fetcher ND-GAIN Country Index (vulnerabilidad climática).

Descarga el índice ND-GAIN de adaptación climática por país
(192 países, 1995-2022). Tres indicadores: score global,
vulnerabilidad y preparación. Datos anuales almacenados en
el esquema macro.

Fuente: Notre Dame Global Adaptation Initiative.
Licencia: Creative Commons (uso académico/investigación).
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

# ZIP con CSVs por métrica (gain, vulnerability, readiness)
_ZIP_URL = "https://gain.nd.edu/assets/647440/ndgain_countryindex_2026.zip"

# Mapeo: subcarpeta dentro del ZIP → indicador
_ZIP_CSVS = {
    "gain/gain.csv": "score",
    "vulnerability/vulnerability.csv": "vulnerability",
    "readiness/readiness.csv": "readiness",
}

# (columna_csv, código, nombre, categoría)
# Si el CSV viene en formato largo, columna_csv es el nombre
# de la columna de valor. Si viene en formato ancho, se usa
# la métrica para filtrar filas o se ignora este campo.
INDICATORS = [
    (
        "score",
        "NDGAIN_OVERALL",
        "ND-GAIN Overall Score",
        "environment",
    ),
    (
        "vulnerability",
        "NDGAIN_VULNERABILITY",
        "ND-GAIN Vulnerability Score",
        "environment",
    ),
    (
        "readiness",
        "NDGAIN_READINESS",
        "ND-GAIN Readiness Score",
        "environment",
    ),
]


class NDGAINFetcher(BaseFetcher):
    """ND-GAIN Country Index: vulnerabilidad climática."""

    SOURCE_NAME = "ndgain"
    DOMAIN = "macro"
    RATE_LIMIT = 0

    # ── descarga ────────────────────────────────

    def _download_csv(self) -> pd.DataFrame:
        """Descargar ZIP y combinar 3 CSVs."""
        logger.info("NDGAIN: descargando ZIP...")
        self._rate_limit()
        resp = self._session.get(
            _ZIP_URL,
            timeout=120,
            headers={
                "User-Agent": ("Mozilla/5.0 stonks-db/1.0"),
            },
        )
        resp.raise_for_status()
        logger.info(
            "NDGAIN: %d bytes descargados",
            len(resp.content),
        )

        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        # Buscar CSVs dentro del ZIP
        all_names = zf.namelist()
        frames: list[pd.DataFrame] = []
        for suffix, metric in _ZIP_CSVS.items():
            match = [n for n in all_names if n.endswith(suffix)]
            if not match:
                logger.warning(
                    "NDGAIN: %s no encontrado",
                    suffix,
                )
                continue
            df = pd.read_csv(
                zf.open(match[0]),
                encoding="latin-1",
            )
            df.columns = [c.strip().lower() for c in df.columns]
            iso_col = next(
                (c for c in df.columns if "iso" in c),
                df.columns[0],
            )
            year_cols = [c for c in df.columns if c.strip().isdigit()]
            melted = df.melt(
                id_vars=[iso_col],
                value_vars=year_cols,
                var_name="year",
                value_name=metric,
            )
            melted = melted.rename(columns={iso_col: "iso3"})
            melted["year"] = pd.to_numeric(
                melted["year"], errors="coerce"
            ).astype(int)
            melted[metric] = pd.to_numeric(melted[metric], errors="coerce")
            frames.append(melted[["iso3", "year", metric]])
            logger.info(
                "NDGAIN: %s — %d filas",
                metric,
                len(melted),
            )

        if not frames:
            raise RuntimeError("NDGAIN: ningún CSV encontrado")

        # Combinar los 3 DataFrames por iso3+year
        combined = frames[0]
        for f in frames[1:]:
            combined = combined.merge(
                f,
                on=["iso3", "year"],
                how="outer",
            )

        # Renombrar score si falta
        if "score" not in combined.columns:
            combined["score"] = None
        if "vulnerability" not in combined.columns:
            combined["vulnerability"] = None
        if "readiness" not in combined.columns:
            combined["readiness"] = None

        logger.info(
            "NDGAIN: %d registros combinados",
            len(combined),
        )
        return combined

    # ── normalización ───────────────────────────

    @staticmethod
    def _normalize(df: pd.DataFrame) -> pd.DataFrame:
        """Normalizar CSV a formato largo.

        El CSV de ND-GAIN puede venir en dos formatos:
        - Largo: ISO3, Name, Year, Score, Vuln, Readiness
        - Ancho: ISO3, Name, 1995, 1996, ..., 2022
          (un CSV por métrica — menos probable en el
           archivo combinado)

        Devuelve siempre: iso3, year, score,
        vulnerability, readiness.
        """
        # Normalizar nombres de columnas a minúsculas
        df.columns = [c.strip().lower().replace("-", "_") for c in df.columns]

        # Detectar formato largo: buscar columna 'year'
        if "year" in df.columns:
            return NDGAINFetcher._parse_long(df)
        return NDGAINFetcher._parse_wide(df)

    @staticmethod
    def _parse_long(df: pd.DataFrame) -> pd.DataFrame:
        """Parsear formato largo."""
        # Mapeo flexible de nombres de columna
        col_map = {}
        for col in df.columns:
            low = col.lower().replace(" ", "_")
            if "iso" in low or low == "iso3":
                col_map["iso3"] = col
            elif low in ("year",):
                col_map["year"] = col
            elif "nd_gain" in low or "gain" in low:
                if "score" in low or "index" in low:
                    col_map["score"] = col
            elif "vulnerab" in low:
                col_map["vulnerability"] = col
            elif "readi" in low:
                col_map["readiness"] = col
            elif low == "score":
                col_map["score"] = col

        # Si no se encontró score, buscar más amplio
        if "score" not in col_map:
            for col in df.columns:
                low = col.lower()
                if "nd" in low and "gain" in low:
                    col_map["score"] = col
                    break

        iso_col = col_map.get("iso3")
        if not iso_col:
            raise ValueError(
                "NDGAIN: no se encontró columna ISO3. "
                f"Columnas: {list(df.columns)}"
            )

        rename = {}
        for target, src in col_map.items():
            rename[src] = target

        out = df.rename(columns=rename)
        # Asegurar columnas mínimas
        for c in ("score", "vulnerability", "readiness"):
            if c not in out.columns:
                out[c] = None

        out["year"] = pd.to_numeric(out["year"], errors="coerce")
        out = out.dropna(subset=["iso3", "year"])
        out["year"] = out["year"].astype(int)

        for c in ("score", "vulnerability", "readiness"):
            out[c] = pd.to_numeric(out[c], errors="coerce")

        return out[["iso3", "year", "score", "vulnerability", "readiness"]]

    @staticmethod
    def _parse_wide(df: pd.DataFrame) -> pd.DataFrame:
        """Parsear formato ancho (melt a largo)."""
        # Buscar columna ISO3
        iso_col = None
        name_col = None
        for col in df.columns:
            low = col.lower()
            if "iso" in low:
                iso_col = col
            elif "name" in low or "country" in low:
                name_col = col

        if not iso_col:
            raise ValueError(
                "NDGAIN: no se encontró columna ISO3 "
                f"en formato ancho. "
                f"Columnas: {list(df.columns)}"
            )

        # Columnas numéricas = años
        year_cols = [
            c
            for c in df.columns
            if c not in (iso_col, name_col) and str(c).strip().isdigit()
        ]

        if not year_cols:
            raise ValueError(
                "NDGAIN: no se encontraron columnas de año en formato ancho."
            )

        melted = df.melt(
            id_vars=[iso_col],
            value_vars=year_cols,
            var_name="year",
            value_name="score",
        )
        melted = melted.rename(columns={iso_col: "iso3"})
        melted["year"] = pd.to_numeric(melted["year"], errors="coerce").astype(
            int
        )
        melted["score"] = pd.to_numeric(melted["score"], errors="coerce")
        # En formato ancho solo tenemos una métrica
        melted["vulnerability"] = None
        melted["readiness"] = None

        return melted[["iso3", "year", "score", "vulnerability", "readiness"]]

    # ── fetch principal ─────────────────────────

    def fetch(self) -> dict:
        """Descargar y almacenar ND-GAIN."""
        run_id = self._start_run(params={"source": "ndgain_csv"})
        logger.info("NDGAIN: iniciando descarga...")

        try:
            df = self._download_csv()
            logger.info(
                "NDGAIN: %d registros listos",
                len(df),
            )
        except Exception as e:  # noqa: BLE001
            self._finish_run(
                run_id,
                "failed",
                error_log={"msg": str(e)},
            )
            logger.error("NDGAIN: %s", e)
            return {"error": str(e)}

        session = get_session()
        try:
            src_id = self._ensure_source(session)
            valid = {
                r[0]
                for r in session.execute(text("SELECT code FROM ref.country"))
            }

            total = 0
            for col, code, name, cat in INDICATORS:
                if col not in df.columns:
                    logger.warning(
                        "NDGAIN: columna %s ausente",
                        col,
                    )
                    continue

                ind_id = self._ensure_indicator(
                    session, code, name, cat, src_id
                )
                sub = df[["iso3", "year", col]].dropna(subset=[col])

                batch = []
                for _, row in sub.iterrows():
                    iso3 = str(row["iso3"]).strip()
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
                        "NDGAIN %s: %d puntos",
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
                "indicadores": len(INDICATORS),
                "puntos": total,
            }
        except Exception as e:  # noqa: BLE001
            session.rollback()
            self._finish_run(
                run_id,
                "failed",
                error_log={"msg": str(e)},
            )
            logger.error("NDGAIN: %s", e)
            return {"error": str(e)}
        finally:
            session.close()

    # ── helpers BD ──────────────────────────────

    def _ensure_source(self, session) -> int:
        """Crear o recuperar DataSource ndgain."""
        src = (
            session.query(DataSource).filter_by(name=self.SOURCE_NAME).first()
        )
        if not src:
            src = DataSource(
                name=self.SOURCE_NAME,
                display_name=("ND-GAIN Country Index"),
                base_url=("https://gain.nd.edu/our-work/country-index/"),
            )
            session.add(src)
            session.commit()
        return src.id

    @staticmethod
    def _ensure_indicator(session, code, name, cat, src_id) -> int:
        """Crear o recuperar Indicator."""
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
        """Obtener o crear Series para país."""
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
