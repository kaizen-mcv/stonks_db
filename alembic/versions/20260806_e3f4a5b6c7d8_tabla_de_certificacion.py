"""tabla de certificacion de tablas

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-08-06

`meta.table_certification` guarda, por cada tabla de datos, como se ha
verificado: contrastada contra una cifra publicada fuera del proyecto,
coherente sin referencia externa, no verificable con su motivo, o sin
certificar.

Ese ultimo estado es el que da valor a la tabla: un test falla si
alguna tabla lo tiene, asi que no se puede anadir una tabla nueva sin
declarar como se comprueba.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, Sequence[str], None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crear la tabla de certificacion."""
    op.create_table(
        "table_certification",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("schema_name", sa.String(63), nullable=False),
        sa.Column("table_name", sa.String(63), nullable=False),
        sa.Column("estado", sa.String(40), nullable=False),
        sa.Column("metodo", sa.String(500), nullable=True),
        sa.Column("motivo", sa.String(500), nullable=True),
        sa.Column("filas", sa.BigInteger(), nullable=True),
        sa.Column("referencias", sa.Integer(), nullable=True),
        sa.Column("certificado_por", sa.String(60), nullable=True),
        sa.Column(
            "certified_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("schema_name", "table_name"),
        schema="meta",
    )


def downgrade() -> None:
    """Quitar la tabla."""
    op.drop_table("table_certification", schema="meta")
