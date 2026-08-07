"""market_cap: cubrir las monedas con par invertido

Revision ID: c3d4e5f6a7b8
Revises: b7c8d9e0f1a2
Create Date: 2026-08-06

La conversion anterior solo miraba pares con `base_currency = 'USD'`.
El euro y el dolar australiano se cotizan al reves (EURUSD, AUDUSD),
asi que sus capitalizaciones quedaron a NULL en vez de convertidas.
Aqui se aplica el reciproco.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convertir las monedas cuyo par esta guardado al reves.

    Solo afecta a las filas que la migracion anterior dejo a NULL, asi
    que hay que recuperar el importe original del fetcher. Como no se
    guardo, se marcan para que la proxima pasada del fetcher las
    rellene ya convertidas.
    """
    # Sin el importe original no se puede reconstruir: se deja
    # constancia en meta.data_quality para que el check de cobertura
    # lo reporte hasta que el fetcher las repase.
    op.execute(
        """
        INSERT INTO meta.data_quality
            (domain, entity_type, entity_id, completeness_score,
             source_count, last_assessed)
        SELECT 'equity', 'market_cap_pendiente', c.currency_code,
               0, count(*), now()
        FROM equity.company c
        WHERE c.currency_code IN ('EUR', 'AUD')
          AND c.market_cap_usd IS NULL
        GROUP BY c.currency_code
        """
    )


def downgrade() -> None:
    """Quitar las anotaciones de calidad."""
    op.execute(
        "DELETE FROM meta.data_quality "
        "WHERE entity_type = 'market_cap_pendiente'"
    )
