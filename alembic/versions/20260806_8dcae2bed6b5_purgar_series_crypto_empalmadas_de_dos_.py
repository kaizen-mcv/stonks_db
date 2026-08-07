"""purgar series crypto empalmadas de dos activos distintos

Revision ID: 8dcae2bed6b5
Revises: 81c55f8f31d8
Create Date: 2026-08-06

Cuatro `coin_id` contenian dos activos distintos empalmados: un bloque
antiguo de valores minusculos y, tras un hueco de meses o anos, el
bloque real de la moneda.

Verificado contra CoinGecko (rango del ultimo ano, que es lo que da el
plan gratuito):

| Simbolo | Real ultimo ano | Bloque ajeno                  |
|---------|-----------------|-------------------------------|
| APT     | 0,55 - 5,45     | 2021-11 a 2025-06, max 0,299  |
| COMP    | 15,19 - 55,38   | 2018-08 a 2022-01, max 0,0033 |
| GTC     | 0,066 - 0,449   | 2026-01-27, 0,000003          |
| SUI     | 0,68 - 4,01     | 2022-03 a 2024-06, max 0,019  |

Ademas de la diferencia de magnitud (de 4.789x a 17 millones de veces),
los bloques ajenos son anteriores al lanzamiento de cada moneda:
Compound salio en junio de 2020, Aptos en octubre de 2022, Gitcoin en
mayo de 2021 y Sui en mayo de 2023. Ningun dato previo puede ser suyo.

Se borra el bloque ajeno y se conserva el bueno. El historico correcto
no se puede recuperar: la API gratuita de CoinGecko solo sirve 365
dias.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8dcae2bed6b5"
down_revision: Union[str, Sequence[str], None] = "81c55f8f31d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (simbolo, primera fecha que si pertenece a la moneda)
CORTES = [
    ("APT", "2026-07-05"),
    ("COMP", "2026-07-05"),
    ("GTC", "2026-07-06"),
    ("SUI", "2025-04-21"),
]


def upgrade() -> None:
    """Borrar los bloques que pertenecen a otro activo."""
    for simbolo, corte in CORTES:
        op.execute(
            "DELETE FROM crypto.price_daily p "
            "USING crypto.coin c "
            f"WHERE c.id = p.coin_id AND c.symbol = '{simbolo}' "
            f"AND p.date < DATE '{corte}'"
        )


def downgrade() -> None:
    """No reversible: los datos borrados eran de otro activo.

    Recuperarlos exigiria saber de que moneda eran, y esa informacion
    se perdio al fusionar los `coin_id`.
    """
