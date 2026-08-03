"""Fetcher Fragile States Index (Fund for Peace).

Descarga el XLSX anual del FSI con scores 0-120 por país/año
(178 países, 2006-2025). Se extraen 3 indicadores:
  - FSI_TOTAL: score total de fragilidad estatal
  - FSI_COHESION: suma C1+C2+C3 (cohesión)
  - FSI_ECONOMIC: suma E1+E2+E3 (económico)

Fuente: Fund for Peace — fragilestatesindex.org
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

# URLs verificadas por año (agosto 2026)
_YEAR_URLS = {
    2006: "data/fsi-2006.xlsx",
    2007: "data/fsi-2007.xlsx",
    2008: "data/fsi-2008.xlsx",
    2009: "data/fsi-2009.xlsx",
    2010: "data/fsi-2010.xlsx",
    2011: "data/fsi-2011.xlsx",
    2012: "data/fsi-2012.xlsx",
    2013: "data/fsi-2013.xlsx",
    2014: "data/fsi-2014.xlsx",
    2015: "data/fsi-2015.xlsx",
    2016: "data/fsi-2016.xlsx",
    2017: "data/fsi-2017.xlsx",
    2018: "2018/04/fsi-2018.xlsx",
    2019: "2019/04/fsi-2019.xlsx",
    2020: "2020/05/fsi-2020.xlsx",
    2021: "2021/05/fsi-2021.xlsx",
    2022: "2022/07/fsi-2022-download.xlsx",
    2023: "2023/06/FSI-2023-DOWNLOAD.xlsx",
}
_BASE = "https://fragilestatesindex.org/wp-content/uploads/"

# Columnas XLSX para cada sub-indicador
_COL_C1 = "C1: Security Apparatus"
_COL_C2 = "C2: Factionalized Elites"
_COL_C3 = "C3: Group Grievance"
_COL_E1 = "E1: Economy"
_COL_E2 = "E2: Economic Inequality"
_COL_E3 = "E3: Human Flight and Brain Drain"

# Indicadores a generar: (code, nombre, categoría)
INDICATORS = [
    (
        "FSI_TOTAL",
        "Fragile States Index Total Score (0-120)",
        "governance",
    ),
    (
        "FSI_COHESION",
        "FSI Cohesion (C1+C2+C3)",
        "governance",
    ),
    (
        "FSI_ECONOMIC",
        "FSI Economic (E1+E2+E3)",
        "governance",
    ),
]

# Mapeo manual: nombre FSI → ISO3 para países
# que no coinciden con ref.country
_NAME_OVERRIDES = {
    "Brunei Darussalam": "BRN",
    "Cabo Verde": "CPV",
    "Congo Democratic Republic": "COD",
    "Congo Republic": "COG",
    "Cote d'Ivoire": "CIV",
    "Czech Republic": "CZE",
    "Eswatini": "SWZ",
    "Guinea Bissau": "GNB",
    "Iran": "IRN",
    "Israel and West Bank": "ISR",
    "Ivory Coast": "CIV",
    "Korea Democratic Republic": "PRK",
    "Korea Republic": "KOR",
    "Kyrgyz Republic": "KGZ",
    "Lao PDR": "LAO",
    "Laos": "LAO",
    "Libya": "LBY",
    "Micronesia": "FSM",
    "Moldova": "MDA",
    "North Korea": "PRK",
    "North Macedonia": "MKD",
    "Palestine": "PSE",
    "Russia": "RUS",
    "Slovak Republic": "SVK",
    "Slovakia": "SVK",
    "South Korea": "KOR",
    "Syria": "SYR",
    "Tanzania": "TZA",
    "Timor-Leste": "TLS",
    "Trinidad and Tobago": "TTO",
    "Turkey": "TUR",
    "Turkiye": "TUR",
    "Venezuela": "VEN",
    "Vietnam": "VNM",
    "Bolivia": "BOL",
    "Congo (Brazzaville)": "COG",
    "Congo (Kinshasa)": "COD",
    "Gambia": "GMB",
    "Swaziland": "SWZ",
    "Macedonia": "MKD",
    "Czechia": "CZE",
    "Myanmar": "MMR",
    "Burma": "MMR",
    "Cape Verde": "CPV",
    "East Timor": "TLS",
    "Somaliland": None,  # no tiene ISO3
}


def _build_country_map(session) -> dict[str, str]:
    """Construir mapeo nombre → ISO3 desde ref.country
    + overrides manuales."""
    rows = session.execute(text("SELECT code, name FROM ref.country"))
    name_to_iso = {}
    for code, name in rows:
        name_to_iso[name] = code
        # Variante sin acentos / minúsculas
        name_to_iso[name.strip()] = code
    # Añadir overrides manuales
    for name, iso3 in _NAME_OVERRIDES.items():
        if iso3 is not None:
            name_to_iso[name] = iso3
    return name_to_iso


def _parse_fsi(
    data: bytes,
) -> pd.DataFrame:
    """Leer XLSX del FSI y devolver DataFrame limpio."""
    df = pd.read_excel(
        io.BytesIO(data),
        engine="openpyxl",
    )
    # Normalizar nombres de columnas (quitar espacios)
    df.columns = [c.strip() for c in df.columns]

    # Verificar columnas mínimas
    required = {"Country", "Year", "Total"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Columnas faltantes en XLSX: {missing}")

    # Normalizar Year (algunos XLSX usan Timestamp)
    df["Year"] = pd.to_numeric(
        pd.to_datetime(df["Year"], errors="coerce").dt.year.fillna(df["Year"]),
        errors="coerce",
    )

    # Calcular indicadores compuestos
    cohesion_cols = [_COL_C1, _COL_C2, _COL_C3]
    economic_cols = [_COL_E1, _COL_E2, _COL_E3]

    # Verificar que existan las columnas de detalle
    for col in cohesion_cols + economic_cols:
        if col not in df.columns:
            logger.warning("FSI: columna '%s' no encontrada", col)

    # Sumar cohesión si las 3 columnas existen
    if all(c in df.columns for c in cohesion_cols):
        df["Cohesion"] = df[cohesion_cols].sum(axis=1)
    else:
        df["Cohesion"] = pd.NA

    # Sumar económico si las 3 columnas existen
    if all(c in df.columns for c in economic_cols):
        df["Economic"] = df[economic_cols].sum(axis=1)
    else:
        df["Economic"] = pd.NA

    return df


class FSIFetcher(BaseFetcher):
    """Fund for Peace — Fragile States Index."""

    SOURCE_NAME = "fsi"
    DOMAIN = "macro"
    RATE_LIMIT = 1.0

    def fetch(self) -> dict:
        """Descargar y almacenar FSI (multi-año)."""
        run_id = self._start_run(params={"years": list(_YEAR_URLS.keys())})

        # Descargar todos los XLSX anuales
        frames: list[pd.DataFrame] = []
        for year, suffix in _YEAR_URLS.items():
            url = _BASE + suffix
            self._rate_limit()
            try:
                resp = self._session.get(url, timeout=60)
                resp.raise_for_status()
            except Exception:  # noqa: BLE001
                logger.warning(
                    "FSI: %d no disponible (%s)",
                    year,
                    url,
                )
                continue
            try:
                df_y = _parse_fsi(resp.content)
                if "Year" not in df_y.columns:
                    df_y["Year"] = year
                frames.append(df_y)
                logger.info(
                    "FSI %d: %d filas",
                    year,
                    len(df_y),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "FSI: error parseando %d: %s",
                    year,
                    exc,
                )

        if not frames:
            self._finish_run(
                run_id,
                "success",
                fetched=0,
                inserted=0,
            )
            return {"puntos": 0}

        df = pd.concat(frames, ignore_index=True)
        logger.info(
            "FSI: %d filas totales × %d columnas",
            len(df),
            len(df.columns),
        )

        col_map = {
            "Total": "FSI_TOTAL",
            "Cohesion": "FSI_COHESION",
            "Economic": "FSI_ECONOMIC",
        }

        session = get_session()
        try:
            src_id = self._ensure_source(session)
            country_map = _build_country_map(session)
            valid = {
                r[0]
                for r in session.execute(text("SELECT code FROM ref.country"))
            }

            total = 0
            for code, name, cat in INDICATORS:
                ind_id = self._ensure_indicator(
                    session, code, name, cat, src_id
                )
                df_col = next(k for k, v in col_map.items() if v == code)
                sub = df[["Country", "Year", df_col]].dropna(subset=[df_col])

                batch: list[dict] = []
                skip: set[str] = set()
                for _, row in sub.iterrows():
                    country = str(row["Country"]).strip()
                    iso3 = country_map.get(country)
                    if iso3 is None:
                        if country not in skip:
                            logger.debug(
                                "FSI: país no mapeado: '%s'",
                                country,
                            )
                            skip.add(country)
                        continue
                    if iso3 not in valid:
                        continue
                    try:
                        yr = int(row["Year"])
                    except (ValueError, TypeError):
                        continue
                    if not (2000 <= yr <= 2030):
                        continue

                    sid = self._get_series(session, ind_id, iso3)
                    batch.append(
                        {
                            "series_id": sid,
                            "date": date(yr, 12, 31),
                            "value": float(row[df_col]),
                            "source_id": src_id,
                        }
                    )

                # Deduplicar por (series_id, date)
                if batch:
                    seen: dict[tuple, dict] = {}
                    for rec in batch:
                        k = (
                            rec["series_id"],
                            rec["date"],
                        )
                        seen[k] = rec
                    batch = list(seen.values())
                    stmt = insert(DataPoint).values(batch)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["series_id", "date"],
                        set_={"value": stmt.excluded.value},
                    )
                    session.execute(stmt)
                    session.commit()
                    total += len(batch)
                    logger.info(
                        "FSI %s: %d puntos",
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
            logger.error("FSI: %s", e)
            return {"error": str(e)}
        finally:
            session.close()

    def _ensure_source(self, session) -> int:
        """Crear o recuperar DataSource para FSI."""
        src = (
            session.query(DataSource).filter_by(name=self.SOURCE_NAME).first()
        )
        if not src:
            src = DataSource(
                name=self.SOURCE_NAME,
                display_name=("Fund for Peace — Fragile States Index"),
                base_url=_BASE,
            )
            session.add(src)
            session.commit()
        return src.id

    @staticmethod
    def _ensure_indicator(session, code, name, cat, src_id) -> int:
        """Crear o recuperar Indicator + link."""
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
        """Obtener o crear Series para
        (indicador, país)."""
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
