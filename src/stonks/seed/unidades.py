"""Deducir la unidad de un indicador a partir de su nombre.

De los 1.835 indicadores de `macro.indicator`, 1.670 no declaraban
unidad. No es que la unidad se perdiera al descargarla: casi siempre
viene dentro del propio nombre —"(% of GDP)", "(current US$)",
"(per 1,000 people)"— y los fetchers la ignoraban al construir el
`Indicator`. Este modulo la recupera de ahi.

La inferencia no es una heuristica frágil. Se valido contra la
magnitud observada: de los 729 indicadores cuyo nombre dice "%" y
tienen mas de 100 observaciones, 722 tienen una mediana de |valor|
dentro de 0-100. Un 99,0 % de acierto.

Lo que no se puede deducir se marca `desconocida`, nunca NULL: un NULL
no distingue "no lo sabemos" de "no lo hemos mirado".
"""

import re

from stonks.logger import get_logger

logger = get_logger("stonks.seed")

# Etiqueta para lo que no se puede deducir. Explicita a proposito.
DESCONOCIDA = "desconocida"

# Patrones ordenados de mas especifico a mas general: el primero que
# encaje gana. El orden importa —"% of GDP" tiene que probarse antes
# que "%" a secas—.
_PATRONES: list[tuple[str, str]] = [
    # ── Trampas conocidas, antes que nada ─────────────────────────
    # Nombres que llevan dentro la pista de OTRA unidad y despistan al
    # patron generico. Todas salieron de contrastar la inferencia
    # contra la magnitud observada, que es lo que las delato.
    # "Carbon intensity of GDP (kg CO2e per constant 2015 US$)" no
    # esta en dolares: son kilos por dolar.
    (r"\bintensity of GDP\b|kg CO2e per", "kg_por_usd"),
    # "Number of deaths ages 5-9 years" no se mide en anos.
    (r"^number of deaths", "units"),
    # "Military expenditure (current USD millions)" convive con
    # "(current USD)" a secas; la de millones tiene que probarse
    # primero.
    (r"USD millions|US\$ millions", "usd_millions"),
    # ── Porcentajes con denominador conocido ──────────────────────
    (r"%\s*of\s*GDP|\(%\s*GDP\)|percent of GDP|%\s*GDP", "pct_gdp"),
    (r"%\s*of\s*GNI", "pct_gni"),
    (r"annual\s*%|annual growth|%\s*change|growth rate", "pct_change_yoy"),
    (r"%\s*of\s*potential", "pct_potential_gdp"),
    (r"%\s*of\s*world", "pct_world"),
    # ── Porcentaje generico ───────────────────────────────────────
    (r"\(%[^)]*\)|\(.*\bpercent\b.*\)|\brate\b.*\(%\)|%\)", "pct"),
    (r"\bpercentage\b|\bpercent\b", "pct"),
    # ── Moneda ────────────────────────────────────────────────────
    (r"constant\s*\d{4}\s*US\$|constant US\$", "usd_constant"),
    (r"current US\$|\bUS\$\)|\(BoP", "usd"),
    (r"international\s*\$|\bPPP\b", "intl_usd"),
    (r"current LCU|constant LCU|\bLCU\b", "lcu"),
    (r"national currency", "moneda_nacional"),
    # ── Indices y escalas ─────────────────────────────────────────
    (r"=\s*100\b|\bindex\b\s*\(|\bindex\b", "index"),
    (r"\bscore\b|\(1=.*to.*\)|\(-2\.5.*2\.5\)", "score"),
    # ── Tasas por poblacion ───────────────────────────────────────
    (r"per\s*100,000", "por_100000"),
    (r"per\s*1,000|per\s*1000", "por_1000"),
    (r"per\s*capita|per\s*person|per\s*million people", "por_habitante"),
    (r"per\s*sq\.?\s*km", "por_km2"),
    # ── Fisicas ───────────────────────────────────────────────────
    (r"\bMt\s*CO2|\bMtCO2|CO2\s*equivalent", "mt_co2e"),
    (r"\(Mt\)|million\s*(metric\s*)?tons", "mt"),
    (r"\(kt\)|kiloton", "kt"),
    (r"metric tons|\(tonnes?\)|\(t\)", "t"),
    (r"\(kg[\s,)]|kilograms?", "kg"),
    (r"kg of oil equivalent", "kg_oil_eq"),
    (r"\bkWh\b|kilowatt", "kwh"),
    (r"\bTWh\b", "twh"),
    (r"sq\.?\s*km|square kilomet", "km2"),
    (r"\bhectares?\b", "ha"),
    (r"cu\.?\s*m|cubic met", "m3"),
    (r"\bTEU\b", "teu"),
    (r"ton-km|route-km", "km"),
    (r"liters?\b", "l"),
    # ── Tiempo y recuentos ────────────────────────────────────────
    (r"\(years?\)|\byears\b", "years"),
    (r"\(days?\)", "days"),
    (r"hours? per week|\(hours?\)", "hours"),
    (r"months of imports|\(months?\)", "months"),
    (r"\bpopulation\b|\bpeople\b|\bpersons\b|\binhabitants\b", "persons"),
    (r"number of|,\s*total$|\bcount\b|applications|subscriptions", "units"),
    # ── Familias sin unidad en el nombre ──────────────────────────
    # Hasta aqui llegan las que la traen escrita. Lo que sigue son
    # familias enteras de indicadores cuya unidad hay que conocer de
    # antemano: puntuaciones de gobernanza, tasas de organismos que
    # no las etiquetan, recuentos en prosa.
    (r"^B-READY|governance estimate|freedom house|\(0-1\)", "score"),
    (r"income share|wealth share|\blabou?r share\b", "pct"),
    (r"confidence \(OECD\)|leading indicator|volume \(OECD\)", "index"),
    (r"effective exchange rate|\bdeflator\b", "index"),
    (r"maternal mortality", "por_100000"),
    (r"mortality rate|mortality ratio", "por_1000"),
    (r"life expectancy", "years"),
    (r"prevalence|prob\.? dying|\bobesity\b|water stress", "pct"),
    (
        r"unemployment rate|participation rate|inflation rate"
        r"|lending rate|policy rate|money market rate"
        r"|\brate\b.*\(IMF IFS\)|internal rate of return",
        "pct",
    ),
    (r"pupil-\w+ ratio|debt service ratio|sex ratio|\bratio\b", "ratio"),
    (r"fertility rate|births per", "births_per_woman"),
    (r"hours worked", "hours"),
    (r"constant nat\.? prices|const\.? nat\.? prices", "usd_constant"),
    (r"\(current USD", "usd"),
    (
        r"passengers carried|\bpupils\b|\bteachers\b|journal articles"
        r"|internet servers|species|refugees|asylum-seekers"
        r"|patents granted|businesses registered|out of school"
        r"|net migration|newly infected|living with HIV"
        r"|nights in accommodation|carrier departures",
        "units",
    ),
]

_COMPILADOS = [(re.compile(p, re.IGNORECASE), u) for p, u in _PATRONES]


# Indicadores cuya unidad documenta la fuente y el nombre no delata.
# Mandan sobre cualquier patron. Todos salieron de contrastar la
# inferencia contra la magnitud observada: sin ese contraste, cinco de
# estos seis habrian quedado etiquetados como dolares o porcentajes.
_UNIDADES_POR_CODIGO = {
    # PWT: `rkna` y `rtfpna` son indices con base 2017=1, no importes.
    "PWT_CAPITAL_STOCK": "index",
    "PWT_TFP_NATIONAL": "index",
    "PWT_TFP_LEVEL": "index",
    # `labsh` e `irr` son fracciones (0,52 y 0,11), no porcentajes.
    "PWT_LABOR_SHARE": "ratio",
    "PWT_IRR": "ratio",
    "PWT_REAL_GDP": "usd_millions",
    # El nombre dice "PPP" y la unidad es un porcentaje del total
    # mundial.
    "IMF_PPPSH": "pct_world",
}


# Etiquetas en prosa que llegan crudas de la fuente —el FMI las manda
# en el CSV, FRED en `/fred/series`— y hay que llevar al vocabulario
# canonico.
_EQUIVALENCIAS = {
    "purchasing power parity; billions of international": "intl_usd",
    "purchasing power parity; international dollars per": "intl_usd",
    "national currency per international dollar": "moneda_nacional",
    "months of imports of goods and services": "months",
    "percent": "pct",
    "percent per annum": "pct",
    "percent of gdp": "pct_gdp",
    "percent change from preceding period": "pct_change",
    "percent change from year ago": "pct_change_yoy",
    "index": "index",
    "normalised (normal=100)": "index",
    "us dollars": "usd",
    "dollars": "usd",
    "billions of dollars": "usd_billions",
    "millions of dollars": "usd_millions",
    "dollars per barrel": "usd_per_barrel",
    "dollars per million btu": "usd_per_mmbtu",
    "thousands of persons": "persons_thousands",
    "thousands of units": "units_thousands",
    "number": "units",
    "number of units": "units",
    "national currency": "moneda_nacional",
}

# Familias enteras que no vale la pena enumerar una a una: FRED tiene
# una etiqueta de indice distinta por cada base ("Index 1982-1984=100",
# "Index Jan 2006=100") y una de tipo de cambio por cada par
# ("Japanese Yen to One U.S. Dollar").
_PATRONES_FUENTE = [
    (re.compile(r"^index\b|=\s*100", re.IGNORECASE), "index"),
    (re.compile(r"\bto one\b", re.IGNORECASE), "tipo_de_cambio"),
]


def normalizar_unidad(texto: str | None) -> str | None:
    """Llevar una etiqueta de la fuente al vocabulario canonico.

    Devuelve None si no hay etiqueta, para que el llamante decida si
    intentar la inferencia por nombre.
    """
    if not texto:
        return None
    limpio = texto.strip().lower()
    if limpio in _EQUIVALENCIAS:
        return _EQUIVALENCIAS[limpio]
    for patron, unidad in _PATRONES_FUENTE:
        if patron.search(limpio):
            return unidad
    return texto.strip()[:50]


def inferir_unidad(nombre: str | None) -> str | None:
    """Deducir la unidad del nombre del indicador.

    Devuelve None si ningun patron encaja, para que el llamante pueda
    distinguir "no se ha podido deducir" de una unidad real.
    """
    if not nombre:
        return None
    for patron, unidad in _COMPILADOS:
        if patron.search(nombre):
            return unidad
    return None


def aplicar_unidades(forzar: bool = False) -> dict[str, int]:
    """Rellenar `macro.indicator.unit` en toda la tabla.

    Tres pasadas, de mas fiable a menos:

    1. Normalizar las etiquetas que ya existen pero llegaron en prosa
       de la fuente ("Purchasing power parity; billions of
       international").
    2. Deducir del nombre las que faltan.
    3. Marcar `desconocida` lo que quede, que es distinto de NULL:
       dice que se miro y no se pudo determinar.

    Es idempotente: se puede relanzar tras anadir patrones nuevos y
    solo toca lo que sigue sin resolver. Lo que no reescribe es una
    unidad ya canonica, para no pisar la que un fetcher haya puesto
    con mejor informacion que el nombre.

    Con `forzar`, vuelve a deducir tambien las que ya tienen unidad,
    pero solo las sustituye cuando la inferencia da algo: asi se
    puede corregir una etiqueta mal deducida sin borrar las que
    vinieron de la fuente, que no llevan la unidad en el nombre.
    """
    from sqlalchemy import text

    from stonks.db import engine

    salida = {"normalizadas": 0, "inferidas": 0, "desconocidas": 0}

    with engine.begin() as conn:
        filas = conn.execute(
            text("SELECT id, code, name, unit FROM macro.indicator")
        ).fetchall()

        for ind_id, codigo, nombre, unidad in filas:
            declarada = _UNIDADES_POR_CODIGO.get(codigo)
            if declarada:
                if declarada != unidad:
                    conn.execute(
                        text(
                            "UPDATE macro.indicator SET unit = :u "
                            "WHERE id = :i"
                        ),
                        {"u": declarada, "i": ind_id},
                    )
                    salida["normalizadas"] += 1
                continue

            if unidad and unidad != DESCONOCIDA:
                canonica = normalizar_unidad(unidad)
                rededucida = inferir_unidad(nombre) if forzar else None
                if canonica != unidad:
                    nueva, clave = canonica, "normalizadas"
                elif rededucida and rededucida != unidad:
                    nueva, clave = rededucida, "inferidas"
                else:
                    continue
            else:
                deducida = inferir_unidad(nombre)
                if deducida:
                    nueva, clave = deducida, "inferidas"
                elif unidad == DESCONOCIDA:
                    continue
                else:
                    nueva, clave = DESCONOCIDA, "desconocidas"

            conn.execute(
                text(
                    "UPDATE macro.indicator SET unit = :u WHERE id = :i"
                ),
                {"u": nueva, "i": ind_id},
            )
            salida[clave] += 1

    logger.info(
        "Unidades: %d normalizadas, %d inferidas del nombre, "
        "%d marcadas como desconocidas",
        salida["normalizadas"],
        salida["inferidas"],
        salida["desconocidas"],
    )
    return salida
