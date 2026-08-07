"""Fetcher de identificadores LEI (GLEIF).

El LEI (Legal Entity Identifier, ISO 17442) es el unico identificador
global, publico y gratuito de entidades juridicas. GLEIF lo publica via
API sin clave.

El modelo cruzaba empresas por `ticker`, que no es unico entre mercados
(AAPL en NASDAQ y en otra bolsa) ni estable en el tiempo (los tickers se
reasignan tras una fusion o una quiebra). El LEI resuelve eso y ademas
permite cruzar `stonks_db` con `borme_db` y `supliers_db`, que usan el
mismo estandar.

La correspondencia se hace por nombre legal, que es lo unico que ofrece
la API sin pasar por servicios de pago. Por eso se exige coincidencia
alta y se deja sin asignar lo dudoso: un LEI equivocado es peor que un
LEI ausente.
"""

import re
import unicodedata
from difflib import SequenceMatcher

import requests
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.meta import DataSource
from stonks.models.ref import LegalEntity

BASE_URL = "https://api.gleif.org/api/v1/lei-records"
CHUNK = 500

# Similitud minima entre el nombre de la empresa y el nombre legal del
# registro LEI para aceptar la correspondencia.
UMBRAL_SIMILITUD = 0.87

# Sufijos societarios que no aportan a la comparacion de nombres.
SUFIJOS = {
    "inc", "incorporated", "corp", "corporation", "co", "company",
    "ltd", "limited", "plc", "llc", "lp", "llp", "sa", "s a",
    "ag", "nv", "n v", "se", "spa", "s p a", "ab", "asa", "oyj",
    "as", "kk", "holdings", "holding", "group", "the", "class",
    "sas", "gmbh", "bv", "b v", "pte", "pcl", "tbk", "aps",
}


class GleifFetcher(BaseFetcher):
    """Catalogo LEI y correspondencia con equity.company."""

    SOURCE_NAME = "gleif"
    DOMAIN = "ref"
    RATE_LIMIT = 0.5

    def __init__(self) -> None:
        super().__init__()
        self._session.headers.update(
            {"Accept": "application/vnd.api+json"}
        )

    def enlazar_empresas(self, limite: int | None = None) -> dict:
        """Buscar el LEI de las empresas que aun no lo tienen.

        Args:
            limite: maximo de empresas a resolver en esta pasada.

        Returns:
            {"buscadas": N, "enlazadas": N, "sin_match": N}
        """
        session = get_session()
        run_id = self._start_run({"limite": limite})
        src_id = self._ensure_source(session)

        buscadas = 0
        enlazadas = 0
        sin_match = 0

        try:
            sql = (
                "SELECT id, name, country_code FROM equity.company "
                "WHERE lei IS NULL AND name IS NOT NULL "
                "ORDER BY market_cap_usd DESC NULLS LAST"
            )
            if limite:
                sql += f" LIMIT {int(limite)}"
            empresas = session.execute(text(sql)).fetchall()

            logger.info("GLEIF: %d empresas sin LEI", len(empresas))

            for company_id, nombre, pais in empresas:
                buscadas += 1
                registro = self._buscar_por_nombre(session, nombre, pais)
                if not registro:
                    sin_match += 1
                    continue

                self._guardar_entidad(session, registro)
                session.execute(
                    text(
                        "UPDATE equity.company SET lei = :lei "
                        "WHERE id = :cid"
                    ),
                    {"lei": registro["lei"], "cid": company_id},
                )
                session.commit()
                enlazadas += 1
                logger.info(
                    "  %s -> %s (%s)",
                    nombre[:40],
                    registro["lei"],
                    registro["legal_name"][:40],
                )

            self._finish_run(
                run_id,
                "success",
                fetched=buscadas,
                updated=enlazadas,
            )
            logger.info(
                "GLEIF: %d buscadas, %d enlazadas, %d sin match",
                buscadas,
                enlazadas,
                sin_match,
            )
        except Exception as e:
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
            logger.error("GLEIF fallo: %s", e)
            raise
        finally:
            session.close()

        return {
            "buscadas": buscadas,
            "enlazadas": enlazadas,
            "sin_match": sin_match,
        }

    # ── Internos ─────────────────────────────────

    def _buscar_por_nombre(
        self, session, nombre: str, pais: str | None
    ) -> dict | None:
        """Buscar un LEI cuyo nombre legal coincida con `nombre`.

        El filtro de GLEIF es difuso y la puntuacion societaria lo
        despista ("Samsung Electronics Co., Ltd." no devuelve nada util,
        "Samsung Electronics" si), asi que se consultan dos variantes.

        El riesgo real no es no encontrar nada, sino enlazar una filial
        en vez de la matriz: buscar "Samsung Electronics Co., Ltd."
        devuelve "SAMSUNG ELECTRONICS GMBH", que normaliza al mismo
        texto y puntua 1.0. Por eso, cuando se conoce el pais de la
        empresa, la coincidencia de pais es un requisito, no un
        desempate.

        Devuelve None si ningun candidato supera el umbral o si ninguno
        esta en el pais esperado: es preferible dejar la empresa sin LEI
        a asignarle uno erroneo.
        """
        objetivo = self._normalizar(nombre)
        if not objetivo:
            return None

        candidatos: dict[str, tuple[float, dict]] = {}
        for consulta in (nombre, objetivo):
            for registro in self._consultar(consulta):
                score = SequenceMatcher(
                    None, objetivo, self._normalizar(registro["legal_name"])
                ).ratio()
                previo = candidatos.get(registro["lei"])
                if previo is None or score > previo[0]:
                    candidatos[registro["lei"]] = (score, registro)
            if consulta == objetivo:
                break

        if not candidatos:
            return None

        viables = [
            (s, r)
            for s, r in candidatos.values()
            if s >= UMBRAL_SIMILITUD
        ]
        if not viables:
            return None

        # Filtro duro por pais: descarta las filiales extranjeras que
        # normalizan igual que la matriz.
        pais2 = None
        if pais:
            pais2 = session.execute(
                text("SELECT code_alpha2 FROM ref.country WHERE code = :c"),
                {"c": pais},
            ).scalar()
        if pais2:
            viables = [
                (s, r)
                for s, r in viables
                if r.get("country_alpha2") == pais2
            ]
            if not viables:
                return None

        def _prioridad(par: tuple) -> tuple:
            # 1) mayor similitud  2) sin matriz (es la cabecera)
            # 3) nombre mas corto (la matriz suele serlo)
            score, reg = par
            return (
                -score,
                0 if not reg.get("parent_lei") else 1,
                len(reg["legal_name"]),
            )

        return sorted(viables, key=_prioridad)[0][1]

    def _consultar(self, nombre: str) -> list[dict]:
        """Lanzar una consulta a GLEIF y devolver candidatos activos."""
        self._rate_limit()
        try:
            resp = self._session.get(
                BASE_URL,
                params={
                    "filter[entity.legalName]": nombre,
                    "page[size]": 15,
                },
                timeout=30,
            )
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            datos = resp.json().get("data", [])
        except (requests.RequestException, ValueError) as e:
            logger.warning("GLEIF '%s': %s", nombre[:40], e)
            return []

        salida = []
        for item in datos:
            registro = self._parsear(item)
            # Solo entidades vivas: una fusionada apunta a otra cosa.
            if registro and registro.get("entity_status") == "ACTIVE":
                salida.append(registro)
        return salida

    @staticmethod
    def _normalizar(nombre: str) -> str:
        """Nombre comparable: sin acentos, puntuacion ni sufijos.

        Las formas societarias con punto ("N.V.", "S.A.", "B.V.")
        quedan como palabras sueltas al quitar la puntuacion, asi que
        los sufijos de varias palabras se eliminan como secuencia antes
        de filtrar palabra a palabra.
        """
        txt = unicodedata.normalize("NFKD", nombre.lower())
        txt = "".join(c for c in txt if not unicodedata.combining(c))
        txt = re.sub(r"[^a-z0-9 ]", " ", txt)
        palabras = txt.split()

        compuestos = sorted(
            (s.split() for s in SUFIJOS if " " in s),
            key=len,
            reverse=True,
        )
        for secuencia in compuestos:
            n = len(secuencia)
            i = 0
            while i <= len(palabras) - n:
                if palabras[i : i + n] == secuencia:
                    del palabras[i : i + n]
                else:
                    i += 1

        return " ".join(p for p in palabras if p not in SUFIJOS)

    @staticmethod
    def _parsear(item: dict) -> dict | None:
        """Extraer los campos de interes de un registro GLEIF."""
        atributos = item.get("attributes") or {}
        entidad = atributos.get("entity") or {}
        nombre = (entidad.get("legalName") or {}).get("name")
        lei = atributos.get("lei") or item.get("id")
        if not lei or not nombre:
            return None

        direccion = entidad.get("legalAddress") or {}
        pais_alpha2 = direccion.get("country")
        registro = atributos.get("registration") or {}

        return {
            "lei": lei[:20],
            "legal_name": nombre[:500],
            "country_alpha2": pais_alpha2,
            "legal_jurisdiction": (entidad.get("jurisdiction") or "")[:10]
            or None,
            "entity_status": (entidad.get("status") or "")[:20] or None,
            "entity_category": (entidad.get("category") or "")[:40] or None,
            "parent_lei": (
                (entidad.get("associatedEntity") or {}).get("lei")
            ),
            "registration_status": (
                registro.get("status") or ""
            )[:30]
            or None,
            "city": (direccion.get("city") or "")[:120] or None,
        }

    @staticmethod
    def _guardar_entidad(session, registro: dict) -> None:
        """Upsert de la entidad legal en ref.legal_entity."""
        # ref.legal_entity referencia ref.country por ISO3, pero GLEIF
        # publica ISO2: se traduce con el catalogo propio.
        pais3 = None
        if registro.get("country_alpha2"):
            pais3 = session.execute(
                text("SELECT code FROM ref.country WHERE code_alpha2 = :a"),
                {"a": registro["country_alpha2"]},
            ).scalar()

        valores = {
            "lei": registro["lei"],
            "legal_name": registro["legal_name"],
            "country_code": pais3,
            "legal_jurisdiction": registro["legal_jurisdiction"],
            "entity_status": registro["entity_status"],
            "entity_category": registro["entity_category"],
            "parent_lei": registro["parent_lei"],
            "registration_status": registro["registration_status"],
            "city": registro["city"],
        }
        stmt = insert(LegalEntity).values(valores)
        stmt = stmt.on_conflict_do_update(
            index_elements=["lei"],
            set_={
                k: stmt.excluded[k]
                for k in valores
                if k != "lei"
            },
        )
        session.execute(stmt)

    @staticmethod
    def _ensure_source(session) -> int:
        """Registrar GLEIF en meta.data_source si falta."""
        src = session.query(DataSource).filter_by(name="gleif").first()
        if not src:
            src = DataSource(
                name="gleif",
                display_name="GLEIF (Legal Entity Identifier)",
                base_url=BASE_URL,
                rate_limit_per_second=2.0,
                is_enabled=True,
                notes=(
                    "Identificadores LEI (ISO 17442). Publico y sin "
                    "clave. Permite cruzar con borme_db y supliers_db."
                ),
            )
            session.add(src)
            session.commit()
        return src.id
