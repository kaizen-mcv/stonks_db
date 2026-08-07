"""Certificacion de las tablas de datos.

Responde a la pregunta "¿son fiables los datos?" con evidencia en vez
de con confianza. Para cada tabla deja escrito **como** se ha
verificado, y si no se puede verificar, **por que**.

El estado se deduce solo siempre que se puede:

1. Si algun valor de `tests/referencias.yml` consulta la tabla, esta
   contrastada contra una cifra publicada fuera del proyecto.
2. Si no, pero pasa comprobaciones estructurales (OHLC posible,
   unidad plausible, minimo de filas, frescura), es coherente sin
   referencia externa.
3. Si tampoco, hace falta una declaracion escrita a mano en
   `config/certificacion.yml`, con su motivo.
4. Lo que no encaje en ninguna de las tres queda `sin_certificar`, y
   eso hace fallar el test de certificacion.

Esa cuarta regla es la pieza importante: hace imposible anadir una
tabla sin declarar como se comprueba.
"""

from datetime import datetime
from pathlib import Path

import yaml
from sqlalchemy import text

from stonks.config import settings
from stonks.db import engine
from stonks.logger import get_logger

logger = get_logger("stonks.certificacion")

CONTRASTADA = "contrastada_externamente"
COHERENTE = "coherente_sin_referencia"
NO_VERIFICABLE = "no_verificable"
SIN_CERTIFICAR = "sin_certificar"

# Esquemas que no contienen datos que certificar.
_ESQUEMAS_FUERA = {
    "pg_catalog",
    "information_schema",
    "pg_toast",
    "meta",
    "public",
}

_RAIZ = Path(__file__).resolve().parent.parent.parent


def _referencias() -> list[dict]:
    """Leer el corpus de valores de referencia."""
    ruta = _RAIZ / "tests" / "referencias.yml"
    if not ruta.exists():
        return []
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def _declaraciones() -> dict:
    """Leer las certificaciones escritas a mano."""
    ruta = settings.config_dir / "certificacion.yml"
    if not ruta.exists():
        return {}
    with open(ruta, encoding="utf-8") as f:
        datos = yaml.safe_load(f) or {}
    return datos.get("tablas", {})


def _tablas_con_referencia() -> dict[str, int]:
    """Cuantas referencias externas consulta cada tabla.

    Se busca el nombre cualificado dentro del SQL de cada referencia.
    Es un contains, no un parser: basta para saber que la tabla
    interviene, que es lo unico que hay que decidir aqui.
    """
    cuenta: dict[str, int] = {}
    for ref in _referencias():
        sql = ref.get("consulta", "")
        for ruta in _tablas_de_datos():
            if ruta in sql:
                cuenta[ruta] = cuenta.get(ruta, 0) + 1
    return cuenta


_cache_tablas: dict[str, int] = {}


def _tablas_con_filas() -> dict[str, int]:
    """Tablas a certificar, con su numero aproximado de filas.

    Se usa la estimacion del planificador (`reltuples`) en vez de un
    `count(*)`: contar de verdad `gold.fact_fundamentals_pit` (33 M) y
    `equity.price_daily` (29 M) tardaba minutos y dejaba la suite de
    tests colgada. Aqui el numero es informativo —lo que se certifica
    es el metodo de verificacion, no el volumen—, asi que una
    estimacion vale. Las que nunca se han analizado devuelven -1 y esas
    si se cuentan.
    """
    global _cache_tablas
    if _cache_tablas:
        return _cache_tablas
    with engine.begin() as conn:
        filas = conn.execute(
            text(
                "SELECT n.nspname, c.relname, c.reltuples::bigint "
                "FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE c.relkind IN ('r', 'p', 'm') "
                "  AND NOT c.relispartition "
                "  AND NOT (n.nspname = ANY(:fuera)) "
                "ORDER BY 1, 2"
            ),
            {"fuera": sorted(_ESQUEMAS_FUERA)},
        ).fetchall()

        salida = {}
        for esquema, tabla, estimadas in filas:
            ruta = f"{esquema}.{tabla}"
            if estimadas is None or estimadas < 0:
                estimadas = conn.execute(
                    text(f"SELECT count(*) FROM {ruta}")
                ).scalar()
            salida[ruta] = int(estimadas or 0)

    _cache_tablas = salida
    return _cache_tablas


def _tablas_de_datos() -> list[str]:
    """Tablas y vistas materializadas que hay que certificar."""
    return list(_tablas_con_filas())


def _estructurales() -> set[str]:
    """Tablas que alguna comprobacion estructural vigila.

    Se leen de las propias constantes de los checks, no de una lista
    aparte: si manana se anade una tabla a `_MINIMOS`, queda
    certificada sin tocar nada aqui.
    """
    from stonks import quality_datos as q

    vigiladas = {t for t, _ in q._TABLAS_OHLC}
    vigiladas |= set(q._MINIMOS)
    vigiladas |= {s[0] for s in q._SLA}
    return vigiladas


def certificar(por: str = "stonks certify") -> list[dict]:
    """Recorrer las tablas, decidir su estado y persistirlo."""
    con_referencia = _tablas_con_referencia()
    declaradas = _declaraciones()
    estructurales = _estructurales()
    resultado = []

    with engine.begin() as conn:
        for ruta, filas in _tablas_con_filas().items():
            esquema, tabla = ruta.split(".", 1)
            declarada = declaradas.get(ruta, {})
            n_refs = con_referencia.get(ruta, 0)

            if n_refs:
                estado = CONTRASTADA
                metodo = f"{n_refs} valor(es) en tests/referencias.yml"
                motivo = None
            elif declarada.get("estado"):
                estado = declarada["estado"]
                metodo = declarada.get("metodo")
                motivo = declarada.get("motivo")
            elif ruta in estructurales:
                estado = COHERENTE
                metodo = "checks estructurales de stonks.quality_datos"
                motivo = None
            else:
                estado = SIN_CERTIFICAR
                metodo = None
                motivo = (
                    "nadie ha declarado como se verifica; anadela a "
                    "config/certificacion.yml o a tests/referencias.yml"
                )

            conn.execute(
                text(
                    "DELETE FROM meta.table_certification "
                    "WHERE schema_name = :e AND table_name = :t"
                ),
                {"e": esquema, "t": tabla},
            )
            conn.execute(
                text(
                    "INSERT INTO meta.table_certification "
                    "(schema_name, table_name, estado, metodo, motivo, "
                    " filas, referencias, certificado_por, certified_at) "
                    "VALUES (:e, :t, :est, :met, :mot, :f, :r, :p, :d)"
                ),
                {
                    "e": esquema,
                    "t": tabla,
                    "est": estado,
                    "met": metodo,
                    "mot": motivo,
                    "f": filas,
                    "r": n_refs,
                    "p": por,
                    "d": datetime.now(),
                },
            )
            resultado.append(
                {
                    "tabla": ruta,
                    "estado": estado,
                    "filas": filas,
                    "metodo": metodo,
                    "motivo": motivo,
                }
            )

    resumen: dict[str, int] = {}
    for r in resultado:
        resumen[r["estado"]] = resumen.get(r["estado"], 0) + 1
    logger.info("Certificacion: %s", resumen)
    return resultado


def resumen() -> dict[str, int]:
    """Contar tablas por estado, sin recertificar."""
    with engine.begin() as conn:
        filas = conn.execute(
            text(
                "SELECT estado, count(*) FROM meta.table_certification "
                "GROUP BY estado ORDER BY 2 DESC"
            )
        ).fetchall()
    return {e: n for e, n in filas}
