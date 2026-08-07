"""Fetcher de los factores de Fama-French (Ken French Data Library).

La Data Library de Kenneth French publica gratis las series canonicas
de factores academicos: mercado, tamano, valor, rentabilidad, inversion
y momento, tanto globales como por region.

La base ya calculaba puntuaciones propias en `gold.fact_factor_scores`,
pero no tenia ningun patron externo con el que contrastarlas. Sin una
serie de referencia no hay forma de saber si un factor propio esta bien
construido o simplemente esta capturando ruido.

Formato de los ficheros: ZIP con un CSV que lleva varias lineas de notas
antes de la cabecera, secciones anuales despues de las mensuales, y
-99.99 como marca de dato ausente. Todo eso se filtra aqui.
"""

import csv
import io
import zipfile
from datetime import date

import requests
from sqlalchemy.dialects.postgresql import insert

from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.equity import FactorReturn
from stonks.models.meta import DataSource

BASE_URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
)
CHUNK = 5000

# La fuente marca los datos ausentes con este centinela.
AUSENTE = -99.99

# (region, fichero ZIP)
DATASETS = [
    ("us", "F-F_Research_Data_5_Factors_2x3_CSV.zip"),
    ("us_mom", "F-F_Momentum_Factor_CSV.zip"),
    ("developed", "Developed_5_Factors_CSV.zip"),
    ("emerging", "Emerging_5_Factors_CSV.zip"),
    ("europe", "Europe_5_Factors_CSV.zip"),
    ("japan", "Japan_5_Factors_CSV.zip"),
    ("asia_pacific", "Asia_Pacific_ex_Japan_5_Factors_CSV.zip"),
]

# Cabecera del CSV -> nombre de factor en la base.
FACTORES = {
    "mkt-rf": "mkt_rf",
    "smb": "smb",
    "hml": "hml",
    "rmw": "rmw",
    "cma": "cma",
    "mom": "mom",
    "rf": "rf",
}


class FamaFrenchFetcher(BaseFetcher):
    """Series de factores academicos por region."""

    SOURCE_NAME = "fama_french"
    DOMAIN = "equity"
    RATE_LIMIT = 1.0

    def fetch(self, regiones: list[str] | None = None) -> dict:
        """Descargar y cargar las series de factores.

        Args:
            regiones: subconjunto de regiones a cargar. Si es None se
                cargan todas las de `DATASETS`.

        Returns:
            {"observaciones": N, "series": N, "fallidas": [...]}
        """
        session = get_session()
        run_id = self._start_run({"regiones": regiones})
        src_id = self._ensure_source(session)

        total = 0
        series = set()
        fallidas = []

        try:
            for region, fichero in DATASETS:
                if regiones and region.split("_")[0] not in regiones:
                    continue

                filas = self._descargar_dataset(fichero)
                if not filas:
                    fallidas.append(region)
                    continue

                # us_mom es el complemento de momento de la serie us.
                region_bd = "us" if region == "us_mom" else region

                lote = [
                    {
                        "region": region_bd,
                        "frequency": "monthly",
                        "factor": factor,
                        "date": fecha,
                        "value_pct": valor,
                        "source_id": src_id,
                    }
                    for fecha, factor, valor in filas
                ]
                guardadas = self._guardar(session, lote)
                total += guardadas
                series.update((region_bd, f) for _, f, _ in filas)
                logger.info(
                    "Fama-French %s: %d observaciones", region, guardadas
                )

            self._finish_run(
                run_id,
                "success" if not fallidas else "partial",
                fetched=total,
                inserted=total,
                errors=len(fallidas),
            )
            logger.info(
                "Fama-French: %d observaciones, %d series, %d fallidas",
                total,
                len(series),
                len(fallidas),
            )
        except Exception as e:
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
            logger.error("Fama-French fallo: %s", e)
            raise
        finally:
            session.close()

        return {
            "observaciones": total,
            "series": len(series),
            "fallidas": fallidas,
        }

    # ── Internos ─────────────────────────────────

    def _descargar_dataset(
        self, fichero: str
    ) -> list[tuple[date, str, float]]:
        """Descargar un ZIP y devolver (fecha, factor, valor)."""
        self._rate_limit()
        try:
            # BaseFetcher fija Accept: application/json en la sesion y
            # el servidor responde 406 a una descarga de ZIP.
            resp = self._session.get(
                BASE_URL + fichero,
                headers={
                    "User-Agent": "stonks/0.4",
                    "Accept": "application/zip, */*",
                },
                timeout=90,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning("Fama-French %s: %s", fichero, e)
            return []

        try:
            zf = zipfile.ZipFile(io.BytesIO(resp.content))
            nombre = zf.namelist()[0]
            texto = zf.read(nombre).decode("latin-1")
        except (zipfile.BadZipFile, IndexError, UnicodeDecodeError) as e:
            logger.warning("Fama-French %s ilegible: %s", fichero, e)
            return []

        return self._parsear(texto)

    @staticmethod
    def _parsear(texto: str) -> list[tuple[date, str, float]]:
        """Extraer las observaciones mensuales del CSV.

        El fichero arranca con notas en prosa, luego la cabecera, luego
        los meses en formato AAAAMM y, tras una linea en blanco, la
        seccion anual en formato AAAA. Solo interesa la mensual.
        """
        salida: list[tuple[date, str, float]] = []
        columnas: list[str] | None = None

        for linea in texto.splitlines():
            campos = [c.strip() for c in next(csv.reader([linea]), [])]
            if not campos:
                # Linea en blanco: separa la seccion mensual de la anual.
                if columnas:
                    break
                continue

            clave = campos[0]

            if columnas is None:
                # La cabecera es la primera fila cuya primera celda esta
                # vacia y cuyo resto son nombres de factor conocidos.
                if clave == "" and any(
                    c.lower() in FACTORES for c in campos[1:]
                ):
                    columnas = [c.lower() for c in campos[1:]]
                continue

            if not (len(clave) == 6 and clave.isdigit()):
                # Fin de la seccion mensual (empiezan los años).
                break

            fecha = date(int(clave[:4]), int(clave[4:6]), 1)
            for col, bruto in zip(columnas, campos[1:]):
                factor = FACTORES.get(col)
                if not factor or bruto == "":
                    continue
                try:
                    valor = float(bruto)
                except ValueError:
                    continue
                if valor <= AUSENTE:
                    continue
                salida.append((fecha, factor, valor))

        return salida

    @staticmethod
    def _guardar(session, lote: list[dict]) -> int:
        """Upsert de las observaciones de factores."""
        total = 0
        for i in range(0, len(lote), CHUNK):
            trozo = lote[i : i + CHUNK]
            stmt = insert(FactorReturn).values(trozo)
            stmt = stmt.on_conflict_do_update(
                constraint=(
                    "factor_return_region_frequency_factor_date_key"
                ),
                set_={
                    "value_pct": stmt.excluded.value_pct,
                    "source_id": stmt.excluded.source_id,
                },
            )
            session.execute(stmt)
            total += len(trozo)
        session.commit()
        return total

    @staticmethod
    def _ensure_source(session) -> int:
        """Registrar la Data Library en meta.data_source si falta."""
        src = (
            session.query(DataSource)
            .filter_by(name="fama_french")
            .first()
        )
        if not src:
            src = DataSource(
                name="fama_french",
                display_name="Kenneth French Data Library",
                base_url=BASE_URL,
                rate_limit_per_second=1.0,
                is_enabled=True,
                notes=(
                    "Factores academicos (mercado, tamano, valor, "
                    "rentabilidad, inversion, momento) por region. "
                    "Actualizacion mensual. Gratuito."
                ),
            )
            session.add(src)
            session.commit()
        return src.id
