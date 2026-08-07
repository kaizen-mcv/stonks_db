"""corregir y normalizar unidades de macro.indicator

Revision ID: 9c02eb906bdd
Revises: f216205f1991
Create Date: 2026-08-06

Dos problemas distintos con `macro.indicator.unit`.

**1. Etiquetas que mienten.** `GDP_NOMINAL` declaraba `billion_usd`
pero sus valores estan en dolares absolutos: la mediana es 8,2e9, es
decir 8.200 millones de dolares, no 8.200 millones de miles de
millones. Lo mismo con `GDP_PPP` y `billion_intl_usd`. Quien confiara
en la etiqueta se equivocaba por un factor de mil millones.

Se corrige la etiqueta, no el dato: los valores en dolares absolutos
son los que devuelve el World Bank, los que consume
`gold.mart_country_year.gdp_usd` y los que se han verificado como
correctos (EE.UU. 2023 = 27,81 billones frente a los 27,72 reales).
Reescalar 18.723 observaciones romperia la capa gold y perderia
precision.

Comprobado que los indicadores del FMI SI son correctos y no se tocan:
`IMF_NGDPD` en "Billions of U.S. dollars" tiene mediana 37, e
`IMF_GDP` en "Millions of US Dollars" tiene mediana 17.000.

**2. Vocabulario disperso.** 32 etiquetas distintas para un punado de
conceptos: "percent", "Percent" y "%" conviven, igual que "Percent of
GDP" y "% of GDP". Se normalizan los sinonimos inequivocos y se dejan
tal cual los que llevan informacion propia (la base de un indice, o la
diferencia entre toneladas y megatoneladas).

Los 1.670 indicadores sin unidad se quedan sin unidad: inventarsela
seria peor que no tenerla. Los reporta el check de completitud de
metadatos.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c02eb906bdd"
down_revision: Union[str, Sequence[str], None] = "f216205f1991"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Etiquetas que no describian la magnitud real de los datos.
CORRECCIONES = [
    ("GDP_NOMINAL", "billion_usd", "usd"),
    ("GDP_PPP", "billion_intl_usd", "intl_usd"),
]

# Sinonimos que se unifican. Solo los inequivocos: no se tocan las
# etiquetas que llevan informacion propia, como la base de un indice
# ("Index, 2010 = 100") o la escala de una tonelada ("Mt" y "t" no son
# lo mismo).
NORMALIZACION = [
    (["percent", "Percent", "%"], "pct"),
    (["Percent of GDP", "% of GDP"], "pct_gdp"),
    (["% of Potential GDP"], "pct_potential_gdp"),
    (["Percent of World"], "pct_world"),
    (
        ["Annual percent change", "Annual average percent change"],
        "pct_change_yoy",
    ),
    (["Units", "Unit"], "units"),
    (["Millions of US Dollars"], "usd_millions"),
    (["Billions of U.S. dollars"], "usd_billions"),
    (["Millions of people"], "people_millions"),
    (["U.S. dollars per capita"], "usd_per_capita"),
    (
        ["Index, 2010 = 100", "Annual Average Index, 2010 = 100"],
        "index_2010_100",
    ),
    (["Index"], "index"),
    (["Mt CO2e"], "mt_co2e"),
]


def upgrade() -> None:
    """Corregir las etiquetas falsas y unificar sinonimos."""
    for codigo, _viejo, nuevo in CORRECCIONES:
        op.execute(
            "UPDATE macro.indicator "
            f"SET unit = '{nuevo}' WHERE code = '{codigo}'"
        )

    for variantes, canonica in NORMALIZACION:
        lista = ", ".join(f"'{v}'" for v in variantes)
        op.execute(
            "UPDATE macro.indicator "
            f"SET unit = '{canonica}' WHERE unit IN ({lista})"
        )


def downgrade() -> None:
    """Restaurar las etiquetas originales.

    La normalizacion solo se revierte a la primera variante de cada
    grupo: los sinonimos originales por indicador no se guardaron.
    """
    for variantes, canonica in NORMALIZACION:
        op.execute(
            "UPDATE macro.indicator "
            f"SET unit = '{variantes[0]}' WHERE unit = '{canonica}'"
        )

    for codigo, viejo, _nuevo in CORRECCIONES:
        op.execute(
            "UPDATE macro.indicator "
            f"SET unit = '{viejo}' WHERE code = '{codigo}'"
        )
