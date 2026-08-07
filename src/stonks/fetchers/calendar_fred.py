"""Fetcher del calendario economico (esquema calendar).

El esquema `calendar` existia sin ninguna tabla. Se rellena con la API
de *releases* de FRED, que publica gratis el catalogo de publicaciones
estadisticas de Estados Unidos (nominas, IPC, PIB, decisiones de la
Reserva Federal...) junto con sus fechas pasadas y futuras.

Saber **cuando** se publico un dato es tan importante como el dato. Es
lo que permite alinear una serie macro con el momento en que el mercado
la conocio, y es el complemento natural de
`macro.data_point.is_forecast` y de `macro.data_point_vintage`.
"""

import time
from datetime import date, datetime

import requests
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from stonks.config import settings
from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.calendar import Release, ReleaseDate
from stonks.models.meta import DataSource

BASE_URL = "https://api.stlouisfed.org/fred"
CHUNK = 5000

# Todas las publicaciones de FRED son de organismos estadounidenses.
PAIS = "USA"


class SinClaveFred(RuntimeError):
    """La clave de FRED no esta configurada."""


class CalendarFetcher(BaseFetcher):
    """Catalogo de publicaciones estadisticas y sus fechas."""

    SOURCE_NAME = "fred"
    DOMAIN = "calendar"
    RATE_LIMIT = 0.6

    def __init__(self) -> None:
        super().__init__()
        self.api_key = settings.fred_api_key

    def fetch(
        self,
        desde: str = "2000-01-01",
        hasta: str | None = None,
    ) -> dict:
        """Descargar publicaciones y sus fechas de salida.

        Args:
            desde: fecha inicial del rango de fechas de publicacion.
            hasta: fecha final. Por defecto un ano por delante, para
                capturar el calendario futuro ya anunciado.

        Returns:
            {"publicaciones": N, "fechas": N}
        """
        if not self.api_key:
            raise SinClaveFred(
                "Falta STONKS_FRED_API_KEY en .env. Clave gratuita en "
                "https://fred.stlouisfed.org/docs/api/api_key.html"
            )

        if hasta is None:
            hoy = date.today()
            hasta = date(hoy.year + 1, hoy.month, 1).isoformat()

        session = get_session()
        run_id = self._start_run({"desde": desde, "hasta": hasta})
        src_id = self._ensure_source(session)

        publicaciones = 0
        fechas = 0

        try:
            catalogo = self._descargar_releases()
            publicaciones = self._guardar_releases(
                session, catalogo, src_id
            )

            mapa = self._mapa_releases(session, src_id)
            calendario = self._descargar_fechas(
                desde, hasta, list(mapa.keys())
            )
            fechas = self._guardar_fechas(session, calendario, mapa)

            self._finish_run(
                run_id,
                "success",
                fetched=publicaciones + fechas,
                inserted=publicaciones + fechas,
            )
            logger.info(
                "Calendario: %d publicaciones, %d fechas",
                publicaciones,
                fechas,
            )
        except Exception as e:
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
            logger.error("Calendario fallo: %s", e)
            raise
        finally:
            session.close()

        return {"publicaciones": publicaciones, "fechas": fechas}

    # ── Internos ─────────────────────────────────

    def _pedir(self, endpoint: str, params: dict) -> dict:
        """Llamada a FRED con clave, formato y reintentos.

        El calendario son casi 90.000 fechas paginadas de 1.000 en
        1.000, y FRED se vuelve lento en los offsets profundos: sin
        reintento, una sola lectura lenta aborta la carga entera.
        """
        params = dict(params)
        params.update({"api_key": self.api_key, "file_type": "json"})

        for intento in range(1, self.MAX_RETRIES + 1):
            self._rate_limit()
            try:
                resp = self._session.get(
                    f"{BASE_URL}/{endpoint}", params=params, timeout=120
                )
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as e:
                logger.warning(
                    "FRED %s intento %d/%d: %s",
                    endpoint,
                    intento,
                    self.MAX_RETRIES,
                    e,
                )
                if intento == self.MAX_RETRIES:
                    raise
                time.sleep(2**intento)
        return {}

    def _descargar_releases(self) -> list[dict]:
        """Catalogo completo de publicaciones."""
        salida: list[dict] = []
        offset = 0
        while True:
            datos = self._pedir(
                "releases", {"limit": 1000, "offset": offset}
            )
            lote = datos.get("releases", [])
            salida.extend(lote)
            if len(lote) < 1000:
                break
            offset += 1000
        logger.info("Calendario: %d publicaciones en el catalogo", len(salida))
        return salida

    def _descargar_fechas(
        self, desde: str, hasta: str, ids: list[str]
    ) -> list[dict]:
        """Fechas de publicacion, consultadas publicacion a publicacion.

        El endpoint global `releases/dates` devuelve casi 90.000 filas y
        FRED responde 504 a partir de unos pocos miles de offset. Pedir
        las fechas de cada release por separado son mas peticiones pero
        todas pequenas, y un fallo puntual solo pierde una publicacion
        en lugar de abortar la carga entera.
        """
        salida: list[dict] = []
        fallidas = 0

        for i, rid in enumerate(ids, 1):
            try:
                datos = self._pedir(
                    "release/dates",
                    {
                        "release_id": rid,
                        "realtime_start": desde,
                        "realtime_end": hasta,
                        "include_release_dates_with_no_data": "true",
                        "limit": 10000,
                        "sort_order": "asc",
                    },
                )
            except requests.RequestException:
                fallidas += 1
                continue

            for f in datos.get("release_dates", []):
                f.setdefault("release_id", rid)
                salida.append(f)

            if i % 50 == 0:
                logger.info(
                    "Calendario: %d/%d publicaciones, %d fechas",
                    i,
                    len(ids),
                    len(salida),
                )

        if fallidas:
            logger.warning(
                "Calendario: %d publicaciones sin fechas por error de red",
                fallidas,
            )
        return salida

    @staticmethod
    def _guardar_releases(
        session, catalogo: list[dict], src_id: int
    ) -> int:
        """Upsert del catalogo de publicaciones."""
        lote = []
        for r in catalogo:
            rid = r.get("id")
            nombre = r.get("name")
            if rid is None or not nombre:
                continue
            lote.append(
                {
                    "external_id": str(rid),
                    "name": str(nombre)[:300],
                    "country_code": PAIS,
                    "link": (r.get("link") or None),
                    "source_id": src_id,
                }
            )

        for i in range(0, len(lote), CHUNK):
            trozo = lote[i : i + CHUNK]
            stmt = insert(Release).values(trozo)
            stmt = stmt.on_conflict_do_update(
                constraint="release_source_id_external_id_key",
                set_={
                    "name": stmt.excluded.name,
                    "link": stmt.excluded.link,
                },
            )
            session.execute(stmt)
        session.commit()
        return len(lote)

    @staticmethod
    def _mapa_releases(session, src_id: int) -> dict[str, int]:
        """Diccionario external_id -> id interno."""
        filas = session.execute(
            text(
                "SELECT external_id, id FROM calendar.release "
                "WHERE source_id = :s"
            ),
            {"s": src_id},
        ).fetchall()
        return {ext: interno for ext, interno in filas}

    @staticmethod
    def _guardar_fechas(
        session, calendario: list[dict], mapa: dict[str, int]
    ) -> int:
        """Upsert de las fechas de publicacion."""
        hoy = date.today()
        vistos: set[tuple[int, date]] = set()
        lote = []

        for f in calendario:
            rid = str(f.get("release_id", ""))
            release_id = mapa.get(rid)
            bruto = f.get("date")
            if not release_id or not bruto:
                continue
            try:
                fecha = datetime.strptime(bruto, "%Y-%m-%d").date()
            except ValueError:
                continue

            clave = (release_id, fecha)
            if clave in vistos:
                continue
            vistos.add(clave)

            lote.append(
                {
                    "release_id": release_id,
                    "date": fecha,
                    # Anunciada pero aun no publicada.
                    "is_scheduled": fecha > hoy,
                }
            )

        for i in range(0, len(lote), CHUNK):
            trozo = lote[i : i + CHUNK]
            stmt = insert(ReleaseDate).values(trozo)
            stmt = stmt.on_conflict_do_update(
                constraint="release_date_release_id_date_key",
                set_={"is_scheduled": stmt.excluded.is_scheduled},
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
