"""Fetcher UNCTAD: inversión extranjera y conectividad marítima.

Descarga de UNCTADstat:
- Inversión extranjera directa, flujos y stock, entrante y saliente
  (millones de USD corrientes, desde 1990)
- LSCI (Liner Shipping Connectivity Index), trimestral desde 2006

**Cambio de fuente (auditoría 2026-08).** El fetcher apuntaba a
`unctadstat.unctad.org/EN/BulkDownload/*.csv`, que hoy devuelve 404:
por eso nunca cargó nada. UNCTAD rehízo el portal y ahora sirve los
mismos datos por API (`unctadstat-api.unctad.org`), pero comprimidos
en 7z en lugar de CSV plano, de ahí la dependencia de `py7zr`.

Los CSV usan nombres de país (no ISO3), así que se construye un mapa
nombre→ISO3 desde ref.country con overrides manuales para las
discrepancias habituales.

Fuente: UNCTAD, https://unctadstat.unctad.org
"""

import io
import pathlib
import tempfile
from datetime import date

import pandas as pd
import py7zr
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

# ── Descarga bulk vía la API nueva (ficheros 7z) ──
_API = "https://unctadstat-api.unctad.org/bulkdownload"
_FDI_CSV = f"{_API}/US.FdiFlowsStock/US_FdiFlowsStock"
_LSCI_CSV = f"{_API}/US.LSCI/US_LSCI"

# ── Datasets: (url, filtro columna/tipo, variables)
# Cada variable: (code, nombre, categoría, filtro)
# filtro = dict de columnas que deben coincidir para
# seleccionar las filas de ese indicador.
_FDI_VARS = [
    (
        "UNCTAD_FDI_IN",
        "FDI inward flows (millions USD)",
        "external",
        {"Flow Label": "Flow", "Direction Label": "Inward"},
    ),
    (
        "UNCTAD_FDI_OUT",
        "FDI outward flows (millions USD)",
        "external",
        {"Flow Label": "Flow", "Direction Label": "Outward"},
    ),
    (
        "UNCTAD_FDI_STOCK_IN",
        "FDI inward stock (millions USD)",
        "external",
        {"Flow Label": "Stock", "Direction Label": "Inward"},
    ),
    (
        "UNCTAD_FDI_STOCK_OUT",
        "FDI outward stock (millions USD)",
        "external",
        {"Flow Label": "Stock", "Direction Label": "Outward"},
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
        logger.info("UNCTAD %s: descargando...", label)
        self._rate_limit()
        resp = self._session.get(
            url,
            headers={"Accept": "application/octet-stream, */*"},
            timeout=300,
        )
        resp.raise_for_status()

        df = self._read_csv(self._descomprimir(resp.content))
        logger.info(
            "UNCTAD %s: %d filas × %d columnas",
            label,
            len(df),
            len(df.columns),
        )

        # Normalizar nombres de columnas
        df.columns = [c.strip() for c in df.columns]

        # Detectar columna de país
        # "Economy" es el codigo M49 numerico y "Economy Label" el
        # nombre: el mapeo a ISO3 se hace por nombre, asi que la
        # etiqueta va primero.
        eco_col = self._find_column(
            df,
            ["Economy Label", "Country Label", "Economy", "Country",
             "Reporter"],
        )
        year_col = self._find_column(
            df, ["Year", "Period", "Quarter"]
        )
        val_col = self._find_column(
            df,
            [
                "US$ at current prices in millions",
                "Index (Average Q1 2023 = 100)",
                "Value",
            ],
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
                fecha = self._periodo_a_fecha(row[year_col])
                if fecha is None:
                    continue

                sid = self._get_series(session, ind_id, iso3)
                batch.append(
                    {
                        "series_id": sid,
                        "date": fecha,
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
    def _periodo_a_fecha(bruto) -> date | None:
        """Convertir el periodo de UNCTAD en fecha de cierre.

        FDI es anual ("2024") y LSCI trimestral ("2006Q01"). Sin
        tratar el segundo formato, la serie de conectividad maritima
        se descartaba entera.
        """
        texto = str(bruto).strip()
        if not texto or texto.lower() == "nan":
            return None

        if "Q" in texto.upper():
            partes = texto.upper().split("Q")
            try:
                anio = int(partes[0])
                trimestre = int(partes[1])
            except (ValueError, IndexError):
                return None
            if not 1 <= trimestre <= 4:
                return None
            # Ultimo dia del trimestre.
            mes, dia = {1: (3, 31), 2: (6, 30), 3: (9, 30),
                        4: (12, 31)}[trimestre]
        else:
            try:
                anio = int(float(texto))
            except (ValueError, TypeError):
                return None
            mes, dia = 12, 31

        if not 1900 <= anio <= 2100:
            return None
        return date(anio, mes, dia)

    @staticmethod
    def _descomprimir(contenido: bytes) -> bytes:
        """Sacar el CSV del archivo 7z que sirve la API.

        Si la respuesta no es un 7z se devuelve tal cual, para que el
        fetcher siga funcionando si UNCTAD vuelve al CSV plano.
        """
        if not contenido.startswith(b"7z\xbc\xaf\x27\x1c"):
            return contenido

        with tempfile.TemporaryDirectory() as tmp:
            with py7zr.SevenZipFile(io.BytesIO(contenido)) as archivo:
                archivo.extractall(path=tmp)
            for fichero in sorted(pathlib.Path(tmp).rglob("*")):
                if fichero.is_file() and fichero.suffix.lower() == ".csv":
                    return fichero.read_bytes()
        raise ValueError("UNCTAD: el 7z no contiene ningun CSV")

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
