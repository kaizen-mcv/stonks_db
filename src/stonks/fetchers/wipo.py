"""Fetcher WIPO IP Statistics — patentes mundiales.

Solicitudes y concesiones de patentes por oficina y año, almacenadas
en `macro` como indicadores anuales.

**Cambio de fuente (auditoría 2026-08).** El fetcher apuntaba al CSV
bulk `www3.wipo.int/ipstats/ipstats-export-patents.csv`, que hoy
devuelve la página HTML del Data Center en lugar de datos: por eso
nunca llegó a cargar nada. El Data Center actual es una aplicación
JavaScript sin endpoint público de descarga.

Lo que sí sigue publicando WIPO como fichero descargable es su serie
histórica 1883-1979, en un ZIP de CSV limpios. Es un tramo que ninguna
otra fuente de la base cubre —casi un siglo de actividad inventiva por
país— así que el fetcher se reorienta a él en vez de retirarse.

Para el tramo 1980 en adelante no hay hoy vía programática gratuita;
queda documentado como hueco en docs/AUDIT_2026-08.md.

Fuente: WIPO Statistics Database (datos históricos).
Licencia: uso público.
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

# ZIP con los CSV historicos (1883-1979) de solicitudes y
# concesiones por oficina y origen.
HISTORICAL_ZIP_URL = (
    "https://www.wipo.int/documents/2948119/3215563/"
    "wipo_ip_historical_data.zip"
)

# Ficheros del ZIP que se usan.
CSV_SOLICITUDES = "patents_filed_from_1883_to_1979.csv"
CSV_CONCESIONES = "patents_granted_from_1883_to_1979.csv"

# La fuente marca con 'ZZ' la fila agregada de todos los origenes.
ORIGEN_TOTAL = "ZZ"

# Variables WIPO: (col_pattern, code, nombre, categoría)
# col_pattern se usa para buscar la columna en el CSV
VARIABLES = [
    (
        "total",
        "WIPO_PATENT_APPS",
        "Patent applications total",
        "innovation",
    ),
    (
        "grants",
        "WIPO_PATENT_GRANTS",
        "Patents granted total",
        "innovation",
    ),
    (
        "resident",
        "WIPO_PATENT_RESIDENT",
        "Resident patent applications",
        "innovation",
    ),
]

BATCH_SIZE = 10_000


class WIPOFetcher(BaseFetcher):
    """WIPO IP Statistics: patentes mundiales."""

    SOURCE_NAME = "wipo"
    DOMAIN = "macro"
    RATE_LIMIT = 1.0

    def fetch(self) -> dict:
        """Descargar y almacenar datos WIPO."""
        run_id = self._start_run(params={"source": "wipo_historical_zip"})
        logger.info("WIPO: descargando ZIP historico...")
        self._rate_limit()
        resp = self._session.get(
            HISTORICAL_ZIP_URL,
            headers={"Accept": "application/zip, */*"},
            timeout=300,
        )
        resp.raise_for_status()

        df = self._parse_historico(resp.content)
        logger.info(
            "WIPO: %d filas × %d columnas (1883-1979)",
            len(df),
            len(df.columns),
        )

        session = get_session()
        try:
            src_id = self._ensure_source(session)
            # Mapeo ISO2 → ISO3 para países WIPO
            iso2_to_iso3 = self._build_iso_map(session)
            valid = {
                r[0]
                for r in session.execute(text("SELECT code FROM ref.country"))
            }

            # Detectar columnas del CSV
            col_map = self._detect_columns(df)

            total = 0
            for pattern, code, name, cat in VARIABLES:
                col = col_map.get(pattern)
                if col is None:
                    logger.warning(
                        "WIPO: columna '%s' no encontrada",
                        pattern,
                    )
                    continue

                ind_id = self._ensure_indicator(
                    session, code, name, cat, src_id
                )
                total += self._ingest_variable(
                    session,
                    df,
                    col,
                    ind_id,
                    src_id,
                    iso2_to_iso3,
                    valid,
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
            logger.error("WIPO: %s", e)
            return {"error": str(e)}
        finally:
            session.close()

    # ── Parseo del CSV ──────────────────────────────

    @staticmethod
    def _parse_historico(contenido: bytes) -> pd.DataFrame:
        """Convertir el ZIP historico en una tabla ancha.

        Cada CSV es largo: una fila por (año, oficina, origen). Se
        pivota a una fila por (oficina, año) con tres columnas, que es
        lo que espera `_ingest_variable`.

        - `total`: filas con origen 'ZZ' (agregado de todos los
          origenes) que publica la propia fuente.
        - `resident`: filas donde el origen coincide con la oficina.
        - `grants`: mismo criterio que `total`, sobre concesiones.

        Los CSV llevan nueve lineas de titulos y notas en tres idiomas
        antes de la cabecera, asi que esta se localiza en vez de
        saltarse un numero fijo de filas.
        """
        zf = zipfile.ZipFile(io.BytesIO(contenido))

        solicitudes = WIPOFetcher._leer_csv(zf, CSV_SOLICITUDES)
        concesiones = WIPOFetcher._leer_csv(zf, CSV_CONCESIONES)

        total = WIPOFetcher._agregar(solicitudes, solo_residentes=False)
        residentes = WIPOFetcher._agregar(
            solicitudes, solo_residentes=True
        )
        grants = WIPOFetcher._agregar(concesiones, solo_residentes=False)

        df = total.rename(columns={"valor": "total"})
        df = df.merge(
            residentes.rename(columns={"valor": "resident"}),
            on=["country_code", "year"],
            how="outer",
        )
        df = df.merge(
            grants.rename(columns={"valor": "grants"}),
            on=["country_code", "year"],
            how="outer",
        )

        # `_ingest_variable` limpia los valores con operaciones de
        # cadena, asi que las columnas se entregan como texto.
        for col in ("total", "resident", "grants"):
            df[col] = df[col].apply(
                lambda v: "" if pd.isna(v) else str(int(v))
            )
        df["year"] = df["year"].astype(int).astype(str)
        return df

    @staticmethod
    def _leer_csv(zf: zipfile.ZipFile, nombre: str) -> pd.DataFrame:
        """Leer un CSV del ZIP localizando su fila de cabecera."""
        texto = zf.read(nombre).decode("latin-1")
        lineas = texto.splitlines()
        # Solicitudes usan 'filing_year' y concesiones 'grant_year'.
        for i, linea in enumerate(lineas[:40]):
            if linea.lower().startswith(("filing_year,", "grant_year,")):
                return pd.read_csv(
                    io.StringIO("\n".join(lineas[i:])),
                    dtype=str,
                )
        raise ValueError(f"WIPO: sin cabecera en {nombre}")

    @staticmethod
    def _agregar(
        df: pd.DataFrame, solo_residentes: bool
    ) -> pd.DataFrame:
        """Sumar por oficina y año.

        La columna del año se llama `filing_year` en solicitudes y
        `grant_year` en concesiones.
        """
        col_year = (
            "filing_year" if "filing_year" in df.columns else "grant_year"
        )
        col_valor = next(
            c for c in ("filings", "grants", "value") if c in df.columns
        )

        sub = df.copy()
        if solo_residentes:
            sub = sub[sub["origin_code"] == sub["office_code"]]
        else:
            sub = sub[sub["origin_code"] == ORIGEN_TOTAL]

        sub["valor"] = pd.to_numeric(sub[col_valor], errors="coerce")
        sub["year"] = pd.to_numeric(sub[col_year], errors="coerce")
        sub = sub.dropna(subset=["valor", "year"])

        agregado = (
            sub.groupby(["office_code", "year"], as_index=False)["valor"]
            .sum()
            .rename(columns={"office_code": "country_code"})
        )
        return agregado

    @staticmethod
    def _detect_columns(
        df: pd.DataFrame,
    ) -> dict[str, str]:
        """Detectar columnas de datos en el CSV.

        Busca nombres que contengan las palabras clave
        de cada variable WIPO.
        """
        cols = list(df.columns)
        mapping: dict[str, str] = {}

        # Patrones de búsqueda para cada variable
        searches = {
            "total": [
                "total_application",
                "total_app",
                "total",
                "applications",
            ],
            "grants": [
                "grant",
                "patents_granted",
                "total_grant",
            ],
            "resident": [
                "resident_application",
                "resident_app",
                "resident",
            ],
        }

        for key, patterns in searches.items():
            for pat in patterns:
                for col in cols:
                    if pat in col and key not in mapping:
                        mapping[key] = col
                        break
                if key in mapping:
                    break

        logger.info("WIPO: columnas detectadas: %s", mapping)
        return mapping

    # ── Mapeo ISO ───────────────────────────────────

    @staticmethod
    def _build_iso_map(
        session,
    ) -> dict[str, str]:
        """Construir mapeo ISO2 → ISO3 desde ref.country.

        La columna se llama `code_alpha2`, no `iso2`: la consulta
        antigua fallaba siempre, que era el segundo motivo por el que
        este fetcher nunca cargo nada.
        """
        rows = session.execute(
            text(
                "SELECT code_alpha2, code FROM ref.country "
                "WHERE code_alpha2 IS NOT NULL"
            )
        )
        return {r[0]: r[1] for r in rows if r[0] is not None}

    # ── Ingesta por variable ────────────────────────

    def _ingest_variable(
        self,
        session,
        df: pd.DataFrame,
        col: str,
        ind_id: int,
        src_id: int,
        iso2_to_iso3: dict[str, str],
        valid: set[str],
        code: str,
    ) -> int:
        """Ingestar una variable del CSV en lotes."""
        # Detectar columna de país y año
        country_col = self._find_col(
            df,
            [
                "country_code",
                "code",
                "country",
                "iso",
                "iso2",
                "iso_code",
                "origin",
            ],
        )
        year_col = self._find_col(
            df, ["year", "filing_year", "application_year"]
        )
        if not country_col or not year_col:
            logger.warning("WIPO %s: sin columna país/año", code)
            return 0

        sub = df[[country_col, year_col, col]].copy()
        # Limpiar valores numéricos (comas, espacios)
        sub[col] = (
            sub[col]
            .str.replace(",", "", regex=False)
            .str.replace(" ", "", regex=False)
            .str.strip()
        )
        sub[col] = pd.to_numeric(sub[col], errors="coerce")
        sub = sub.dropna(subset=[col])
        sub[year_col] = pd.to_numeric(sub[year_col], errors="coerce")
        sub = sub.dropna(subset=[year_col])

        batch: list[dict] = []
        count = 0
        for _, row in sub.iterrows():
            raw_code = str(row[country_col]).strip()
            # Resolver código ISO3
            iso3 = self._resolve_iso3(raw_code, iso2_to_iso3)
            if iso3 is None or iso3 not in valid:
                continue

            year = int(row[year_col])
            # La serie historica arranca en 1883: un limite en 1900
            # descartaba en silencio los primeros 17 anos.
            if year < 1800 or year > 2100:
                continue

            sid = self._get_series(session, ind_id, iso3)
            batch.append(
                {
                    "series_id": sid,
                    "date": date(year, 12, 31),
                    "value": float(row[col]),
                    "source_id": src_id,
                }
            )

            # Insertar en lotes de BATCH_SIZE
            if len(batch) >= BATCH_SIZE:
                self._flush_batch(session, batch)
                count += len(batch)
                batch = []

        # Insertar lote final
        if batch:
            self._flush_batch(session, batch)
            count += len(batch)

        logger.info("WIPO %s: %d puntos", code, count)
        return count

    @staticmethod
    def _resolve_iso3(
        raw: str,
        iso2_to_iso3: dict[str, str],
    ) -> str | None:
        """Resolver código de país a ISO3.

        Acepta ISO3 directamente o ISO2 mapeado.
        """
        if len(raw) == 3 and raw.isalpha():
            return raw.upper()
        if len(raw) == 2 and raw.isalpha():
            return iso2_to_iso3.get(raw.upper())
        return None

    @staticmethod
    def _find_col(
        df: pd.DataFrame,
        candidates: list[str],
    ) -> str | None:
        """Buscar primera columna que coincida."""
        cols = set(df.columns)
        for c in candidates:
            if c in cols:
                return c
        # Búsqueda parcial
        for c in candidates:
            for real in df.columns:
                if c in real:
                    return real
        return None

    @staticmethod
    def _flush_batch(session, batch: list[dict]) -> None:
        """Insertar lote con upsert."""
        stmt = insert(DataPoint).values(batch)
        stmt = stmt.on_conflict_do_update(
            index_elements=["series_id", "date"],
            set_={"value": stmt.excluded.value},
        )
        session.execute(stmt)
        session.commit()

    # ── Metadatos ───────────────────────────────────

    def _ensure_source(self, session) -> int:
        src = (
            session.query(DataSource).filter_by(name=self.SOURCE_NAME).first()
        )
        if not src:
            src = DataSource(
                name=self.SOURCE_NAME,
                display_name=("WIPO IP Statistics"),
                base_url=("https://www3.wipo.int/ipstats/index.htm"),
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
