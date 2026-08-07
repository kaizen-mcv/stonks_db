"""Fetcher de los datasets de Aswath Damodaran (NYU Stern).

Damodaran publica cada enero, de forma gratuita, la prima de riesgo de
renta variable por pais y los tipos impositivos de sociedades. Son las
referencias academicas estandar para valoracion.

Cubren dos huecos concretos de la base de datos:

- `fi.country_risk_premium` (nueva): `gold.mart_sovereign_risk` cruzaba
  rating con macro pero no tenia ninguna medida de la prima exigida al
  pais, que es justo lo que convierte un rating en coste de capital.
- `country.tax_rate`: la tabla existia desde el principio y estaba
  vacia.

El fichero es un Excel con muchas hojas y cabeceras a distinta altura,
asi que la fila de cabecera se busca en vez de fijarse por numero: si
Damodaran mueve una fila, el fetcher no se rompe en silencio.
"""

import io
import re
import unicodedata
from datetime import date

import pandas as pd
import requests
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.country import TaxRate
from stonks.models.fixed_income import CountryRiskPremium
from stonks.models.meta import DataSource

URL_CTRYPREM = (
    "https://pages.stern.nyu.edu/~adamodar/pc/datasets/ctryprem.xlsx"
)

HOJA_ERP = "ERPs by country"
HOJA_TAX = "Country Tax Rates"

# Nombres que Damodaran usa y que no coinciden con ref.country.
ALIAS_PAIS = {
    "abu dhabi": "ARE",
    "sharjah": "ARE",
    "ras al khaimah": "ARE",
    "united arab emirates": "ARE",
    "korea": "KOR",
    "korea, south": "KOR",
    "south korea": "KOR",
    "north korea": "PRK",
    "russia": "RUS",
    "russian federation": "RUS",
    "vietnam": "VNM",
    "laos": "LAO",
    "syria": "SYR",
    "iran": "IRN",
    "taiwan": "TWN",
    "hong kong": "HKG",
    "macao": "MAC",
    "china": "CHN",
    "bolivia": "BOL",
    "venezuela": "VEN",
    "tanzania": "TZA",
    "moldova": "MDA",
    "czech republic": "CZE",
    "slovakia": "SVK",
    "turkey": "TUR",
    "turkiye": "TUR",
    "cape verde": "CPV",
    "ivory coast": "CIV",
    "cote d ivoire": "CIV",
    "congo democratic republic": "COD",
    "congo republic of": "COG",
    "swaziland": "SWZ",
    "macedonia": "MKD",
    "north macedonia": "MKD",
    "united kingdom": "GBR",
    "united states": "USA",
    "usa": "USA",
    "bahamas": "BHS",
    "gambia": "GMB",
    "netherlands": "NLD",
    "philippines": "PHL",
    "andorra principality of": "AND",
    "isle of man": "IMN",
    "channel islands": "JEY",
    "st maarten": "SXM",
    "sint maarten": "SXM",
    "curacao": "CUW",
    "brunei": "BRN",
    "laos peoples democratic republic": "LAO",
    "congo democratic republic of": "COD",
    "guernsey states of": "GGY",
    "jersey states of": "JEY",
    "ras al khaimah emirate of": "ARE",
    "st vincent the grenadines": "VCT",
    "korea d p r": "PRK",
    "yemen republic": "YEM",
}

# Filas de la hoja que no son paises: agregados y repeticiones de la
# cabecera intercaladas en la tabla.
NO_PAISES = {
    "country",
    "frontier markets no sovereign ratings",
}


class DamodaranFetcher(BaseFetcher):
    """Primas de riesgo pais y tipos de sociedades."""

    SOURCE_NAME = "damodaran"
    DOMAIN = "fi"
    RATE_LIMIT = 2.0

    def fetch(self, anio: int | None = None) -> dict:
        """Descargar primas de riesgo y tipos impositivos.

        Args:
            anio: ejercicio al que atribuir los datos. Por defecto el
                año en curso, que es el criterio de Damodaran (publica
                en enero con datos de cierre del año anterior).

        Returns:
            {"primas": N, "tipos": N}
        """
        anio = anio or date.today().year
        session = get_session()
        run_id = self._start_run({"anio": anio})
        src_id = self._ensure_source(session)

        try:
            contenido = self._descargar()
            mapa = self._mapa_paises(session)

            primas = self._cargar_primas(
                session, contenido, mapa, anio, src_id
            )
            tipos = self._cargar_tipos(session, contenido, mapa, anio)

            self._finish_run(
                run_id,
                "success",
                fetched=primas + tipos,
                inserted=primas + tipos,
            )
            logger.info(
                "Damodaran: %d primas de riesgo, %d tipos impositivos",
                primas,
                tipos,
            )
        except Exception as e:
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
            logger.error("Damodaran fallo: %s", e)
            raise
        finally:
            session.close()

        return {"primas": primas, "tipos": tipos}

    # ── Internos ─────────────────────────────────

    def _descargar(self) -> bytes:
        """Bajar el Excel de primas de riesgo pais."""
        self._rate_limit()
        resp = requests.get(
            URL_CTRYPREM,
            headers={"User-Agent": "stonks/0.4"},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.content

    @staticmethod
    def _normalizar(nombre: str) -> str:
        """Nombre de pais comparable: sin acentos ni puntuacion."""
        txt = unicodedata.normalize("NFKD", str(nombre).lower())
        txt = "".join(c for c in txt if not unicodedata.combining(c))
        txt = re.sub(r"[^a-z ]", " ", txt)
        return " ".join(txt.split())

    def _mapa_paises(self, session) -> dict[str, str]:
        """Diccionario nombre normalizado -> codigo ISO3."""
        mapa = {}
        filas = session.execute(
            text("SELECT code, name FROM ref.country")
        ).fetchall()
        for codigo, nombre in filas:
            mapa[self._normalizar(nombre)] = codigo
            # Muchos nombres oficiales llevan coma ("Korea, Republic
            # of"): tambien se indexa la parte previa.
            corto = str(nombre).split(",")[0]
            mapa.setdefault(self._normalizar(corto), codigo)
        mapa.update(ALIAS_PAIS)
        return mapa

    @staticmethod
    def _leer_hoja(contenido: bytes, hoja: str, primera_col: str):
        """Leer una hoja localizando su fila de cabecera.

        Damodaran deja notas y titulos sobre la tabla, y la altura
        cambia entre ediciones. Se busca la fila cuya primera celda es
        `primera_col` en lugar de fijar un `skiprows`.
        """
        crudo = pd.read_excel(
            io.BytesIO(contenido), sheet_name=hoja, header=None
        )
        for i in range(min(40, len(crudo))):
            celda = str(crudo.iloc[i, 0]).strip()
            if celda == primera_col:
                return pd.read_excel(
                    io.BytesIO(contenido), sheet_name=hoja, skiprows=i
                )
        raise ValueError(
            f"No se encontro la cabecera '{primera_col}' en '{hoja}'"
        )

    @staticmethod
    def _numero(valor) -> float | None:
        """Convertir a porcentaje. La fuente publica tantos por uno."""
        try:
            if valor is None or pd.isna(valor):
                return None
            return round(float(valor) * 100, 4)
        except (TypeError, ValueError):
            return None

    def _cargar_primas(
        self, session, contenido: bytes, mapa: dict, anio: int, src_id: int
    ) -> int:
        """Cargar fi.country_risk_premium."""
        df = self._leer_hoja(contenido, HOJA_ERP, "Country")
        columnas = {str(c).strip(): c for c in df.columns}

        col_erp = columnas.get("Total Equity Risk Premium")
        col_crp = columnas.get("Country Risk Premium")
        col_spread = columnas.get("Rating-based Default Spread")
        col_rating = columnas.get("Moody's rating")
        if col_erp is None or col_crp is None:
            raise ValueError("Faltan columnas de prima en la hoja ERP")

        lote = []
        sin_mapear = []
        for _, fila in df.iterrows():
            nombre = fila.get("Country")
            if not isinstance(nombre, str) or not nombre.strip():
                continue
            normalizado = self._normalizar(nombre)
            if normalizado in NO_PAISES:
                continue
            codigo = mapa.get(normalizado)
            if not codigo:
                sin_mapear.append(nombre)
                continue

            rating = fila.get(col_rating) if col_rating else None
            lote.append(
                {
                    "country_code": codigo,
                    "year": anio,
                    "equity_risk_premium": self._numero(fila.get(col_erp)),
                    "country_risk_premium": self._numero(fila.get(col_crp)),
                    "default_spread": (
                        self._numero(fila.get(col_spread))
                        if col_spread
                        else None
                    ),
                    "moodys_rating": (
                        str(rating)[:10]
                        if isinstance(rating, str) and rating.strip()
                        else None
                    ),
                    "source_id": src_id,
                }
            )

        if sin_mapear:
            logger.warning(
                "Damodaran: %d paises sin mapear (%s...)",
                len(sin_mapear),
                ", ".join(sin_mapear[:5]),
            )

        lote = self._deduplicar(lote, ("country_code", "year"))
        if lote:
            stmt = insert(CountryRiskPremium).values(lote)
            stmt = stmt.on_conflict_do_update(
                constraint="country_risk_premium_country_code_year_key",
                set_={
                    "equity_risk_premium": stmt.excluded.equity_risk_premium,
                    "country_risk_premium": (
                        stmt.excluded.country_risk_premium
                    ),
                    "default_spread": stmt.excluded.default_spread,
                    "moodys_rating": stmt.excluded.moodys_rating,
                    "source_id": stmt.excluded.source_id,
                },
            )
            session.execute(stmt)
            session.commit()
        return len(lote)

    def _cargar_tipos(
        self, session, contenido: bytes, mapa: dict, anio: int
    ) -> int:
        """Cargar country.tax_rate (tipo de sociedades)."""
        df = self._leer_hoja(contenido, HOJA_TAX, "Country")

        lote = []
        for _, fila in df.iterrows():
            nombre = fila.get("Country")
            if not isinstance(nombre, str) or not nombre.strip():
                continue
            codigo = mapa.get(self._normalizar(nombre))
            tipo = self._numero(fila.get("Tax Rate"))
            if not codigo or tipo is None:
                continue
            lote.append(
                {
                    "country_code": codigo,
                    "year": anio,
                    "corporate_tax_rate": tipo,
                }
            )

        lote = self._deduplicar(lote, ("country_code", "year"))
        if lote:
            stmt = insert(TaxRate).values(lote)
            stmt = stmt.on_conflict_do_update(
                constraint="tax_rate_country_code_year_key",
                set_={
                    "corporate_tax_rate": stmt.excluded.corporate_tax_rate
                },
            )
            session.execute(stmt)
            session.commit()
        return len(lote)

    @staticmethod
    def _deduplicar(lote: list[dict], clave: tuple) -> list[dict]:
        """Una fila por clave: varios nombres mapean al mismo pais.

        Damodaran lista por separado Abu Dhabi, Dubai y Sharjah, que en
        ISO son todos ARE. ON CONFLICT no resuelve duplicados dentro del
        mismo INSERT, asi que se colapsan antes.
        """
        unicos: dict[tuple, dict] = {}
        for fila in lote:
            unicos[tuple(fila[k] for k in clave)] = fila
        return list(unicos.values())

    @staticmethod
    def _ensure_source(session) -> int:
        """Registrar Damodaran en meta.data_source si falta."""
        src = session.query(DataSource).filter_by(name="damodaran").first()
        if not src:
            src = DataSource(
                name="damodaran",
                display_name="Damodaran Online (NYU Stern)",
                base_url="https://pages.stern.nyu.edu/~adamodar/",
                rate_limit_per_second=0.5,
                is_enabled=True,
                notes=(
                    "Primas de riesgo pais y tipos de sociedades. "
                    "Actualizacion anual en enero. Gratuito."
                ),
            )
            session.add(src)
            session.commit()
        return src.id
