"""baseline esquema v0.3 existente

Revision ID: bde127ede9f5
Revises:
Create Date: 2026-08-03

Punto de partida del control de versiones del esquema. No hace nada:
representa la base de datos tal y como estaba antes de introducir
Alembic (creada historicamente con Base.metadata.create_all).

Para una base de datos vacia, el esquema completo se levanta con
`stonks db init` y despues `alembic stamp head`.
"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "bde127ede9f5"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Baseline: el esquema ya existe."""


def downgrade() -> None:
    """Baseline: no hay nada que revertir."""
