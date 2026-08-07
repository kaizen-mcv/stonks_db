"""valores de holders e insiders a usd

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-08-06

`equity.holder.value_usd` y `equity.insider_transaction.value_usd`
guardaban el importe en la moneda de cotizacion del valor, no en
dolares. La posicion de Vanguard en Samsung figuraba con
18.123.636.562.500, que son wones: unos 13.000 millones de dolares.

Es el tercer caso de la misma familia —`market_cap_usd` en moneda
local, `GDP_NOMINAL` etiquetado `billion_usd` con dolares absolutos,
`pct_held` como fraccion—: la columna no contenia lo que su nombre
declara.

Se convierte con el tipo de cambio vigente, que es lo correcto para
`holder` (es una foto reciente) y una aproximacion para las
operaciones de insider antiguas, donde el tipo del dia de la operacion
seria mas preciso. Se asume el vigente porque el importe historico en
moneda local se pierde al convertir y no se puede rehacer despues; lo
que importa es que la magnitud deje de estar equivocada por un factor
de mil.

Las empresas sin moneda declarada se dejan intactas: son sobre todo
cotizadas estadounidenses, ya en dolares.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f8a9b0c1d2e3"
down_revision: Union[str, Sequence[str], None] = "e7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Ultimo tipo USD/moneda, admitiendo el par guardado al reves.
# El DISTINCT ON importa: si una moneda tiene los dos pares (USDXXX y
# XXXUSD) el UPDATE ... FROM cogeria una fila cualquiera de las dos.
_TIPOS = """
    tipos_todos AS (
        SELECT p.quote_currency AS moneda, r.close AS valor
        FROM forex.rate_daily r
        JOIN forex.currency_pair p ON p.id = r.pair_id
        WHERE p.base_currency = 'USD'
          AND r.date = (
              SELECT max(r2.date) FROM forex.rate_daily r2
              WHERE r2.pair_id = r.pair_id
          )
        UNION ALL
        SELECT p.base_currency, 1.0 / r.close
        FROM forex.rate_daily r
        JOIN forex.currency_pair p ON p.id = r.pair_id
        WHERE p.quote_currency = 'USD' AND r.close > 0
          AND r.date = (
              SELECT max(r2.date) FROM forex.rate_daily r2
              WHERE r2.pair_id = r.pair_id
          )
    ),
    tipo AS (
        SELECT DISTINCT ON (moneda) moneda, valor
        FROM tipos_todos WHERE valor > 0 ORDER BY moneda, valor
    )
"""


def upgrade() -> None:
    """Convertir a dolares los importes en moneda local."""
    for tabla in ("equity.holder", "equity.insider_transaction"):
        op.execute(
            f"""
            WITH {_TIPOS}
            UPDATE {tabla} h
            SET value_usd = h.value_usd / t.valor
            FROM equity.company c, tipo t
            WHERE c.id = h.company_id
              AND c.currency_code = t.moneda
              AND c.currency_code <> 'USD'
              AND h.value_usd IS NOT NULL
            """
        )

    # Sin tipo de cambio no se puede convertir, y dejar el importe en
    # moneda local bajo un nombre que dice USD es justo el defecto que
    # esta migracion corrige.
    for tabla in ("equity.holder", "equity.insider_transaction"):
        op.execute(
            f"""
            WITH {_TIPOS}
            UPDATE {tabla} h
            SET value_usd = NULL
            FROM equity.company c
            WHERE c.id = h.company_id
              AND c.currency_code IS NOT NULL
              AND c.currency_code <> 'USD'
              AND h.value_usd IS NOT NULL
              AND c.currency_code NOT IN (SELECT moneda FROM tipo)
            """
        )


def downgrade() -> None:
    """No se puede deshacer.

    La conversion pierde el importe original en moneda local y los
    puestos a NULL no se pueden recuperar. Se rehacen relanzando
    `EquityDeepFetcher`.
    """
    pass
