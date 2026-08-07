"""moneda real de los estados financieros

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-08-07

`equity.income_statement.currency_code` y sus hermanas de balance y
flujos guardaban la moneda de COTIZACION, no la de reporte: el fetcher
escribia `currency_code=comp.currency_code`.

No son lo mismo, y la diferencia rompe cualquier ratio que divida un
precio entre una magnitud contable:

- Central Puerto cotiza en dolares y reporta en pesos argentinos: su
  PER salia 0,006.
- Novo Nordisk reporta en coronas danesas; su ADR cotiza en dolares y
  daba PER 2,0, mientras la accion de Copenhague daba 12,7 con el
  mismo beneficio por accion.
- Booking declaraba 1,25 con un PER implicito de 28,8.

Son 620 de 2.285 PER no comparables, y salen los primeros al ordenar
por PER: justo donde uno busca gangas.

El dato correcto nunca se perdio: Yahoo lo devuelve en
`financialCurrency` y el perfil completo se guarda en
`bronze.yf_profile`. Se recupera de ahi.

Lo que no se puede recuperar se deja a NULL en vez de repetir la
moneda de cotizacion: es preferible no saber la unidad a declarar una
equivocada.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4a5b6c7d8e9"
down_revision: Union[str, Sequence[str], None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLAS = (
    "equity.income_statement",
    "equity.balance_sheet",
    "equity.cash_flow",
)


def upgrade() -> None:
    """Reetiquetar los estados con su moneda de reporte."""
    for tabla in _TABLAS:
        # Primero se borra lo que hay: lo que estaba escrito era la
        # moneda equivocada, no un dato parcial que convenga conservar.
        op.execute(f"UPDATE {tabla} SET currency_code = NULL")
        op.execute(
            f"""
            WITH financiera AS (
                SELECT DISTINCT ON (ticker)
                       ticker,
                       payload->>'financialCurrency' AS moneda
                FROM bronze.yf_profile
                WHERE payload->>'financialCurrency' IS NOT NULL
                ORDER BY ticker, snapshot_date DESC
            )
            UPDATE {tabla} e
            SET currency_code = left(f.moneda, 3)
            FROM equity.company c
            JOIN financiera f ON f.ticker = c.ticker
            WHERE c.id = e.company_id
            """
        )


def downgrade() -> None:
    """Volver a etiquetar con la moneda de cotizacion.

    Se restaura el estado anterior aunque fuera incorrecto, que es lo
    que un downgrade debe hacer.
    """
    for tabla in _TABLAS:
        op.execute(
            f"""
            UPDATE {tabla} e
            SET currency_code = c.currency_code
            FROM equity.company c
            WHERE c.id = e.company_id
            """
        )
