"""ampliar escala de precios a NUMERIC(20,10)

Revision ID: f216205f1991
Revises: 8dcae2bed6b5
Create Date: 2026-08-06

`NUMERIC(14,4)` truncaba a cero las acciones sub-centimo: 29.443 filas
de `equity.price_daily` con `close = 0.0000` en 48 empresas (HCMC,
MMEX y GTCH cotizan a 0,0001 $). En crypto pasaba lo mismo con
`NUMERIC(18,8)`: BABYDOGE tenia la serie entera a cero.

Diez decimales dan cuatro o cinco cifras significativas a un precio de
1e-6, y diez digitos enteros siguen sobrando para el valor mas caro
del universo.

Notas de implementacion:

1. PostgreSQL reescribe la tabla entera cada vez que cambia la escala
   de una columna numerica. Por eso las columnas de cada tabla van en
   un unico `ALTER TABLE`: hacerlo columna a columna, como genera el
   autogenerate de Alembic, provocaria cinco reescrituras de los 4 GB
   de `equity.price_daily` en lugar de una.

2. Cuatro vistas materializadas leen esas columnas y bloquean el
   cambio de tipo (`equity.ratios_mv`, `gold.mart_benchmark_returns`,
   `gold.mart_crypto_overview` y `gold.mart_etf_category`). Se guardan
   su definicion y sus indices, se sueltan, se altera y se recrean.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f216205f1991"
down_revision: Union[str, Sequence[str], None] = "8dcae2bed6b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (tabla, columnas, escala anterior para el downgrade)
TABLAS = [
    ("equity.price_daily",
     ["open", "high", "low", "close", "adj_close"], "NUMERIC(14,4)"),
    ("equity.price_intraday",
     ["open", "high", "low", "close"], "NUMERIC(14,4)"),
    ("equity.index_price",
     ["open", "high", "low", "close"], "NUMERIC(14,4)"),
    ("crypto.price_daily",
     ["open", "high", "low", "close"], "NUMERIC(18,8)"),
    ("crypto.price_intraday",
     ["open", "high", "low", "close"], "NUMERIC(18,8)"),
    ("commodity.price_daily",
     ["open", "high", "low", "close"], "NUMERIC(14,4)"),
    ("commodity.price_intraday",
     ["open", "high", "low", "close"], "NUMERIC(14,4)"),
    ("forex.rate_daily",
     ["open", "high", "low", "close"], "NUMERIC(14,8)"),
    ("forex.rate_intraday",
     ["open", "high", "low", "close"], "NUMERIC(14,8)"),
    ("deriv.futures_daily",
     ["open", "high", "low", "close"], "NUMERIC(14,4)"),
    ("fund.nav_daily", ["nav"], "NUMERIC(14,6)"),
]

NUEVA = "NUMERIC(20,10)"


def _mvs_dependientes(conn) -> list[tuple]:
    """Vistas materializadas que leen las columnas a modificar.

    Devuelve (nombre_cualificado, definicion, [definiciones_indice]).
    Se consulta al vuelo en vez de codificar la lista: si manana se
    anade otro mart sobre precios, la migracion sigue funcionando.
    """
    filas = conn.execute(
        sa.text(
            "SELECT DISTINCT n2.nspname || '.' || dep.relname "
            "FROM pg_depend d "
            "JOIN pg_rewrite r ON r.oid = d.objid "
            "JOIN pg_class dep ON dep.oid = r.ev_class "
            "JOIN pg_namespace n2 ON n2.oid = dep.relnamespace "
            "JOIN pg_class src ON src.oid = d.refobjid "
            "JOIN pg_namespace n ON n.oid = src.relnamespace "
            "WHERE dep.relkind = 'm' "
            "AND n.nspname || '.' || src.relname = ANY(:tablas)"
        ),
        {"tablas": [t for t, _, _ in TABLAS]},
    ).fetchall()

    salida = []
    for (nombre,) in filas:
        definicion = conn.execute(
            sa.text("SELECT pg_get_viewdef(to_regclass(:n), true)"),
            {"n": nombre},
        ).scalar()
        esquema, tabla = nombre.split(".")
        indices = [
            fila[0]
            for fila in conn.execute(
                sa.text(
                    "SELECT indexdef FROM pg_indexes "
                    "WHERE schemaname = :e AND tablename = :t"
                ),
                {"e": esquema, "t": tabla},
            ).fetchall()
        ]
        salida.append((nombre, definicion, indices))
    return salida


def _alterar(tabla: str, columnas: list[str], tipo: str) -> None:
    """Cambiar el tipo de varias columnas en un solo ALTER TABLE."""
    clausulas = ", ".join(
        f"ALTER COLUMN {col} TYPE {tipo}" for col in columnas
    )
    op.execute(f"ALTER TABLE {tabla} {clausulas}")


def _migrar(destino_por_tabla) -> None:
    """Soltar las MVs dependientes, alterar y recrearlas."""
    conn = op.get_bind()
    # Si el pipeline nocturno esta escribiendo, es preferible fallar
    # rapido y reintentar que dejar un ACCESS EXCLUSIVE en cola
    # bloqueando a todos los lectores detras.
    op.execute("SET LOCAL lock_timeout = '60s'")

    mvs = _mvs_dependientes(conn)
    for nombre, _, _ in mvs:
        op.execute(f"DROP MATERIALIZED VIEW IF EXISTS {nombre} CASCADE")

    for tabla, columnas, anterior in TABLAS:
        _alterar(tabla, columnas, destino_por_tabla(anterior))

    for nombre, definicion, indices in mvs:
        op.execute(f"CREATE MATERIALIZED VIEW {nombre} AS {definicion}")
        for indexdef in indices:
            op.execute(indexdef)


def upgrade() -> None:
    """Ampliar la escala de todas las columnas de precio."""
    _migrar(lambda _anterior: NUEVA)


def downgrade() -> None:
    """Volver a la escala anterior.

    Atencion: los decimales por debajo de la escala antigua se pierden
    de forma irreversible al revertir.
    """
    _migrar(lambda anterior: anterior)
