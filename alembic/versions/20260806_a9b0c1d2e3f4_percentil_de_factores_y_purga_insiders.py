"""percentil de factores a 0-100 y purga de insiders imposibles

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-08-06

Dos arreglos que salieron del check nuevo de unidades de columna.

1. `gold.fact_factor_scores.percentile` venia de
   `pandas.rank(pct=True)`, que devuelve 0-1. La columna se llama
   percentil y el resto del proyecto expresa los porcentajes en 0-100.

2. `equity.insider_transaction.value_usd` tenia importes imposibles:
   una operacion de HYEX figuraba con 307 billones de dolares, un
   precio implicito de 23,5 millones por accion cuando el valor cotiza
   por debajo de 1,40. Son datos basura de Yahoo en cotizadas OTC.

   El umbral es 100 veces el precio de mercado del dia. Un precio
   implicito POR DEBAJO del de mercado es normal —las opciones se
   ejercen a un strike inferior—, pero cien veces por encima no
   corresponde a ninguna convencion: es basura de la fuente. Solo
   afecta a 12 filas de 166.365.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a9b0c1d2e3f4"
down_revision: Union[str, Sequence[str], None] = "f8a9b0c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Multiplo del precio de mercado por encima del cual el importe de una
# operacion de insider no puede ser real.
FACTOR_IMPOSIBLE = 100


def upgrade() -> None:
    """Normalizar el percentil y purgar los importes imposibles."""
    # NUMERIC(6,4) solo deja dos digitos enteros: el percentil 100 no
    # cabe. Se amplia a tres antes de multiplicar.
    op.execute(
        "ALTER TABLE gold.fact_factor_scores "
        "ALTER COLUMN percentile TYPE numeric(7, 4)"
    )
    op.execute(
        """
        DO $$
        DECLARE maximo numeric;
        BEGIN
            SELECT max(percentile) INTO maximo
            FROM gold.fact_factor_scores;
            IF maximo > 1 THEN
                RAISE NOTICE
                    'percentile ya llega a %, se deja como esta', maximo;
            ELSE
                UPDATE gold.fact_factor_scores
                SET percentile = percentile * 100
                WHERE percentile IS NOT NULL;
            END IF;
        END $$;
        """
    )

    op.execute(
        f"""
        WITH implicito AS (
            SELECT i.id,
                   i.value_usd / nullif(i.shares, 0) AS precio,
                   (SELECT p.close FROM equity.price_daily p
                     WHERE p.company_id = i.company_id
                       AND p.date <= i.start_date
                     ORDER BY p.date DESC LIMIT 1) AS mercado
            FROM equity.insider_transaction i
            WHERE i.value_usd IS NOT NULL AND i.shares > 0
        )
        UPDATE equity.insider_transaction i
        SET value_usd = NULL
        FROM implicito m
        WHERE m.id = i.id
          AND m.mercado > 0
          AND m.precio > m.mercado * {FACTOR_IMPOSIBLE}
        """
    )


def downgrade() -> None:
    """Devolver el percentil a 0-1. Los importes purgados no vuelven."""
    op.execute(
        """
        UPDATE gold.fact_factor_scores
        SET percentile = percentile / 100
        WHERE percentile IS NOT NULL AND percentile > 1
        """
    )
