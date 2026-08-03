"""Fetcher SIPRI Military Expenditure Database.

Descarga el XLSX anual de SIPRI con gasto militar por país
(170+ países, 1949-2024). Extrae tres indicadores: gasto
en USD corrientes (millones), porcentaje del PIB y gasto
per cápita.

El XLSX tiene formato ancho (años como columnas) con
múltiples hojas. Se parsea con pandas y se normaliza a
formato largo para insertar en macro.data_point.

Fuente: Stockholm International Peace Research Institute.
Licencia: datos de acceso libre para investigación.
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

_URL = (
    "https://www.sipri.org/sites/default/files/SIPRI-Milex-data-1949-2024.xlsx"
)

# Mapeo hoja XLSX → (código, nombre, categoría)
_SHEETS = [
    (
        "Current US$",
        "SIPRI_MILEX_USD",
        "Military expenditure (current USD millions)",
        "fiscal",
    ),
    (
        "Share of GDP",
        "SIPRI_MILEX_GDP",
        "Military expenditure (% of GDP)",
        "fiscal",
    ),
    (
        "Per capita",
        "SIPRI_MILEX_PC",
        "Military expenditure per capita (current USD)",
        "fiscal",
    ),
]

# Nombres SIPRI → ISO3 (solo excepciones que difieren
# de ref.country.name)
_NAME_MAP: dict[str, str] = {
    "Bahamas, The": "BHS",
    "Bolivia": "BOL",
    "Bosnia-Herzegovina": "BIH",
    "Bosnia and Herzegovina": "BIH",
    "Brunei": "BRN",
    "Burma (Myanmar)": "MMR",
    "Burma": "MMR",
    "Myanmar": "MMR",
    "Cape Verde": "CPV",
    "Cabo Verde": "CPV",
    "Congo, Dem. Rep.": "COD",
    "Congo, Rep.": "COG",
    "Congo, Republic of": "COG",
    "Congo, Dem. Republic of": "COD",
    "DR Congo": "COD",
    "Cote d'Ivoire": "CIV",
    "Côte d'Ivoire": "CIV",
    "Ivory Coast": "CIV",
    "Czech Republic": "CZE",
    "Czechia": "CZE",
    "East Timor": "TLS",
    "Timor-Leste": "TLS",
    "Timor Leste": "TLS",
    "Eswatini": "SWZ",
    "Swaziland": "SWZ",
    "Gambia, The": "GMB",
    "Gambia": "GMB",
    "Iran": "IRN",
    "Korea, North": "PRK",
    "North Korea": "PRK",
    "Korea, DPR": "PRK",
    "Korea, South": "KOR",
    "South Korea": "KOR",
    "Korea, Republic of": "KOR",
    "Laos": "LAO",
    "Lao PDR": "LAO",
    "Micronesia": "FSM",
    "Moldova": "MDA",
    "North Macedonia": "MKD",
    "Macedonia, FYR": "MKD",
    "Russia": "RUS",
    "Russian Federation": "RUS",
    "Saint Kitts and Nevis": "KNA",
    "St. Kitts and Nevis": "KNA",
    "Saint Lucia": "LCA",
    "St. Lucia": "LCA",
    "Saint Vincent and the Grenadines": "VCT",
    "St. Vincent and the Grenadines": "VCT",
    "Sao Tome and Principe": "STP",
    "São Tomé and Príncipe": "STP",
    "Slovakia": "SVK",
    "Slovak Republic": "SVK",
    "Syria": "SYR",
    "Syrian Arab Republic": "SYR",
    "Taiwan": "TWN",
    "Taiwan, China": "TWN",
    "Tanzania": "TZA",
    "Trinidad and Tobago": "TTO",
    "Turkey": "TUR",
    "Turkiye": "TUR",
    "Türkiye": "TUR",
    "Vatican City": "VAT",
    "Venezuela": "VEN",
    "Vietnam": "VNM",
    "Viet Nam": "VNM",
    "Yemen, North": "YEM",
    "Yemen, South": "YEM",
    "Serbia and Montenegro": "SRB",
    "Serbia": "SRB",
    "Montenegro": "MNE",
    "Kosovo": "XKX",
    "South Sudan": "SSD",
    "Czechoslovakia": "CZE",
    "USSR": "RUS",
    "Soviet Union": "RUS",
    "Yugoslavia": "SRB",
    "Germany, FRG": "DEU",
    "Germany, GDR": "DEU",
    "USA": "USA",
    "United States of America": "USA",
    "UK": "GBR",
    "United Kingdom": "GBR",
}

# Filas agregadas que no son países (regiones, totales)
_SKIP_ROWS = {
    "Africa",
    "North Africa",
    "sub-Saharan Africa",
    "Sub-Saharan Africa",
    "Americas",
    "Central America and the Caribbean",
    "North America",
    "South America",
    "Asia & Oceania",
    "Central and South Asia",
    "East Asia",
    "Oceania",
    "South East Asia",
    "Europe",
    "Central Europe",
    "Eastern Europe",
    "Western Europe",
    "Middle East",
    "World",
    "World total",
    "Total",
}

# Tamaño máximo de batch para INSERT
_BATCH_SIZE = 10_000


def _find_year_row(df: pd.DataFrame) -> int | None:
    """Encontrar la fila que contiene los años como
    cabecera en un DataFrame sin headers."""
    for idx in range(min(15, len(df))):
        row = df.iloc[idx]
        year_count = 0
        for val in row:
            try:
                n = int(float(val))
                if 1949 <= n <= 2030:
                    year_count += 1
            except (ValueError, TypeError):
                pass
        # Si hay al menos 10 años, es la fila cabecera
        if year_count >= 10:
            return idx
    return None


def _parse_sheet(
    content: bytes,
    sheet_name: str,
) -> pd.DataFrame:
    """Parsear una hoja SIPRI de formato ancho a largo.

    Devuelve DataFrame con columnas: country, year, value.
    """
    try:
        df = pd.read_excel(
            io.BytesIO(content),
            sheet_name=sheet_name,
            header=None,
        )
    except Exception:
        logger.warning(
            "SIPRI: hoja '%s' no encontrada",
            sheet_name,
        )
        return pd.DataFrame()

    # Detectar fila con años
    year_row = _find_year_row(df)
    if year_row is None:
        logger.warning(
            "SIPRI: no se detectaron años en '%s'",
            sheet_name,
        )
        return pd.DataFrame()

    # Mapear columnas con años válidos
    year_cols: dict[int, int] = {}
    country_col = 0
    for col_idx in range(len(df.columns)):
        val = df.iloc[year_row, col_idx]
        try:
            yr = int(float(val))
            if 1949 <= yr <= 2030:
                year_cols[col_idx] = yr
        except (ValueError, TypeError):
            pass

    if not year_cols:
        return pd.DataFrame()

    # Extraer datos: filas después de la cabecera
    records: list[dict] = []
    for idx in range(year_row + 1, len(df)):
        raw_name = df.iloc[idx, country_col]
        if pd.isna(raw_name):
            continue
        country = str(raw_name).strip()
        if not country:
            continue
        # Saltar filas agregadas
        if country in _SKIP_ROWS:
            continue

        for col_idx, year in year_cols.items():
            raw_val = df.iloc[idx, col_idx]
            if pd.isna(raw_val):
                continue
            # SIPRI usa "xxx" y "..." para datos faltantes
            if isinstance(raw_val, str):
                cleaned = raw_val.strip()
                if cleaned in (
                    "xxx",
                    "...",
                    ".",
                    "..",
                    "-",
                ):
                    continue
                try:
                    value = float(cleaned.replace(",", ""))
                except ValueError:
                    continue
            else:
                try:
                    value = float(raw_val)
                except (ValueError, TypeError):
                    continue

            records.append(
                {
                    "country": country,
                    "year": year,
                    "value": value,
                }
            )

    return pd.DataFrame(records)


class SIPRIFetcher(BaseFetcher):
    """SIPRI: gasto militar por país (USD, %PIB,
    per cápita)."""

    SOURCE_NAME = "sipri"
    DOMAIN = "macro"
    RATE_LIMIT = 1.0

    def fetch(self) -> dict:
        """Descargar y almacenar datos SIPRI."""
        run_id = self._start_run(params={"url": _URL})

        logger.info("SIPRI: descargando XLSX...")
        self._rate_limit()
        resp = self._session.get(_URL, timeout=120)
        resp.raise_for_status()
        xlsx_bytes = resp.content
        logger.info(
            "SIPRI: %d bytes descargados",
            len(xlsx_bytes),
        )

        session = get_session()
        try:
            src_id = self._ensure_source(session)

            # Mapa nombre→iso3 desde ref.country
            name_to_iso: dict[str, str] = {}
            for row in session.execute(
                text("SELECT code, name FROM ref.country")
            ):
                name_to_iso[row[1]] = row[0]
            name_to_iso.update(_NAME_MAP)

            valid_codes = {
                r[0]
                for r in session.execute(text("SELECT code FROM ref.country"))
            }

            total_inserted = 0
            total_fetched = 0
            series_cache: dict[tuple[str, str], int] = {}

            for sheet, code, name, cat in _SHEETS:
                df = _parse_sheet(xlsx_bytes, sheet)
                if df.empty:
                    logger.warning("SIPRI: hoja '%s' vacía", sheet)
                    continue

                total_fetched += len(df)
                logger.info(
                    "SIPRI %s: %d filas parseadas",
                    code,
                    len(df),
                )

                ind_id = self._ensure_indicator(
                    session, code, name, cat, src_id
                )

                batch: list[dict] = []
                skipped = 0
                for _, row in df.iterrows():
                    country = row["country"]
                    iso3 = name_to_iso.get(country)
                    if not iso3 or iso3 not in valid_codes:
                        skipped += 1
                        continue

                    key = (code, iso3)
                    sid = series_cache.get(key)
                    if sid is None:
                        sid = self._get_series(session, ind_id, iso3)
                        series_cache[key] = sid

                    batch.append(
                        {
                            "series_id": sid,
                            "date": date(int(row["year"]), 12, 31),
                            "value": float(row["value"]),
                            "source_id": src_id,
                        }
                    )

                if skipped:
                    logger.info(
                        "SIPRI %s: %d filas sin ISO3",
                        code,
                        skipped,
                    )

                # Deduplicar por (series_id, date):
                # p.ej. "Germany, FRG" y "Germany, GDR"
                # mapean al mismo DEU.
                seen: dict[tuple, dict] = {}
                for rec in batch:
                    k = (rec["series_id"], rec["date"])
                    seen[k] = rec
                batch = list(seen.values())

                for i in range(0, len(batch), _BATCH_SIZE):
                    chunk = batch[i : i + _BATCH_SIZE]
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
                total_inserted += len(batch)
                logger.info(
                    "SIPRI %s: %d puntos insertados",
                    code,
                    len(batch),
                )

            self._finish_run(
                run_id,
                "success",
                fetched=total_fetched,
                inserted=total_inserted,
            )
            logger.info(
                "SIPRI total: %d puntos insertados",
                total_inserted,
            )
            return {
                "indicadores": len(_SHEETS),
                "puntos": total_inserted,
            }

        except Exception as e:
            session.rollback()
            self._finish_run(
                run_id,
                "failed",
                error_log={"msg": str(e)},
            )
            logger.error("SIPRI falló: %s", e)
            raise
        finally:
            session.close()

    def _ensure_source(self, session) -> int:
        """Crear o recuperar la fuente SIPRI."""
        src = (
            session.query(DataSource).filter_by(name=self.SOURCE_NAME).first()
        )
        if not src:
            src = DataSource(
                name=self.SOURCE_NAME,
                display_name=("SIPRI Military Expenditure Database"),
                base_url=("https://www.sipri.org/databases/milex"),
            )
            session.add(src)
            session.commit()
        return src.id

    @staticmethod
    def _ensure_indicator(session, code, name, cat, src_id) -> int:
        """Crear o recuperar un indicador SIPRI."""
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
        """Obtener o crear serie para indicador+país.

        Usa caché interno para evitar queries repetidas.
        """
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
