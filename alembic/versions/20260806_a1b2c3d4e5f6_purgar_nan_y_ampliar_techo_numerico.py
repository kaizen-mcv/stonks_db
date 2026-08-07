"""purgar NaN y ampliar el techo numerico

Revision ID: a1b2c3d4e5f6
Revises: 552fd8525b1b
Create Date: 2026-08-06

Dos agujeros de la migracion anterior.

**1. Los NaN atravesaban todas las restricciones.** PostgreSQL admite
`NaN` en `NUMERIC` y lo ordena por encima de cualquier numero:
`'NaN'::numeric > 0` es TRUE, asi que los CHECK de `close > 0` no lo
filtraban. Habia 1.007 valores repartidos por cuatro tablas, y bastan
para que cualquier `max()`, `avg()` o `sum()` sobre esas series
devuelva NaN y contamine los marts que las agregan.

Ojo con la semantica: en `NUMERIC`, a diferencia de IEEE 754,
`NaN = NaN` es TRUE, asi que el truco habitual de `x = x` no sirve
como filtro. La expresion que si funciona es
`x > 0 AND x < 'Infinity'`, porque NaN se ordena por encima del
infinito y falla la segunda condicion. De paso cubre los infinitos,
que `NUMERIC` tambien admite desde PostgreSQL 14.

**2. El techo de 10^10 era demasiado bajo.** `NUMERIC(20,10)` deja
diez digitos enteros y ya habia provocado cinco fallos de
`NumericValueOutOfRange`: hay activos en divisas debiles e indices que
lo superan. Se pasa a `NUMERIC(24,10)`, que sube el techo a 10^14 sin
perder decimales.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "552fd8525b1b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (tabla, columnas a ampliar)
TABLAS = [
    ("equity.price_daily",
     ["open", "high", "low", "close", "adj_close"]),
    ("equity.price_intraday", ["open", "high", "low", "close"]),
    ("equity.index_price", ["open", "high", "low", "close"]),
    ("crypto.price_daily", ["open", "high", "low", "close"]),
    ("crypto.price_intraday", ["open", "high", "low", "close"]),
    ("commodity.price_daily", ["open", "high", "low", "close"]),
    ("commodity.price_intraday", ["open", "high", "low", "close"]),
    ("forex.rate_daily", ["open", "high", "low", "close"]),
    ("forex.rate_intraday", ["open", "high", "low", "close"]),
    ("deriv.futures_daily", ["open", "high", "low", "close"]),
    ("fund.nav_daily", ["nav"]),
]

# Tablas con OHLC completo, donde viven los CHECK.
CON_OHLC = [
    "equity.price_daily",
    "crypto.price_daily",
    "commodity.price_daily",
    "forex.rate_daily",
    "equity.index_price",
    "deriv.futures_daily",
]

NUEVA = "NUMERIC(24,10)"
ANTERIOR = "NUMERIC(20,10)"

# Valor finito y positivo: excluye cero, negativos, NaN e infinitos.
FINITO = "{col} > 0 AND {col} < 'Infinity'::numeric"


def _mvs_dependientes(conn) -> list[tuple]:
    """Vistas materializadas que leen las columnas a modificar."""
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
        {"tablas": [t for t, _ in TABLAS]},
    ).fetchall()

    salida = []
    for (nombre,) in filas:
        definicion = conn.execute(
            sa.text("SELECT pg_get_viewdef(to_regclass(:n), true)"),
            {"n": nombre},
        ).scalar()
        esquema, tabla = nombre.split(".")
        indices = [
            f[0]
            for f in conn.execute(
                sa.text(
                    "SELECT indexdef FROM pg_indexes "
                    "WHERE schemaname = :e AND tablename = :t"
                ),
                {"e": esquema, "t": tabla},
            ).fetchall()
        ]
        salida.append((nombre, definicion, indices))
    return salida


def _purgar_no_finitos() -> None:
    """Borrar las filas con NaN o infinito en el cierre."""
    for tabla in CON_OHLC:
        col = "close"
        op.execute(
            f"DELETE FROM {tabla} "
            f"WHERE NOT ({FINITO.format(col=col)})"
        )
    op.execute(
        "DELETE FROM fund.nav_daily "
        f"WHERE NOT ({FINITO.format(col='nav')})"
    )
    # En las columnas opcionales basta con anularlas: la fila sigue
    # siendo util si el cierre es bueno.
    for tabla in CON_OHLC:
        for col in ("open", "high", "low"):
            op.execute(
                f"UPDATE {tabla} SET {col} = NULL "
                f"WHERE {col} IS NOT NULL "
                f"AND NOT ({col} < 'Infinity'::numeric)"
            )
    op.execute(
        "UPDATE equity.price_daily SET adj_close = NULL "
        "WHERE adj_close IS NOT NULL "
        "AND NOT (adj_close < 'Infinity'::numeric)"
    )


def upgrade() -> None:
    """Purgar no finitos, ampliar el techo y endurecer los CHECK."""
    op.execute("SET LOCAL lock_timeout = '60s'")

    _purgar_no_finitos()

    # Las restricciones antiguas dejaban pasar NaN.
    for tabla in CON_OHLC:
        nombre = tabla.split(".")[1]
        op.execute(
            f"ALTER TABLE {tabla} DROP CONSTRAINT IF EXISTS "
            f"ck_{nombre}_cierre_positivo"
        )

    conn = op.get_bind()
    mvs = _mvs_dependientes(conn)
    for nombre, _, _ in mvs:
        op.execute(f"DROP MATERIALIZED VIEW IF EXISTS {nombre} CASCADE")

    for tabla, columnas in TABLAS:
        clausulas = ", ".join(
            f"ALTER COLUMN {c} TYPE {NUEVA}" for c in columnas
        )
        op.execute(f"ALTER TABLE {tabla} {clausulas}")

    for nombre, definicion, indices in mvs:
        op.execute(f"CREATE MATERIALIZED VIEW {nombre} AS {definicion}")
        for indexdef in indices:
            op.execute(indexdef)

    # Restriccion nueva: finita, no solo positiva.
    for tabla in CON_OHLC:
        nombre = tabla.split(".")[1]
        op.execute(
            f"ALTER TABLE {tabla} ADD CONSTRAINT "
            f"ck_{nombre}_cierre_finito "
            f"CHECK ({FINITO.format(col='close')}) NOT VALID"
        )
        op.execute(
            f"ALTER TABLE {tabla} "
            f"VALIDATE CONSTRAINT ck_{nombre}_cierre_finito"
        )


def downgrade() -> None:
    """Volver al techo anterior y a la restriccion laxa."""
    op.execute("SET LOCAL lock_timeout = '60s'")

    for tabla in CON_OHLC:
        nombre = tabla.split(".")[1]
        op.execute(
            f"ALTER TABLE {tabla} DROP CONSTRAINT IF EXISTS "
            f"ck_{nombre}_cierre_finito"
        )

    conn = op.get_bind()
    mvs = _mvs_dependientes(conn)
    for nombre, _, _ in mvs:
        op.execute(f"DROP MATERIALIZED VIEW IF EXISTS {nombre} CASCADE")

    for tabla, columnas in TABLAS:
        clausulas = ", ".join(
            f"ALTER COLUMN {c} TYPE {ANTERIOR}" for c in columnas
        )
        op.execute(f"ALTER TABLE {tabla} {clausulas}")

    for nombre, definicion, indices in mvs:
        op.execute(f"CREATE MATERIALIZED VIEW {nombre} AS {definicion}")
        for indexdef in indices:
            op.execute(indexdef)

    for tabla in CON_OHLC:
        nombre = tabla.split(".")[1]
        op.execute(
            f"ALTER TABLE {tabla} ADD CONSTRAINT "
            f"ck_{nombre}_cierre_positivo CHECK (close > 0) NOT VALID"
        )
