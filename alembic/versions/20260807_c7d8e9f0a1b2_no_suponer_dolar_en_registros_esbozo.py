"""no suponer dolar en registros esbozo

Revision ID: c7d8e9f0a1b2
Revises: b6c7d8e9f0a1
Create Date: 2026-08-07

Correccion de la migracion a5b6c7d8e9f0, que marco en dolares las
cuentas de las cotizadas con `country_code = 'USA'` y sin sufijo de
mercado.

La condicion era demasiado permisiva. Hay 2.213 empresas cuyo registro
nunca se completo —`name` sigue siendo el propio ticker porque
`fetch_company_info` no llego a ejecutarse— y a las que se les puso
'USA' por defecto. Entre ellas hay ADR que reportan en otra moneda:

- Grupo Aval (AVAL) reporta en pesos colombianos: PER 0,004.
- Kaspi.kz (KSPI) en tenges: PER 0,016.
- Canon (CAJPY) en yenes: PER 0,077.
- Loma Negra (LOMA) en pesos argentinos: PER 0,055.

Justo el defecto que se estaba arreglando, reintroducido por la
correccion. Se revierte a NULL en los registros esbozo: sin perfil
descargado no hay evidencia de donde esta la empresa, y una unidad
supuesta vale menos que ninguna.

Se conserva el dolar en las 1.484 empresas con perfil completo y pais
Estados Unidos, donde si es una deduccion y no una suposicion.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, Sequence[str], None] = "b6c7d8e9f0a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLAS = (
    "equity.income_statement",
    "equity.balance_sheet",
    "equity.cash_flow",
)


def upgrade() -> None:
    """Quitar el dolar supuesto de los registros sin perfil."""
    for tabla in _TABLAS:
        op.execute(
            f"""
            UPDATE {tabla} e
            SET currency_code = NULL
            FROM equity.company c
            WHERE c.id = e.company_id
              AND e.currency_code = 'USD'
              AND c.name = c.ticker
              AND NOT EXISTS (
                  SELECT 1 FROM bronze.yf_profile b
                  WHERE b.ticker = c.ticker
                    AND b.payload->>'financialCurrency' IS NOT NULL
              )
            """
        )


def downgrade() -> None:
    """No se puede: se perderia que fueron un valor supuesto."""
    pass
