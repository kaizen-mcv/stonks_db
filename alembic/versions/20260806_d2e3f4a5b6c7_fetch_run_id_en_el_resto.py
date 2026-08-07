"""fetch_run_id en el resto de tablas de datos

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-08-06

La migracion anterior dejo `source_id` en 63 de 68 tablas, pero
`fetch_run_id` solo en 43: faltaban justo las que ya tenian origen
declarado y ninguna forma de saber en que ejecucion se escribio cada
fila.

Anadir una columna sin valor por defecto es una operacion de metadatos
en PostgreSQL 11 en adelante, asi que las dos tablas grandes
—`gold.fact_fundamentals_pit` con 33,2 M de filas y
`equity.price_daily` con 28,8 M— no se reescriben.

A las cinco tablas de `bronze` les falta `source_id`, pero no se anade:
ya llevan `fetch_run_id`, y `meta.fetch_run` tiene la fuente. Duplicar
la columna solo abriria la puerta a que las dos discrepen.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, Sequence[str], None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLAS = [
    "gold.fact_fundamentals_pit",
    "equity.price_daily",
    "macro.data_point",
    "agri.production",
    "trade.flow",
    "forex.rate_daily",
    "deriv.cot_report",
    "equity.earnings_revision",
    "equity.analyst_estimate",
    "commodity.price_daily",
    "energy.balance",
    "gold.fact_factor_scores",
    "deriv.futures_daily",
    "fi.yield_curve",
    "deriv.volatility_daily",
    "equity.balance_sheet",
    "equity.cash_flow",
    "equity.income_statement",
    "equity.factor_return",
    "macro.indicator_source",
    "equity.index_constituent_current",
    "gold.index_membership",
    "calendar.release",
    "fi.country_risk_premium",
    "realestate.price_index",
]


def upgrade() -> None:
    """Anadir `fetch_run_id` donde falta."""
    for ruta in _TABLAS:
        esquema, tabla = ruta.split(".")
        op.add_column(
            tabla,
            sa.Column("fetch_run_id", sa.Integer(), nullable=True),
            schema=esquema,
        )

    # Los indicadores de FRED no tienen fila en
    # `macro.indicator_source`, asi que el relleno anterior los dejo
    # sin origen. El fetcher les pone la categoria 'FRED', salvo los
    # de bonos e inmobiliario, que van con la suya; esos se resuelven
    # por su codigo, comprobado contra FRED_SERIES.
    op.execute(
        """
        UPDATE macro.indicator
        SET source_id = (
            SELECT id FROM meta.data_source WHERE name = 'fred'
        )
        WHERE source_id IS NULL
          AND (category = 'FRED'
               OR code LIKE 'BOND\\_%'
               OR code LIKE 'HPI\\_%'
               OR code IN ('HOME_MEDIAN_PRICE', 'HOMEOWNERSHIP_RATE'))
        """
    )


def downgrade() -> None:
    """Quitar la columna anadida."""
    for ruta in _TABLAS:
        op.execute(f"ALTER TABLE {ruta} DROP COLUMN IF EXISTS fetch_run_id")
