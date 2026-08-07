"""volumen a bigint en fondos y futuros

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
Create Date: 2026-08-06

`fund.nav_daily.volume` era INTEGER y desbordaba: SPY negocio
2.174.492.800 participaciones el 10/10/2008, por encima del limite de
2.147.483.647. La recarga de los 496 fondos fallaba en esa fila y
perdia el resto de la serie de ese fondo.

`deriv.futures_daily.volume` tiene el mismo tipo y el mismo riesgo
—hoy su maximo es de 6,5 millones, pero no hay razon para dejar la
trampa puesta—.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b0c1d2e3f4a5"
down_revision: Union[str, Sequence[str], None] = "a9b0c1d2e3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Ampliar el volumen a 64 bits."""
    op.alter_column(
        "nav_daily",
        "volume",
        type_=sa.BigInteger(),
        existing_type=sa.Integer(),
        schema="fund",
    )
    op.alter_column(
        "futures_daily",
        "volume",
        type_=sa.BigInteger(),
        existing_type=sa.Integer(),
        schema="deriv",
    )


def downgrade() -> None:
    """Volver a 32 bits (perderia los volumenes grandes)."""
    op.alter_column(
        "nav_daily",
        "volume",
        type_=sa.Integer(),
        existing_type=sa.BigInteger(),
        schema="fund",
    )
    op.alter_column(
        "futures_daily",
        "volume",
        type_=sa.Integer(),
        existing_type=sa.BigInteger(),
        schema="deriv",
    )
