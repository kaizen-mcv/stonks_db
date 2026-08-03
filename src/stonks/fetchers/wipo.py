"""Fetcher WIPO IP Statistics — patentes mundiales.

Descarga estadísticas de solicitudes y concesiones de
patentes por país desde WIPO (200+ países, 1980-2023).
Los datos se almacenan en macro como indicadores anuales.

Fuente: WIPO IP Statistics Data Center.
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

BULK_CSV_URL = "https://www3.wipo.int/ipstats/ipstats-export-patents.csv"

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
        run_id = self._start_run(params={"source": "wipo_bulk_csv"})
        logger.info("WIPO: descargando CSV bulk...")
        self._rate_limit()
        resp = self._session.get(BULK_CSV_URL, timeout=120)
        resp.raise_for_status()

        df = self._parse_csv(resp.content)
        logger.info(
            "WIPO: %d filas × %d columnas",
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
    def _parse_csv(content: bytes) -> pd.DataFrame:
        """Leer CSV y limpiar números con comas."""
        # Intentar varias codificaciones
        for enc in ("utf-8", "latin-1"):
            try:
                df = pd.read_csv(
                    io.BytesIO(content),
                    encoding=enc,
                    dtype=str,
                )
                break
            except UnicodeDecodeError:
                continue
        else:
            df = pd.read_csv(
                io.BytesIO(content),
                encoding="utf-8",
                errors="replace",
                dtype=str,
            )

        # Normalizar nombres de columna
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        return df

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
        """Construir mapeo ISO2 → ISO3 desde
        ref.country."""
        rows = session.execute(
            text("SELECT iso2, code FROM ref.country WHERE iso2 IS NOT NULL")
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
            if year < 1900 or year > 2100:
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
