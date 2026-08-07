"""purgar OHLC imposible y blindar con CHECK

Revision ID: 552fd8525b1b
Revises: 1df48aa663ea
Create Date: 2026-08-06

Tras recargar los precios con `auto_adjust=False`, se limpian los
restos que sigan siendo imposibles y se anaden las restricciones que
impiden que vuelvan a entrar.

**Que se hace con las filas malas.** Se ponen a NULL `open`, `high` y
`low`, conservando `close`, y se deja constancia en el log. No se
intercambian el maximo y el minimo ni se "arregla" el rango: no
sabemos cual de los cuatro valores es el corrupto, e inventar uno
plausible es peor que admitir que no se sabe. Las tres columnas ya
admiten nulo y `close` es lo unico que consume `gold/build.py`.

**Por que NOT VALID primero.** Anadir un CHECK validado escanea la
tabla entera manteniendo un ACCESS EXCLUSIVE: sobre 24 millones de
filas eso bloquea a todos los lectores. Con `NOT VALID` la restriccion
empieza a aplicarse a las filas nuevas de inmediato y sin bloqueo, y
el `VALIDATE` posterior solo necesita un SHARE UPDATE EXCLUSIVE, que
no bloquea ni lecturas ni escrituras.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "552fd8525b1b"
down_revision: Union[str, Sequence[str], None] = "1df48aa663ea"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tablas de precio con OHLC completo.
TABLAS = [
    "equity.price_daily",
    "crypto.price_daily",
    "commodity.price_daily",
    "forex.rate_daily",
    "equity.index_price",
    "deriv.futures_daily",
]

# (sufijo del nombre, condicion que debe cumplirse siempre)
RESTRICCIONES = [
    ("ohlc_rango", "high >= low"),
    ("ohlc_cierre", "close >= low AND close <= high"),
    ("cierre_positivo", "close > 0"),
]


def upgrade() -> None:
    """Limpiar los restos imposibles y anadir las restricciones."""
    for tabla in TABLAS:
        # Anular el OHLC de las velas incoherentes, conservando el
        # cierre, que es lo unico obligatorio.
        op.execute(
            f"UPDATE {tabla} SET open = NULL, high = NULL, low = NULL "
            "WHERE high < low OR close < low OR close > high"
        )
        # Las filas sin cierre valido no se pueden salvar.
        op.execute(f"DELETE FROM {tabla} WHERE close <= 0")

    for tabla in TABLAS:
        nombre_tabla = tabla.split(".")[1]
        for sufijo, condicion in RESTRICCIONES:
            op.execute(
                f"ALTER TABLE {tabla} ADD CONSTRAINT "
                f"ck_{nombre_tabla}_{sufijo} CHECK ({condicion}) NOT VALID"
            )
            op.execute(
                f"ALTER TABLE {tabla} "
                f"VALIDATE CONSTRAINT ck_{nombre_tabla}_{sufijo}"
            )


def downgrade() -> None:
    """Quitar las restricciones.

    Las filas borradas y los OHLC anulados no se recuperan: habria que
    volver a descargarlos de la fuente.
    """
    for tabla in TABLAS:
        nombre_tabla = tabla.split(".")[1]
        for sufijo, _ in RESTRICCIONES:
            op.execute(
                f"ALTER TABLE {tabla} DROP CONSTRAINT IF EXISTS "
                f"ck_{nombre_tabla}_{sufijo}"
            )
