"""moneda de reporte de las cotizadas estadounidenses

Revision ID: a5b6c7d8e9f0
Revises: f4a5b6c7d8e9
Create Date: 2026-08-07

La migracion anterior recupero la moneda de reporte de
`bronze.yf_profile`, pero 1.478 empresas no tienen perfil guardado y
se quedaron sin ella, y sin moneda no hay ratio: `equity.ratios_mv`
devuelve NULL antes que mezclar unidades.

De esas, 1.470 son cotizadas estadounidenses sin sufijo de mercado y
con `country_code = 'USA'`. Ahi el dolar no es una suposicion comoda:
una empresa constituida y cotizada en Estados Unidos presenta sus
cuentas en dolares.

Lo que NO se toca son los ADR —cotizan sin sufijo en Estados Unidos
pero su pais es otro y reportan en su moneda—, que son justamente los
que provocaron el defecto: Central Puerto cotiza en dolares y reporta
en pesos. Por eso la condicion exige el pais, no solo el mercado.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a5b6c7d8e9f0"
down_revision: Union[str, Sequence[str], None] = "f4a5b6c7d8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLAS = (
    "equity.income_statement",
    "equity.balance_sheet",
    "equity.cash_flow",
)


def upgrade() -> None:
    """Marcar en dolares las cuentas de las estadounidenses."""
    for tabla in _TABLAS:
        op.execute(
            f"""
            UPDATE {tabla} e
            SET currency_code = 'USD'
            FROM equity.company c
            WHERE c.id = e.company_id
              AND e.currency_code IS NULL
              AND c.country_code = 'USA'
              AND c.ticker !~ '\\.'
            """
        )


def downgrade() -> None:
    """No se puede distinguir estas de las que ya venian de bronze."""
    pass
