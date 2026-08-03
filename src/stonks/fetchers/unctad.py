"""Fetcher UNCTAD: FDI flows y Liner Shipping (CSV bulk).

Descarga estadísticas de UNCTADstat vía CSV bulk download:
- FDI inward/outward flows (millones USD)
- LSCI (Liner Shipping Connectivity Index)

Los CSV usan nombres de país (no ISO3), así que se
construye un mapa nombre→ISO3 desde ref.country con
overrides manuales para las discrepancias habituales.

Fuente: UNCTAD, https://unctadstat.unctad.org
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

# ── URLs de descarga CSV bulk ─────────────────────
_FDI_CSV = "https://unctadstat.unctad.org/EN/BulkDownload/US.FdiFlowsStock.csv"
_LSCI_CSV = "https://unctadstat.unctad.org/EN/BulkDownload/US.LSCI.csv"

# ── Datasets: (url, filtro columna/tipo, variables)
# Cada variable: (code, nombre, categoría, filtro)
# filtro = dict de columnas que deben coincidir para
# seleccionar las filas de ese indicador.
_FDI_VARS = [
    (
        "UNCTAD_FDI_IN",
        "FDI inward flows (millions USD)",
        "external",
        {"Inward and outward": "Inward"},
    ),
    (
        "UNCTAD_FDI_OUT",
        "FDI outward flows (millions USD)",
        "external",
        {"Inward and outward": "Outward"},
    ),
]
_LSCI_VARS = [
    (
        "UNCTAD_LSCI",
        "Liner Shipping Connectivity Index",
        "trade",
        {},  # sin filtro extra
    ),
]

# ── Overrides nombre UNCTAD → ISO3 ───────────────
# UNCTAD usa nombres largos o variantes no estándar;
# estas excepciones complementan el mapa de ref.country.
_NAME_OVERRIDES: dict[str, str] = {
    "Bolivia (Plurinational State of)": "BOL",
    "Bonaire, Sint Eustatius and Saba": "BES",
    "British Virgin Islands": "VGB",
    "Brunei Darussalam": "BRN",
    "Cabo Verde": "CPV",
    "China, Hong Kong SAR": "HKG",
    "China, Macao SAR": "MAC",
    "China, Taiwan Province of": "TWN",
    "Congo": "COG",
    "Congo, Democratic Republic of the": "COD",
    "Côte d'Ivoire": "CIV",
    "Cote d'Ivoire": "CIV",
    "Czechia": "CZE",
    "Czech Republic": "CZE",
    "Democratic People's Rep. of Korea": "PRK",
    "Democratic Republic of the Congo": "COD",
    "Eswatini": "SWZ",
    "Falkland Islands (Malvinas)": "FLK",
    "Hong Kong, China": "HKG",
    "Iran (Islamic Republic of)": "IRN",
    "Iran, Islamic Republic of": "IRN",
    "Korea, Dem. People's Rep. of": "PRK",
    "Korea, Republic of": "KOR",
    "Lao People's Democratic Republic": "LAO",
    "Lao People's Dem. Rep.": "LAO",
    "Macao, China": "MAC",
    "Micronesia (Federated States of)": "FSM",
    "Moldova, Republic of": "MDA",
    "Republic of Korea": "KOR",
    "Republic of Moldova": "MDA",
    "Russian Federation": "RUS",
    "Saint Kitts and Nevis": "KNA",
    "Saint Vincent and the Grenadines": "VCT",
    "Sao Tome and Principe": "STP",
    "Sint Maarten (Dutch part)": "SXM",
    "State of Palestine": "PSE",
    "Syrian Arab Republic": "SYR",
    "Taiwan Province of China": "TWN",
    "Tanzania, United Republic of": "TZA",
    "The former Yugoslav Rep. of Macedonia": "MKD",
    "Timor-Leste": "TLS",
    "Trinidad and Tobago": "TTO",
    "Türkiye": "TUR",
    "Turkiye": "TUR",
    "Turkey": "TUR",
    "United Kingdom": "GBR",
    "United States": "USA",
    "United States of America": "USA",
    "Venezuela (Bolivarian Republic of)": "VEN",
    "Venezuela, Bolivarian Republic of": "VEN",
    "Viet Nam": "VNM",
    "North Macedonia": "MKD",
}

# Tamaño máximo de batch para inserts
_BATCH_SIZE = 10_000


class UNCTADFetcher(BaseFetcher):
    """UNCTAD: FDI flows y LSCI."""

    SOURCE_NAME = "unctad"
    DOMAIN = "macro"
    RATE_LIMIT = 1.0

    def fetch(self) -> dict:
        """Descargar FDI y LSCI desde UNCTADstat."""
        run_id = self._start_run(params={"datasets": ["fdi", "lsci"]})
        session = get_session()
        try:
            src_id = self._ensure_source(session)
            name_to_iso = self._build_name_map(session)
            valid = {
                r[0]
                for r in session.execute(text("SELECT code FROM ref.country"))
            }

            total = 0

            # ── FDI ───────────────────────────────
            total += self._fetch_dataset(
                session,
                _FDI_CSV,
                _FDI_VARS,
                name_to_iso,
                valid,
                src_id,
                label="FDI",
            )

            # ── LSCI ──────────────────────────────
            total += self._fetch_dataset(
                session,
                _LSCI_CSV,
                _LSCI_VARS,
                name_to_iso,
                valid,
                src_id,
                label="LSCI",
            )

            self._finish_run(
                run_id,
                "success",
                fetched=total,
                inserted=total,
            )
            return {"puntos": total}

        except Exception as e:  # noqa: BLE001
            session.rollback()
            self._finish_run(
                run_id,
                "failed",
                error_log={"msg": str(e)},
            )
            logger.error("UNCTAD: %s", e)
            return {"error": str(e)}
        finally:
            session.close()

    # ── Descarga y procesado de un dataset ────────

    def _fetch_dataset(
        self,
        session,
        url: str,
        variables: list,
        name_to_iso: dict[str, str],
        valid: set[str],
        src_id: int,
        label: str = "",
    ) -> int:
        """Descargar CSV y volcar variables al esquema macro.

        Devuelve el total de puntos insertados.
        """
        logger.info("UNCTAD %s: descargando CSV...", label)
        self._rate_limit()
        resp = self._session.get(url, timeout=120)
        resp.raise_for_status()

        # Detectar encoding y leer CSV
        df = self._read_csv(resp.content)
        logger.info(
            "UNCTAD %s: %d filas × %d columnas",
            label,
            len(df),
            len(df.columns),
        )

        # Normalizar nombres de columnas
        df.columns = [c.strip() for c in df.columns]

        # Detectar columna de país
        eco_col = self._find_column(df, ["Economy", "Country", "Reporter"])
        year_col = self._find_column(df, ["Year", "Period"])
        val_col = self._find_column(
            df, ["Value", "US Dollars at current prices in millions"]
        )

        if eco_col is None or year_col is None:
            logger.warning(
                "UNCTAD %s: columnas no encontradas (tiene: %s)",
                label,
                ", ".join(df.columns[:10]),
            )
            return 0

        if val_col is None:
            # Último recurso: última columna numérica
            for c in reversed(df.columns.tolist()):
                if df[c].dtype in ("float64", "int64"):
                    val_col = c
                    break

        if val_col is None:
            logger.warning(
                "UNCTAD %s: columna valor no encontrada",
                label,
            )
            return 0

        total = 0
        for code, name, cat, filtro in variables:
            sub = df.copy()

            # Aplicar filtros específicos del indicador
            for fcol, fval in filtro.items():
                fcol_real = self._find_column(sub, [fcol])
                if fcol_real is None:
                    logger.warning(
                        "UNCTAD %s: filtro '%s' no encontrado",
                        label,
                        fcol,
                    )
                    sub = sub.iloc[0:0]
                    break
                sub = sub[sub[fcol_real].astype(str).str.strip() == fval]

            # Filtrar solo flujos (no stock) para FDI
            flow_col = self._find_column(
                sub, ["Flows and stocks", "Flow and stock"]
            )
            if flow_col is not None:
                sub = sub[
                    sub[flow_col]
                    .astype(str)
                    .str.strip()
                    .str.lower()
                    .str.contains("flow")
                ]

            sub = sub[[eco_col, year_col, val_col]].copy()
            sub[val_col] = pd.to_numeric(sub[val_col], errors="coerce")
            sub = sub.dropna(subset=[val_col])

            if sub.empty:
                logger.warning(
                    "UNCTAD %s (%s): sin datos tras filtrar",
                    label,
                    code,
                )
                continue

            ind_id = self._ensure_indicator(session, code, name, cat, src_id)

            batch: list[dict] = []
            unmapped: set[str] = set()

            for _, row in sub.iterrows():
                eco = str(row[eco_col]).strip()
                iso3 = name_to_iso.get(eco)
                if iso3 is None:
                    if eco not in unmapped:
                        unmapped.add(eco)
                    continue
                if iso3 not in valid:
                    continue
                try:
                    year = int(float(row[year_col]))
                except (ValueError, TypeError):
                    continue
                if year < 1900 or year > 2100:
                    continue

                sid = self._get_series(session, ind_id, iso3)
                batch.append(
                    {
                        "series_id": sid,
                        "date": date(year, 12, 31),
                        "value": float(row[val_col]),
                        "source_id": src_id,
                    }
                )

                # Flush por lotes
                if len(batch) >= _BATCH_SIZE:
                    self._flush_batch(session, batch)
                    total += len(batch)
                    batch = []

            if batch:
                self._flush_batch(session, batch)
                total += len(batch)

            if unmapped:
                logger.warning(
                    "UNCTAD %s (%s): %d economías sin mapeo ISO3: %s",
                    label,
                    code,
                    len(unmapped),
                    ", ".join(sorted(unmapped)[:10]),
                )
            logger.info(
                "UNCTAD %s (%s): OK",
                label,
                code,
            )

        return total

    # ── Helpers ────────────────────────────────────

    @staticmethod
    def _read_csv(content: bytes) -> pd.DataFrame:
        """Leer CSV con detección de encoding y
        separador."""
        # UNCTAD puede usar UTF-8-BOM o latin-1
        for enc in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                text_data = content.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            text_data = content.decode("utf-8", errors="replace")

        # Detectar separador (coma o punto y coma)
        first_line = text_data.split("\n", 1)[0]
        sep = ";" if first_line.count(";") > 2 else ","

        return pd.read_csv(
            io.StringIO(text_data),
            sep=sep,
            low_memory=False,
        )

    @staticmethod
    def _find_column(
        df: pd.DataFrame,
        candidates: list[str],
    ) -> str | None:
        """Buscar columna por nombre exacto o parcial
        (case-insensitive)."""
        cols = df.columns.tolist()
        # Primero: coincidencia exacta (case-insensitive)
        for cand in candidates:
            for col in cols:
                if col.strip().lower() == cand.lower():
                    return col
        # Segundo: contiene el candidato
        for cand in candidates:
            for col in cols:
                if cand.lower() in col.strip().lower():
                    return col
        return None

    @staticmethod
    def _build_name_map(
        session,
    ) -> dict[str, str]:
        """Construir mapa nombre→ISO3 desde ref.country
        + overrides manuales."""
        name_to_iso: dict[str, str] = {}
        for code, name in session.execute(
            text("SELECT code, name FROM ref.country")
        ):
            name_to_iso[name] = code
        # Los overrides sobreescriben nombres ambiguos
        name_to_iso.update(_NAME_OVERRIDES)
        return name_to_iso

    @staticmethod
    def _flush_batch(session, batch: list[dict]) -> None:
        """Insert batch con upsert por (series_id, date)."""
        stmt = insert(DataPoint).values(batch)
        stmt = stmt.on_conflict_do_update(
            index_elements=["series_id", "date"],
            set_={"value": stmt.excluded.value},
        )
        session.execute(stmt)
        session.commit()

    # ── Source / Indicator / Series ────────────────

    def _ensure_source(self, session) -> int:
        src = (
            session.query(DataSource).filter_by(name=self.SOURCE_NAME).first()
        )
        if not src:
            src = DataSource(
                name=self.SOURCE_NAME,
                display_name=(
                    "UNCTAD - United Nations Conference"
                    " on Trade and Development"
                ),
                base_url=("https://unctadstat.unctad.org/"),
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
