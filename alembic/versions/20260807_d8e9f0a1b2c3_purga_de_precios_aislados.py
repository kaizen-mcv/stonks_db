"""purga de precios aislados

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-08-07

`gold.mart_benchmark_returns` tenia retornos diarios imposibles en la
serie equiponderada; el peor, un +2.539 % el 2012-04-03. Compuestos dan
un indice de 10 elevado a 50.

No era un fallo del mart sino de los precios. Titanium Metals cotizaba
sobre 10.000 toda esa semana y el 2012-04-02 aparece con un OHLC plano
de 1,40 y volumen cero; al dia siguiente vuelve a 10.100. TNB alterna
entre 28.000 y 1,44 nada menos que 599 veces.

Se purgan las velas aisladas: un cierre diez veces por encima o por
debajo del dia anterior Y del siguiente. Ninguna es un movimiento real
—no existe un valor que caiga un 90 % y lo recupere entero al dia
siguiente— y todas envenenan cualquier serie de retornos que las
atraviese.

Son 2.002 filas de 28,9 millones (el 0,007 %) repartidas en 128
empresas, ocho de las cuales concentran la mitad.

El criterio no mira el volumen a proposito: 946 de las velas lo tienen
a cero, pero Banco Santander Chile marca 1.989 entre 20,3 y 20,4 con
14,7 millones de titulos negociados. Lo que delata el artefacto es la
forma, no el volumen.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d8e9f0a1b2c3"
down_revision: Union[str, Sequence[str], None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Multiplo respecto a los dos vecinos por encima del cual la vela no
# puede ser real. Diez es holgado: ni una suspension de cotizacion ni
# un desplome producen una V de ese tamano en un dia.
FACTOR_AISLADO = 10


def upgrade() -> None:
    """Borrar las velas aisladas."""
    op.execute(
        f"""
        WITH vecinos AS (
            SELECT id, close,
                   lag(close) OVER (
                       PARTITION BY company_id ORDER BY date) AS anterior,
                   lead(close) OVER (
                       PARTITION BY company_id ORDER BY date) AS siguiente
            FROM equity.price_daily
        )
        DELETE FROM equity.price_daily p
        USING vecinos v
        WHERE v.id = p.id
          AND v.close > 0 AND v.anterior > 0 AND v.siguiente > 0
          AND (
              (v.anterior > v.close * {FACTOR_AISLADO}
               AND v.siguiente > v.close * {FACTOR_AISLADO})
              OR
              (v.anterior * {FACTOR_AISLADO} < v.close
               AND v.siguiente * {FACTOR_AISLADO} < v.close)
          )
        """
    )


def downgrade() -> None:
    """No se puede: los precios borrados eran basura de la fuente.

    Se recuperan relanzando el fetcher, que los volvera a traer si
    siguen ahi.
    """
    pass
