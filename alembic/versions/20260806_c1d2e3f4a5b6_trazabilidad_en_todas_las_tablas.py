"""trazabilidad source_id y fetch_run_id en todas las tablas

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
Create Date: 2026-08-06

De 68 tablas de datos, 25 tenian `source_id` y solo 5 `fetch_run_id`.
Sin esas dos columnas no se puede responder a "¿quien escribio esta
fila y en que ejecucion?", que es la pregunta con la que empieza
cualquier investigacion cuando un dato sale raro.

`source_id` se rellena hacia atras donde se puede deducir: la mayoria
de las tablas las escribe un unico fetcher, y en `macro.series` se
saca de los propios datos.

`fetch_run_id` NO se puede rellenar hacia atras —esa informacion nunca
se guardo—, asi que las filas existentes quedan a NULL para siempre y
solo lo llevan las nuevas. Es un corte consciente, no un descuido.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "b0c1d2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tabla -> fuente que la escribe, deducida de que fetcher importa cada
# modelo. `None` significa que la escriben varias y hay que resolverlo
# fila a fila o dejarlo sin rellenar.
_TABLAS = {
    "equity.shares_history": "yfinance",
    "equity.upgrade_downgrade": "yfinance",
    "equity.index_price": "yfinance",
    "equity.insider_transaction": "yfinance",
    "equity.earnings_date": "yfinance",
    "equity.dividend": "yfinance",
    "equity.holder": "yfinance",
    "equity.recommendation_trend": "yfinance",
    "equity.company": "yfinance",
    "equity.split": "yfinance",
    "equity.market_index": "yfinance",
    "fund.nav_daily": "yfinance",
    "fund.fund": "yfinance",
    "deriv.option_snapshot": "yfinance",
    "deriv.futures_contract": "yfinance",
    "deriv.volatility_index": "yfinance",
    "crypto.price_daily": "coingecko",
    "crypto.coin": "coingecko",
    "crypto.market_dominance": "coingecko",
    "calendar.release_date": "fred",
    "macro.data_point_vintage": "fred",
    "realestate.price_index_value": "fred",
    "fi.credit_rating": "treasury_fiscal",
    "fi.bond_issuer": "treasury_fiscal",
    "country.demographics": "world_bank",
    "country.profile": "world_bank",
    "country.tax_rate": "damodaran",
    "deriv.cot_contract": "cftc_cot",
    # Escritas por mas de un fetcher: la columna se anade igual, pero
    # el relleno hacia atras no es deducible de una tabla estatica.
    "macro.series": None,
    "macro.indicator": None,
    "alt.sentiment_value": None,
    "alt.sentiment_indicator": None,
    "fi.bond": None,
    "forex.currency_pair": None,
    "commodity.commodity": None,
    "gold.dim_date": None,
    "gold.dim_company": None,
    "gold.dim_country": None,
}


def upgrade() -> None:
    """Anadir las dos columnas y rellenar el origen conocido."""
    for ruta in _TABLAS:
        esquema, tabla = ruta.split(".")
        existentes = {
            c["name"]
            for c in sa.inspect(op.get_bind()).get_columns(
                tabla, schema=esquema
            )
        }
        if "source_id" not in existentes:
            op.add_column(
                tabla,
                sa.Column("source_id", sa.Integer(), nullable=True),
                schema=esquema,
            )
        if "fetch_run_id" not in existentes:
            op.add_column(
                tabla,
                sa.Column("fetch_run_id", sa.Integer(), nullable=True),
                schema=esquema,
            )

    # Relleno hacia atras de las de un solo escritor.
    for ruta, fuente in _TABLAS.items():
        if fuente is None:
            continue
        op.execute(
            f"""
            UPDATE {ruta}
            SET source_id = (
                SELECT id FROM meta.data_source WHERE name = '{fuente}'
            )
            WHERE source_id IS NULL
            """
        )

    # `macro.series` no tiene un unico escritor, pero sus datos si
    # llevan `source_id`: se toma el de la fuente que mas puntos ha
    # escrito en esa serie.
    op.execute(
        """
        WITH dominante AS (
            SELECT DISTINCT ON (series_id) series_id, source_id
            FROM (
                SELECT series_id, source_id, count(*) AS n
                FROM macro.data_point
                WHERE source_id IS NOT NULL
                GROUP BY series_id, source_id
            ) c
            ORDER BY series_id, n DESC
        )
        UPDATE macro.series s
        SET source_id = d.source_id
        FROM dominante d
        WHERE d.series_id = s.id AND s.source_id IS NULL
        """
    )

    # `macro.indicator` ya tiene su propia tabla de enlace con las
    # fuentes; se toma la primera declarada.
    op.execute(
        """
        WITH primera AS (
            SELECT DISTINCT ON (indicator_id) indicator_id, source_id
            FROM macro.indicator_source ORDER BY indicator_id, id
        )
        UPDATE macro.indicator i
        SET source_id = p.source_id
        FROM primera p
        WHERE p.indicator_id = i.id AND i.source_id IS NULL
        """
    )


def downgrade() -> None:
    """Quitar las columnas anadidas.

    Con IF EXISTS porque la subida se salta las tablas que ya tenian
    alguna de las dos columnas y aqui no se sabe cuales eran.
    """
    for ruta in _TABLAS:
        for columna in ("source_id", "fetch_run_id"):
            op.execute(f"ALTER TABLE {ruta} DROP COLUMN IF EXISTS {columna}")
