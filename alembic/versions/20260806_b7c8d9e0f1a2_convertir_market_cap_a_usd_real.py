"""convertir market_cap a USD real

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-08-06

`equity.company.market_cap_usd` contenia la capitalizacion en la
moneda de cotizacion, no en dolares: yfinance devuelve `marketCap` en
moneda local y el fetcher lo guardaba tal cual bajo un nombre que
promete USD.

Toyota figuraba con 34.510.747.992.064, que son yenes; su
capitalizacion real ronda los 230.000 millones de dolares. La media de
las coreanas salia a 148.667 "miles de millones de dolares".

Afecta a unas 350 empresas de 19 monedas distintas, y contamina
`gold.mart_sector_country.avg_market_cap`, que promedia esa columna
por pais.

Se convierte con el ultimo tipo de cambio disponible en
`forex.rate_daily`. Las monedas sin par se dejan a NULL: es preferible
no tener el dato a tenerlo mintiendo sobre su unidad.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convertir a dolares las capitalizaciones en moneda local."""
    op.execute(
        """
        WITH tipo AS (
            SELECT DISTINCT ON (p.quote_currency)
                   p.quote_currency AS moneda, r.close AS cambio
            FROM forex.rate_daily r
            JOIN forex.currency_pair p ON p.id = r.pair_id
            WHERE p.base_currency = 'USD' AND r.close > 0
            ORDER BY p.quote_currency, r.date DESC
        )
        UPDATE equity.company c
        SET market_cap_usd = c.market_cap_usd / t.cambio
        FROM tipo t
        WHERE c.currency_code = t.moneda
          AND c.currency_code <> 'USD'
          AND c.market_cap_usd IS NOT NULL
        """
    )
    # Sin tipo de cambio no se puede afirmar el valor en dolares.
    op.execute(
        """
        UPDATE equity.company c
        SET market_cap_usd = NULL
        WHERE c.currency_code IS NOT NULL
          AND c.currency_code <> 'USD'
          AND c.market_cap_usd IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM forex.currency_pair p
              WHERE p.base_currency = 'USD'
                AND p.quote_currency = c.currency_code
          )
        """
    )


def downgrade() -> None:
    """No reversible.

    Deshacer la conversion exigiria el tipo de cambio exacto que se
    aplico a cada fila, y no se guardo. Volver a cargar el universo
    con el fetcher restaura los valores.
    """
