"""Fetcher de indices de precios inmobiliarios (esquema realestate).

El esquema `realestate` estaba declarado en `stonks.db.SCHEMAS` y
descrito en la documentacion, pero nunca llego a crearse ni a cargarse.
Este fetcher lo rellena con la fuente gratuita de mayor cobertura para
el dominio: las series de precios de vivienda que FRED redistribuye del
BIS y de la OCDE, ademas del indice estadounidense de Case-Shiller.

Las series del BIS via FRED cubren mas de 50 paises con historico largo
y un unico formato, lo que evita tener que integrar tres APIs distintas
para el mismo dato.
"""

from datetime import date, datetime

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from stonks.config import settings
from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.meta import DataSource
from stonks.models.realestate import PriceIndex, PriceIndexValue

BASE_URL = "https://api.stlouisfed.org/fred"
CHUNK = 5000

# Series de FRED por pais. El identificador del BIS sigue el patron
# QXXR628BIS (real, deflactado) y QXXN628BIS (nominal), donde XX es el
# codigo ISO2 del pais.
PAISES_BIS = [
    ("USA", "US"), ("GBR", "GB"), ("DEU", "DE"), ("FRA", "FR"),
    ("ITA", "IT"), ("ESP", "ES"), ("NLD", "NL"), ("BEL", "BE"),
    ("PRT", "PT"), ("IRL", "IE"), ("AUT", "AT"), ("CHE", "CH"),
    ("SWE", "SE"), ("NOR", "NO"), ("DNK", "DK"), ("FIN", "FI"),
    ("POL", "PL"), ("CZE", "CZ"), ("HUN", "HU"), ("GRC", "GR"),
    ("CAN", "CA"), ("MEX", "MX"), ("BRA", "BR"), ("CHL", "CL"),
    ("COL", "CO"), ("PER", "PE"), ("JPN", "JP"), ("KOR", "KR"),
    ("CHN", "CN"), ("IND", "IN"), ("IDN", "ID"), ("THA", "TH"),
    ("MYS", "MY"), ("HKG", "HK"), ("SGP", "SG"), ("AUS", "AU"),
    ("NZL", "NZ"), ("ZAF", "ZA"), ("TUR", "TR"), ("ISR", "IL"),
    ("RUS", "RU"),
]

# Series adicionales de EE.UU. que no siguen el patron del BIS.
SERIES_EXTRA = [
    (
        "CSUSHPINSA",
        "USA",
        "S&P CoreLogic Case-Shiller U.S. National Home Price Index",
        "residential",
        "nominal",
        "monthly",
    ),
    (
        "USSTHPI",
        "USA",
        "All-Transactions House Price Index for the United States",
        "residential",
        "nominal",
        "quarterly",
    ),
    (
        "COMREPUSQ159N",
        "USA",
        "Commercial Real Estate Prices for United States",
        "commercial",
        "nominal",
        "quarterly",
    ),
]


class SinClaveFred(RuntimeError):
    """La clave de FRED no esta configurada."""


class RealEstateFetcher(BaseFetcher):
    """Indices de precios de vivienda por pais."""

    SOURCE_NAME = "fred"
    DOMAIN = "realestate"
    RATE_LIMIT = 0.6

    def __init__(self) -> None:
        super().__init__()
        self.api_key = settings.fred_api_key

    def fetch(self, paises: list[str] | None = None) -> dict:
        """Descargar indices de precios inmobiliarios.

        Args:
            paises: subconjunto de codigos ISO3. Si es None se cargan
                todos los de `PAISES_BIS` mas las series extra de
                Estados Unidos.

        Returns:
            {"indices": N, "observaciones": N, "sin_datos": N}
        """
        if not self.api_key:
            raise SinClaveFred(
                "Falta STONKS_FRED_API_KEY en .env. Clave gratuita en "
                "https://fred.stlouisfed.org/docs/api/api_key.html"
            )

        session = get_session()
        run_id = self._start_run({"paises": paises})
        src_id = self._ensure_source(session)

        indices = 0
        observaciones = 0
        sin_datos = 0

        try:
            for definicion in self._definiciones(paises):
                codigo, pais, nombre, segmento, medida, frecuencia = (
                    definicion
                )
                puntos = self._descargar_serie(codigo)
                if not puntos:
                    sin_datos += 1
                    continue

                index_id = self._asegurar_indice(
                    session,
                    codigo,
                    pais,
                    nombre,
                    segmento,
                    medida,
                    frecuencia,
                    src_id,
                )
                n = self._guardar_valores(session, index_id, puntos)
                indices += 1
                observaciones += n
                logger.info("  %s (%s): %d observaciones", codigo, pais, n)

            self._finish_run(
                run_id,
                "success",
                fetched=observaciones,
                inserted=observaciones,
                errors=sin_datos,
            )
            logger.info(
                "Inmobiliario: %d indices, %d observaciones, %d sin datos",
                indices,
                observaciones,
                sin_datos,
            )
        except Exception as e:
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
            logger.error("Inmobiliario fallo: %s", e)
            raise
        finally:
            session.close()

        return {
            "indices": indices,
            "observaciones": observaciones,
            "sin_datos": sin_datos,
        }

    # ── Internos ─────────────────────────────────

    @staticmethod
    def _definiciones(paises: list[str] | None) -> list[tuple]:
        """Construir la lista de series a descargar."""
        salida = []
        for iso3, iso2 in PAISES_BIS:
            if paises and iso3 not in paises:
                continue
            salida.append(
                (
                    f"Q{iso2}R628BIS",
                    iso3,
                    f"Precio real de la vivienda ({iso3}, BIS)",
                    "residential",
                    "real",
                    "quarterly",
                )
            )
            salida.append(
                (
                    f"Q{iso2}N628BIS",
                    iso3,
                    f"Precio nominal de la vivienda ({iso3}, BIS)",
                    "residential",
                    "nominal",
                    "quarterly",
                )
            )
        for extra in SERIES_EXTRA:
            if not paises or extra[1] in paises:
                salida.append(extra)
        return salida

    def _descargar_serie(self, codigo: str) -> list[tuple[date, float]]:
        """Descargar las observaciones de una serie de FRED."""
        self._rate_limit()
        try:
            resp = self._session.get(
                f"{BASE_URL}/series/observations",
                params={
                    "series_id": codigo,
                    "api_key": self.api_key,
                    "file_type": "json",
                },
                timeout=45,
            )
            if resp.status_code == 400:
                # FRED devuelve 400 cuando la serie no existe.
                return []
            resp.raise_for_status()
            datos = resp.json().get("observations", [])
        except Exception as e:  # noqa: BLE001
            logger.warning("FRED %s: %s", codigo, e)
            return []

        puntos = []
        for obs in datos:
            bruto = obs.get("value")
            if bruto in (None, "", "."):
                continue
            try:
                fecha = datetime.strptime(obs["date"], "%Y-%m-%d").date()
                puntos.append((fecha, float(bruto)))
            except (ValueError, KeyError):
                continue
        return puntos

    @staticmethod
    def _asegurar_indice(
        session,
        codigo: str,
        pais: str,
        nombre: str,
        segmento: str,
        medida: str,
        frecuencia: str,
        src_id: int,
    ) -> int:
        """Crear o actualizar la definicion del indice."""
        valores = {
            "code": codigo,
            "name": nombre[:300],
            "country_code": pais,
            "segment": segmento,
            "measure": medida,
            "frequency": frecuencia,
            "source_id": src_id,
        }
        stmt = insert(PriceIndex).values(valores)
        stmt = stmt.on_conflict_do_update(
            index_elements=["code"],
            set_={k: stmt.excluded[k] for k in valores if k != "code"},
        )
        session.execute(stmt)
        session.commit()
        return session.execute(
            text("SELECT id FROM realestate.price_index WHERE code = :c"),
            {"c": codigo},
        ).scalar()

    @staticmethod
    def _guardar_valores(
        session, index_id: int, puntos: list[tuple[date, float]]
    ) -> int:
        """Upsert de las observaciones del indice."""
        hoy = date.today()
        lote = [
            {
                "index_id": index_id,
                "date": fecha,
                "value": valor,
                "is_forecast": fecha > hoy,
            }
            for fecha, valor in puntos
        ]
        for i in range(0, len(lote), CHUNK):
            trozo = lote[i : i + CHUNK]
            stmt = insert(PriceIndexValue).values(trozo)
            stmt = stmt.on_conflict_do_update(
                constraint="price_index_value_index_id_date_key",
                set_={"value": stmt.excluded.value},
            )
            session.execute(stmt)
        session.commit()
        return len(lote)

    @staticmethod
    def _ensure_source(session) -> int:
        """FRED ya esta registrado; se asegura que este habilitado."""
        src = session.query(DataSource).filter_by(name="fred").first()
        if not src:
            src = DataSource(
                name="fred",
                display_name="Federal Reserve Economic Data",
                base_url=BASE_URL,
                api_key_env_var="STONKS_FRED_API_KEY",
                is_enabled=True,
            )
            session.add(src)
        else:
            src.is_enabled = True
        session.commit()
        return src.id
