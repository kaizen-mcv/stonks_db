"""moneda de cotizacion de las de nueva york y nasdaq

Revision ID: b6c7d8e9f0a1
Revises: a5b6c7d8e9f0
Create Date: 2026-08-07

`equity.company.currency_code` estaba a NULL en 8.544 de 11.012
empresas. Durante mucho tiempo dio igual, pero desde que los ratios se
calculan en dolares hace falta saber en que moneda cotiza cada valor:
sin ella, `equity.ratios_mv` devuelve NULL antes que dividir un precio
entre un beneficio expresado en otra moneda.

De las 8.045 sin sufijo de mercado, 5.869 estan en NASDAQ (XNAS) y
2.176 en NYSE (XNYS). Las dos cotizan exclusivamente en dolares, sin
excepciones: tambien los ADR, que cotizan en dolares aunque presenten
sus cuentas en otra moneda. Ahi no hay nada que deducir.

El hueco venia de que `fetch_company_info` solo fijaba la moneda al
crear la empresa; la rama de actualizacion no la tocaba, y eso se
corrigio en la auditoria de fiabilidad. Esta migracion cierra el
historico que quedo de antes.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b6c7d8e9f0a1"
down_revision: Union[str, Sequence[str], None] = "a5b6c7d8e9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Fijar el dolar en las cotizadas de NYSE y NASDAQ."""
    op.execute(
        """
        UPDATE equity.company c
        SET currency_code = 'USD'
        FROM ref.exchange e
        WHERE e.id = c.exchange_id
          AND c.currency_code IS NULL
          AND e.mic IN ('XNAS', 'XNYS')
        """
    )


def downgrade() -> None:
    """No se puede distinguir estas de las que ya tenian la moneda."""
    pass
