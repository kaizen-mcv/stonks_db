"""pct_held de fraccion a porcentaje

Revision ID: e7f8a9b0c1d2
Revises: d5e6f7a8b9c0
Create Date: 2026-08-06

`equity.holder.pct_held` guardaba una fraccion, no un porcentaje:
yfinance devuelve `pctHeld` como 0,0847 y el fetcher lo escribia tal
cual bajo un nombre que promete porcentaje. BlackRock aparecia con
0,08 en Apple en vez de 8,47.

Sobre las 74.847 filas el maximo era 0,9643 y ninguna pasaba de 1, asi
que la conversion es segura: si alguna superase 1 seria senal de que ya
esta en porcentaje y se estaria multiplicando dos veces.

Es la misma familia de defecto que `market_cap_usd` en moneda local
(b7c8d9e0f1a2) y que `GDP_NOMINAL` etiquetado en `billion_usd` con los
valores en dolares absolutos: la columna no contiene lo que su nombre
declara.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, Sequence[str], None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Pasar las fracciones a porcentaje."""
    # No se puede filtrar por `<= 1` para hacerla idempotente: una
    # participacion legitima del 0,5 % vale 0,5 despues de convertir y
    # se volveria a multiplicar. En su lugar se comprueba la premisa
    # (nada por encima de 1) y se aborta si no se cumple, que es lo que
    # pasaria si la migracion ya hubiese corrido.
    op.execute(
        """
        DO $$
        DECLARE maximo numeric;
        BEGIN
            SELECT max(pct_held) INTO maximo FROM equity.holder;
            IF maximo > 1 THEN
                RAISE EXCEPTION
                    'pct_held ya llega a %, parece porcentaje: '
                    'la conversion se ha hecho ya', maximo;
            END IF;
            UPDATE equity.holder
            SET pct_held = pct_held * 100
            WHERE pct_held IS NOT NULL;
        END $$;
        """
    )


def downgrade() -> None:
    """Devolver los porcentajes a fraccion."""
    op.execute(
        """
        UPDATE equity.holder
        SET pct_held = pct_held / 100
        WHERE pct_held IS NOT NULL AND pct_held > 1
        """
    )
