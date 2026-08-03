"""Fetcher Heritage Foundation — Index of Economic Freedom.

Descarga datos anuales del Index of Economic Freedom
(184 países, 1995-2025). Puntuaciones 0-100
(mayor = más libre).

Fuente: The Heritage Foundation.
Licencia: uso público.
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

# Patrón URL para descargas anuales (XLS y CSV)
_XLS_TPL = "https://www.heritage.org/index/excel/{y}/index{y}_data.xls"
_CSV_TPL = "https://www.heritage.org/index/csv/{y}/index{y}_data.csv"

_YEAR_START = 1995
_YEAR_END = 2025

# (clave_columna, code, nombre, categoría)
_INDICATORS = [
    (
        "overall score",
        "HF_ECON_FREEDOM",
        "Economic Freedom Score (Heritage)",
        "governance",
    ),
    (
        "trade freedom",
        "HF_TRADE_FREEDOM",
        "Trade Freedom Score (Heritage)",
        "governance",
    ),
    (
        "fiscal health",
        "HF_FISCAL",
        "Fiscal Health Score (Heritage)",
        "fiscal",
    ),
]

# Nombres Heritage → ISO3 (excepciones frecuentes)
_NAME_MAP: dict[str, str] = {
    "Bahamas, The": "BHS",
    "Bolivia": "BOL",
    "Brunei": "BRN",
    "Burma": "MMR",
    "Cape Verde": "CPV",
    "Congo, Dem. Rep.": "COD",
    "Congo, Democratic Republic of": "COD",
    "Congo, Rep.": "COG",
    "Congo, Republic of": "COG",
    "Cote d'Ivoire": "CIV",
    "Côte d'Ivoire": "CIV",
    "Czech Republic": "CZE",
    "East Timor": "TLS",
    "Egypt": "EGY",
    "Eswatini": "SWZ",
    "Gambia, The": "GMB",
    "Iran": "IRN",
    "Korea, North": "PRK",
    "Korea, South": "KOR",
    "Kyrgyz Republic": "KGZ",
    "Laos": "LAO",
    "Macau": "MAC",
    "Micronesia": "FSM",
    "Moldova": "MDA",
    "North Korea": "PRK",
    "North Macedonia": "MKD",
    "Russia": "RUS",
    "Saint Kitts and Nevis": "KNA",
    "Saint Lucia": "LCA",
    "Saint Vincent and the Grenadines": "VCT",
    "São Tomé and Príncipe": "STP",
    "Sao Tome and Principe": "STP",
    "Slovakia": "SVK",
    "South Korea": "KOR",
    "Swaziland": "SWZ",
    "Syria": "SYR",
    "Taiwan": "TWN",
    "Tanzania": "TZA",
    "Timor-Leste": "TLS",
    "Trinidad and Tobago": "TTO",
    "Turkey": "TUR",
    "Türkiye": "TUR",
    "Venezuela": "VEN",
    "Vietnam": "VNM",
}


def _find_col(columns: list[str], *candidates: str) -> str | None:
    """Buscar columna por nombre (case-insensitive).

    Retorna el nombre original de la columna o None.
    """
    lower_map = {c.strip().lower(): c for c in columns}
    for cand in candidates:
        if cand in lower_map:
            return lower_map[cand]
    return None


class HeritageFetcher(BaseFetcher):
    """Heritage Foundation: Index of Economic Freedom."""

    SOURCE_NAME = "heritage"
    DOMAIN = "macro"
    RATE_LIMIT = 1.0

    _series_cache: dict[tuple, int] = {}

    def fetch(self) -> dict:
        """Descargar y almacenar Heritage Index."""
        run_id = self._start_run(
            params={
                "years": (f"{_YEAR_START}-{_YEAR_END}"),
            }
        )

        session = get_session()
        try:
            src_id = self._ensure_source(session)

            # Mapa nombre→ISO3 desde ref.country
            name_to_iso: dict[str, str] = {}
            for r in session.execute(
                text("SELECT code, name FROM ref.country")
            ):
                name_to_iso[r[1]] = r[0]
            # Sobreescribir con excepciones manuales
            name_to_iso.update(_NAME_MAP)

            valid_codes = {
                r[0]
                for r in session.execute(text("SELECT code FROM ref.country"))
            }

            # Crear los 3 indicadores
            ind_ids: dict[str, int] = {}
            for _, code, name, cat in _INDICATORS:
                ind_ids[code] = self._ensure_indicator(
                    session, code, name, cat, src_id
                )

            total = 0
            years_ok = 0

            for year in range(_YEAR_START, _YEAR_END + 1):
                df = self._download_year(year)
                if df is None:
                    logger.debug(
                        "Heritage: sin datos %d",
                        year,
                    )
                    continue

                # Normalizar nombres de columna
                df.columns = [c.strip() for c in df.columns]

                # Buscar columna de país
                country_col = _find_col(
                    list(df.columns),
                    "country name",
                    "country",
                    "name",
                )
                if country_col is None:
                    logger.warning(
                        "Heritage %d: sin columna de país",
                        year,
                    )
                    continue

                # Buscar columna de año (opcional)
                year_col = _find_col(
                    list(df.columns),
                    "index year",
                    "year",
                )

                years_ok += 1
                batch: list[dict] = []

                for col_key, code, _, _ in _INDICATORS:
                    real_col = _find_col(
                        list(df.columns),
                        col_key,
                    )
                    if real_col is None:
                        # Fiscal Health no existe pre-2017
                        continue

                    ind_id = ind_ids[code]

                    for _, row in df.iterrows():
                        cname = str(row[country_col]).strip()
                        iso3 = name_to_iso.get(cname)
                        if not iso3 or iso3 not in valid_codes:
                            continue

                        # Valor numérico
                        raw = row.get(real_col)
                        try:
                            val = float(raw)
                        except (ValueError, TypeError):
                            continue
                        if pd.isna(val):
                            continue

                        # Año del datapoint
                        dy = year
                        if year_col is not None:
                            try:
                                dy = int(float(row[year_col]))
                            except (
                                ValueError,
                                TypeError,
                            ):
                                pass

                        sid = self._get_series(session, ind_id, iso3)
                        batch.append(
                            {
                                "series_id": sid,
                                "date": date(dy, 12, 31),
                                "value": val,
                                "source_id": src_id,
                            }
                        )

                if batch:
                    stmt = insert(DataPoint).values(batch)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=[
                            "series_id",
                            "date",
                        ],
                        set_={
                            "value": (stmt.excluded.value),
                        },
                    )
                    session.execute(stmt)
                    session.commit()
                    total += len(batch)
                    logger.info(
                        "Heritage %d: %d puntos",
                        year,
                        len(batch),
                    )

            self._finish_run(
                run_id,
                "success",
                fetched=total,
                inserted=total,
            )
            logger.info(
                "Heritage: %d años, %d puntos total",
                years_ok,
                total,
            )
            return {
                "años": years_ok,
                "puntos": total,
            }
        except Exception as e:  # noqa: BLE001
            session.rollback()
            self._finish_run(
                run_id,
                "failed",
                error_log={"msg": str(e)},
            )
            logger.error("Heritage: %s", e)
            return {"error": str(e)}
        finally:
            session.close()

    # ── Descarga por año ────────────────────────

    def _download_year(self, year: int) -> pd.DataFrame | None:
        """Descargar datos de un año.

        Intenta XLS primero, luego CSV como fallback.
        Retorna DataFrame o None si no hay datos.
        """
        # Intentar XLS
        xls_url = _XLS_TPL.format(y=year)
        self._rate_limit()
        try:
            resp = self._session.get(
                xls_url,
                timeout=30,
                headers={"Accept": "*/*"},
            )
            if resp.status_code == 200:
                return pd.read_excel(
                    io.BytesIO(resp.content),
                )
        except Exception:
            pass

        # Fallback a CSV
        csv_url = _CSV_TPL.format(y=year)
        self._rate_limit()
        try:
            resp = self._session.get(
                csv_url,
                timeout=30,
                headers={"Accept": "*/*"},
            )
            if resp.status_code == 200:
                return pd.read_csv(
                    io.StringIO(resp.text),
                )
        except Exception:
            pass

        return None

    # ── Helpers BD ──────────────────────────────

    def _ensure_source(self, session) -> int:
        """Crear o recuperar DataSource heritage."""
        src = (
            session.query(DataSource).filter_by(name=self.SOURCE_NAME).first()
        )
        if not src:
            src = DataSource(
                name=self.SOURCE_NAME,
                display_name=("Heritage Foundation"),
                base_url=("https://www.heritage.org/index/"),
            )
            session.add(src)
            session.commit()
        return src.id

    @staticmethod
    def _ensure_indicator(session, code, name, cat, src_id) -> int:
        """Crear o recuperar indicador."""
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

    def _get_series(self, session, ind_id, iso3) -> int:
        """Obtener o crear serie (con caché)."""
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
