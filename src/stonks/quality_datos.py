"""Checks de veracidad y completitud de datos.

Complementa `stonks.quality`, que mide cobertura e integridad
referencial. Aquí van las comprobaciones que responden a otra
pregunta: **¿los datos son ciertos?**

Cada check nació de un defecto real encontrado en la auditoría de
datos de 2026-08, y existe para que ese defecto no pueda volver sin
que nadie se entere:

- `check_ohlc_coherente`: había 22.166 precios negativos y 10.672
  filas con `high < low`, consecuencia de guardar precios ajustados
  en la columna `close`.
- `check_unidades`: `GDP_NOMINAL` declaraba `billion_usd` con valores
  en dólares absolutos, un error de factor mil millones.
- `check_coherencia_fuentes`: contrasta indicadores que publican dos
  organismos distintos. Es la prueba directa de veracidad.
- `check_empalme_series`: cuatro `coin_id` de crypto contenían dos
  activos distintos empalmados.
- `check_frescura_sla`: el SLA estaba escrito en prosa y nadie lo
  comparaba con la realidad.
- `check_fallos_fetch`: había 2.428 ejecuciones fallidas que no
  aparecían en ningún sitio, incluidas las 12 del intraday que
  mantuvieron tres tablas a cero.
- `check_tablas_vacias`: distingue el catálogo legítimamente pequeño
  de la tabla que debería tener datos y no los tiene.
- `check_unidades_de_columna`: una columna que se llama `_usd` o
  `_pct` promete una unidad. Cuatro defectos distintos llegaron a
  producción por no comprobar esa promesa.

Como el resto de checks, son informativos: registran en
`meta.data_quality` y avisan por log, pero no bloquean nada.
"""

from sqlalchemy import text

from stonks.db import engine
from stonks.logger import get_logger

logger = get_logger("stonks.quality")


# ─── OHLC coherente ────────────────────────────────────────────────
# (tabla, columna de cierre) de cada serie de precios.
_TABLAS_OHLC = [
    ("equity.price_daily", "close"),
    ("crypto.price_daily", "close"),
    ("commodity.price_daily", "close"),
    ("forex.rate_daily", "close"),
    ("equity.index_price", "close"),
    ("deriv.futures_daily", "close"),
]

# (nombre de la regla, condición SQL que la INCUMPLE)
_REGLAS_OHLC = [
    ("cierre_no_positivo", "close <= 0"),
    ("maximo_menor_que_minimo", "high < low"),
    ("cierre_fuera_de_rango", "close < low OR close > high"),
    ("apertura_fuera_de_rango", "open < low OR open > high"),
]


# ─── Plausibilidad de unidades ─────────────────────────────────────
# (etiqueta canónica, mínimo y máximo plausibles para la mediana de
# |valor|). Una etiqueta que diga "miles de millones" no puede tener
# una mediana de 8.200.000.000.
_RANGOS_UNIDAD = {
    "pct": (0.001, 500),
    "pct_gdp": (0.001, 1000),
    "pct_change_yoy": (0.001, 1000),
    "pct_potential_gdp": (0.001, 500),
    "pct_world": (0.0001, 100),
    "usd": (1, 1e15),
    "intl_usd": (1, 1e15),
    "usd_millions": (0.001, 1e8),
    "usd_billions": (0.001, 1e5),
    "usd_per_capita": (1, 1e6),
    "people_millions": (0.0001, 2000),
    "persons": (1, 1e10),
    "index": (0.01, 1e5),
    "index_2010_100": (0.01, 1e5),
    # Vocabulario que entró al recuperar las unidades del catálogo
    # macro. Los rangos son deliberadamente anchos: sirven para cazar
    # un error de factor mil, no para afinar.
    "pct_gni": (0.001, 500),
    "pct_change": (0.001, 1000),
    "usd_constant": (1, 1e15),
    "lcu": (1, 1e18),
    "moneda_nacional": (0.001, 1e18),
    "score": (0.001, 1000),
    "ratio": (0.0001, 1e4),
    "por_1000": (0.0001, 1e4),
    "por_100000": (0.0001, 1e6),
    "por_habitante": (0.0001, 1e7),
    "por_km2": (0.0001, 1e6),
    "years": (0.1, 200),
    "days": (0.01, 1e4),
    "hours": (0.01, 1e5),
    "months": (0.01, 1e3),
    "persons_thousands": (0.001, 1e7),
    "units": (0.001, 1e12),
    "units_thousands": (0.001, 1e9),
    "births_per_woman": (0.1, 20),
    "tipo_de_cambio": (1e-6, 1e6),
    "mt_co2e": (1e-6, 1e5),
    "kg_oil_eq": (0.1, 1e6),
    "usd_per_barrel": (1, 1e4),
    "usd_per_mmbtu": (0.01, 1e3),
}


# ─── Coherencia entre fuentes ──────────────────────────────────────
# (indicador A, indicador B, tolerancia en % sobre la desviación)
# Dos organismos midiendo lo mismo deberían coincidir a grandes
# rasgos; si divergen mucho, uno de los dos está mal cargado.
_PARES_CRUZADOS = [
    ("GDP_PER_CAPITA", "IMF_NGDPDPC", 10.0),
    ("INFLATION_CPI", "IMF_PCPIPCH", 20.0),
    ("UNEMPLOYMENT", "IMF_LUR", 20.0),
]


# ─── SLA de frescura ───────────────────────────────────────────────
# (dominio, tabla, columna de fecha, días máximos de retraso)
# Los umbrales salen de docs/FRESHNESS_SLA.md, pero viven aquí porque
# es donde se pueden comprobar. El documento explica el porqué.
_SLA = [
    ("equity", "equity.price_daily", "date", 5),
    ("equity", "equity.index_price", "date", 5),
    ("crypto", "crypto.price_daily", "date", 3),
    ("forex", "forex.rate_daily", "date", 5),
    ("commodity", "commodity.price_daily", "date", 5),
    ("fund", "fund.nav_daily", "date", 5),
    ("fi", "fi.yield_curve", "date", 7),
    ("deriv", "deriv.volatility_daily", "date", 5),
    ("deriv", "deriv.futures_daily", "date", 5),
    # El COT se publica los viernes con tres días de retraso.
    ("deriv", "deriv.cot_report", "report_date", 12),
    ("realestate", "realestate.price_index_value", "date", 200),
]


# ─── Tablas que deberían tener datos ───────────────────────────────
# Solo las que son hechos, no catálogos: `deriv.volatility_index` con
# 12 filas está bien, `crypto.price_intraday` con 0 no.
_MINIMOS = {
    "equity.price_daily": 1_000_000,
    "equity.price_intraday": 1_000,
    "crypto.price_daily": 10_000,
    "crypto.price_intraday": 1_000,
    "forex.rate_daily": 10_000,
    "forex.rate_intraday": 1_000,
    "commodity.price_daily": 10_000,
    "commodity.price_intraday": 1_000,
    "fund.nav_daily": 10_000,
    "macro.data_point": 1_000_000,
    "trade.flow": 100_000,
    "deriv.cot_report": 10_000,
    "realestate.price_index_value": 1_000,
    "calendar.release_date": 1_000,
    "country.profile": 150,
    "country.tax_rate": 100,
    "fi.country_risk_premium": 100,
    "equity.factor_return": 1_000,
    "ref.legal_entity": 100,
}


def _persistir(conn, dominio, tipo, entidad, score, n=None) -> None:
    """Escribir una fila de resultado en meta.data_quality."""
    conn.execute(
        text(
            "INSERT INTO meta.data_quality "
            "(domain, entity_type, entity_id, completeness_score, "
            " source_count, last_assessed) "
            "VALUES (:d, :t, :e, :s, :n, now())"
        ),
        {"d": dominio, "t": tipo, "e": entidad[:200], "s": score, "n": n},
    )


def _limpiar(conn, tipo: str) -> None:
    """Borrar los resultados previos de un tipo de check."""
    conn.execute(
        text("DELETE FROM meta.data_quality WHERE entity_type = :t"),
        {"t": tipo},
    )


def check_ohlc_coherente() -> dict:
    """Comprobar que las velas de precio son internamente posibles.

    Un maximo por debajo del minimo, o un cierre fuera del rango del
    dia, significan que la serie esta corrupta.
    """
    resumen: dict[str, int] = {}
    with engine.begin() as conn:
        _limpiar(conn, "ohlc")
        for tabla, _ in _TABLAS_OHLC:
            for regla, condicion in _REGLAS_OHLC:
                clave = f"{tabla}:{regla}"
                try:
                    n = conn.execute(
                        text(f"SELECT count(*) FROM {tabla} WHERE {condicion}")
                    ).scalar() or 0
                except Exception as e:  # noqa: BLE001
                    logger.warning("ohlc %s: %s", clave, e)
                    continue

                resumen[clave] = n
                _persistir(
                    conn,
                    tabla.split(".")[0],
                    "ohlc",
                    clave,
                    100.0 if n == 0 else 0.0,
                    n,
                )
                if n:
                    logger.warning("OHLC %s: %d filas", clave, n)

    total = sum(resumen.values())
    logger.info("OHLC: %d filas incoherentes en total", total)
    return resumen


def check_unidades() -> dict:
    """Contrastar la etiqueta de unidad con la magnitud observada.

    `GDP_NOMINAL` declaraba `billion_usd` teniendo una mediana de
    8,2e9: quien confiara en la etiqueta se equivocaba por un factor
    de mil millones.
    """
    resumen: dict[str, str] = {}
    with engine.begin() as conn:
        _limpiar(conn, "unidad")
        filas = conn.execute(
            text(
                "SELECT i.code, i.unit, "
                "  percentile_cont(0.5) WITHIN GROUP "
                "    (ORDER BY abs(d.value)) AS mediana "
                "FROM macro.data_point d "
                "JOIN macro.series s ON s.id = d.series_id "
                "JOIN macro.indicator i ON i.id = s.indicator_id "
                "WHERE i.unit IS NOT NULL AND d.value <> 0 "
                "GROUP BY i.code, i.unit "
                "HAVING count(*) > 100"
            )
        ).fetchall()

        for code, unidad, mediana in filas:
            rango = _RANGOS_UNIDAD.get(unidad)
            if rango is None or mediana is None:
                continue
            minimo, maximo = rango
            ok = minimo <= float(mediana) <= maximo
            _persistir(
                conn,
                "macro",
                "unidad",
                f"{code}:{unidad}",
                100.0 if ok else 0.0,
            )
            if not ok:
                resumen[code] = f"{unidad} con mediana {float(mediana):.3g}"
                logger.warning(
                    "Unidad implausible %s: '%s' con mediana %.3g",
                    code,
                    unidad,
                    float(mediana),
                )

    logger.info("Unidades: %d etiquetas implausibles", len(resumen))
    return resumen


def check_coherencia_fuentes() -> dict:
    """Comparar indicadores que publican dos organismos distintos.

    Si el World Bank y el FMI miden lo mismo y sus cifras divergen
    mucho, uno de los dos esta mal cargado. En la auditoria, el PIB
    per capita de 2022 daba un desvio medio del 3,57 % sobre 190
    paises, que es lo esperable entre dos metodologias.
    """
    resumen: dict[str, dict] = {}
    with engine.begin() as conn:
        _limpiar(conn, "coherencia")
        for codigo_a, codigo_b, tolerancia in _PARES_CRUZADOS:
            try:
                fila = conn.execute(
                    text(
                        "WITH a AS ("
                        "  SELECT s.country_code, d.date, d.value v "
                        "  FROM macro.data_point d "
                        "  JOIN macro.series s ON s.id = d.series_id "
                        "  JOIN macro.indicator i ON i.id = s.indicator_id "
                        "  WHERE i.code = :ca AND NOT d.is_forecast), "
                        "b AS ("
                        "  SELECT s.country_code, d.date, d.value v "
                        "  FROM macro.data_point d "
                        "  JOIN macro.series s ON s.id = d.series_id "
                        "  JOIN macro.indicator i ON i.id = s.indicator_id "
                        "  WHERE i.code = :cb AND NOT d.is_forecast) "
                        "SELECT count(*), "
                        "  avg(abs(a.v - b.v) / nullif(abs(b.v), 0)) * 100, "
                        "  count(*) FILTER ("
                        "    WHERE abs(a.v - b.v) / nullif(abs(b.v), 0) "
                        "          > :tol) "
                        "FROM a JOIN b "
                        "  ON a.country_code = b.country_code "
                        " AND a.date = b.date"
                    ),
                    {"ca": codigo_a, "cb": codigo_b,
                     "tol": tolerancia / 100.0},
                ).first()
            except Exception as e:  # noqa: BLE001
                logger.warning("coherencia %s/%s: %s", codigo_a, codigo_b, e)
                continue

            comparadas, desvio, divergentes = fila
            if not comparadas:
                continue

            pct_divergentes = 100.0 * (divergentes or 0) / comparadas
            clave = f"{codigo_a}~{codigo_b}"
            resumen[clave] = {
                "comparadas": comparadas,
                "desvio_pct": round(float(desvio or 0), 2),
                "divergentes": divergentes or 0,
            }
            _persistir(
                conn,
                "macro",
                "coherencia",
                clave,
                round(100.0 - pct_divergentes, 2),
                comparadas,
            )
            if pct_divergentes > 25:
                logger.warning(
                    "Coherencia %s: %.1f%% de %d observaciones divergen "
                    "mas del %.0f%%",
                    clave,
                    pct_divergentes,
                    comparadas,
                    tolerancia,
                )

    logger.info("Coherencia entre fuentes: %s", resumen)
    return resumen


def check_empalme_series() -> dict:
    """Detectar series que empalman dos activos distintos.

    Cuatro `coin_id` de crypto tenian un bloque antiguo de valores
    minusculos y, tras un hueco de meses o anos, el bloque real de la
    moneda. Se busca ese patron: hueco largo mas salto de magnitud.
    """
    resumen: dict[str, int] = {}
    with engine.begin() as conn:
        _limpiar(conn, "empalme")
        filas = conn.execute(
            text(
                "WITH saltos AS ("
                "  SELECT c.symbol, p.date, "
                "    p.date - lag(p.date) OVER w AS hueco, "
                "    p.close, lag(p.close) OVER w AS previo "
                "  FROM crypto.price_daily p "
                "  JOIN crypto.coin c ON c.id = p.coin_id "
                "  WHERE p.close > 0 "
                "  WINDOW w AS (PARTITION BY p.coin_id ORDER BY p.date)) "
                "SELECT symbol, date, hueco, previo, close "
                "FROM saltos "
                "WHERE hueco > 90 AND previo > 0 "
                "  AND (close / previo > 100 OR close / previo < 0.01)"
            )
        ).fetchall()

        for simbolo, fecha, hueco, previo, cierre in filas:
            resumen[simbolo] = int(hueco)
            _persistir(conn, "crypto", "empalme", simbolo, 0.0, int(hueco))
            logger.warning(
                "Empalme en %s el %s: hueco de %d dias, de %.8f a %.8f",
                simbolo,
                fecha,
                hueco,
                float(previo),
                float(cierre),
            )

        if not filas:
            _persistir(conn, "crypto", "empalme", "sin_empalmes", 100.0, 0)

    logger.info("Empalmes de serie: %d detectados", len(resumen))
    return resumen


def check_frescura_sla() -> dict:
    """Comparar el retraso real de cada dominio con su SLA.

    Hasta ahora el SLA solo existia en prosa, en
    docs/FRESHNESS_SLA.md, y nadie lo comprobaba.
    """
    resumen: dict[str, dict] = {}
    with engine.begin() as conn:
        _limpiar(conn, "sla")
        for dominio, tabla, columna, maximo in _SLA:
            try:
                dias = conn.execute(
                    text(
                        f"SELECT CURRENT_DATE - max({columna}) FROM {tabla}"
                    )
                ).scalar()
            except Exception as e:  # noqa: BLE001
                logger.warning("sla %s: %s", tabla, e)
                continue

            if dias is None:
                # Tabla vacia: lo reporta check_tablas_vacias.
                continue

            dias = int(dias)
            cumple = dias <= maximo
            resumen[tabla] = {"dias": dias, "sla": maximo, "ok": cumple}
            conn.execute(
                text(
                    "INSERT INTO meta.data_quality "
                    "(domain, entity_type, entity_id, "
                    " completeness_score, freshness_days, last_assessed) "
                    "VALUES (:d, 'sla', :e, :s, :f, now())"
                ),
                {
                    "d": dominio,
                    "e": tabla,
                    "s": 100.0 if cumple else 0.0,
                    "f": dias,
                },
            )
            if not cumple:
                logger.warning(
                    "SLA incumplido en %s: %d dias de retraso (maximo %d)",
                    tabla,
                    dias,
                    maximo,
                )

    incumplen = [t for t, v in resumen.items() if not v["ok"]]
    logger.info("SLA: %d dominios fuera de plazo", len(incumplen))
    return resumen


def check_fallos_fetch(dias: int = 30) -> dict:
    """Contar ejecuciones fallidas por dominio.

    Habia 2.428 fallos invisibles, entre ellos las 12 del intraday
    que mantuvieron tres tablas a cero durante semanas sin que nada
    lo dijera.
    """
    resumen: dict[str, int] = {}
    with engine.begin() as conn:
        _limpiar(conn, "fallos_fetch")
        filas = conn.execute(
            text(
                "SELECT domain, "
                "  count(*) FILTER (WHERE status = 'failed') fallos, "
                "  count(*) total "
                "FROM meta.fetch_run "
                "WHERE started_at > now() - make_interval(days => :d) "
                "GROUP BY domain ORDER BY 2 DESC"
            ),
            {"d": dias},
        ).fetchall()

        for dominio, fallos, total in filas:
            if not total:
                continue
            pct_ok = 100.0 * (total - fallos) / total
            resumen[dominio] = fallos
            _persistir(
                conn, dominio, "fallos_fetch", dominio, round(pct_ok, 2), fallos
            )
            if fallos and pct_ok < 90:
                logger.warning(
                    "Fetch %s: %d fallos de %d ejecuciones (%.0f%% ok)",
                    dominio,
                    fallos,
                    total,
                    pct_ok,
                )

    logger.info("Fallos de fetch (%d dias): %s", dias, resumen)
    return resumen


def check_tablas_vacias() -> dict:
    """Comprobar que las tablas de hechos tienen datos.

    Solo mira las que deberian tenerlos: un catalogo de 12 indices de
    volatilidad esta bien con 12 filas, pero `crypto.price_intraday`
    con cero significa que su fetcher lleva semanas fallando.
    """
    resumen: dict[str, int] = {}
    with engine.begin() as conn:
        _limpiar(conn, "tabla_vacia")
        for tabla, minimo in sorted(_MINIMOS.items()):
            try:
                n = conn.execute(
                    text(f"SELECT count(*) FROM {tabla}")
                ).scalar() or 0
            except Exception as e:  # noqa: BLE001
                logger.warning("tabla_vacia %s: %s", tabla, e)
                continue

            score = min(100.0, 100.0 * n / minimo) if minimo else 100.0
            resumen[tabla] = n
            _persistir(conn, tabla.split(".")[0], "tabla_vacia", tabla,
                       round(score, 2), n)
            if n < minimo:
                logger.warning(
                    "Tabla por debajo del minimo: %s tiene %d filas "
                    "(se esperaban %d)",
                    tabla,
                    n,
                    minimo,
                )

    bajas = [t for t, n in resumen.items() if n < _MINIMOS[t]]
    logger.info("Tablas por debajo del minimo: %d", len(bajas))
    return resumen


def check_precios_cruzados(muestra: int = 20) -> dict:
    """Contrastar los precios contra una segunda fuente.

    Hasta ahora todos los precios de renta variable venian de yfinance,
    asi que un error suyo era indetectable desde dentro: la base seria
    perfectamente coherente consigo misma y estaria equivocada. Este
    check pide los ultimos cierres de una muestra a Tiingo y mide la
    diferencia.

    Sin `STONKS_TIINGO_KEY` no se puede ejecutar. En ese caso se
    registra como omitido en vez de fallar en silencio: la diferencia
    entre "no diverge" y "no se ha mirado" es justo lo que este
    proyecto lleva tres auditorias intentando no perder.
    """
    from stonks.fetchers.tiingo import SinClaveTiingo, TiingoFetcher

    with engine.begin() as conn:
        _limpiar(conn, "precios_cruzados")
        try:
            salida = TiingoFetcher().comparar_precios(muestra=muestra)
        except SinClaveTiingo:
            logger.warning(
                "Cruce de precios omitido: falta STONKS_TIINGO_KEY"
            )
            _persistir(
                conn, "equity", "precios_cruzados", "sin_clave", None, 0
            )
            return {"omitido": "falta STONKS_TIINGO_KEY"}

        comparados = salida["comparados"]
        divergentes = salida["divergentes"]
        pct_ok = (
            100.0 * (comparados - divergentes) / comparados
            if comparados
            else 0.0
        )
        _persistir(
            conn,
            "equity",
            "precios_cruzados",
            "yfinance_vs_tiingo",
            round(pct_ok, 2),
            comparados,
        )
        if divergentes:
            logger.warning(
                "Cruce de precios: %d de %d divergen mas del umbral; "
                "el peor es %s",
                divergentes,
                comparados,
                salida["peor"],
            )

    return salida


# Multiplo respecto a los dos vecinos por encima del cual una vela no
# puede ser real. Ni una suspension de cotizacion ni un desplome
# producen una V de ese tamano en un solo dia.
FACTOR_PRECIO_AISLADO = 10


def check_precios_aislados() -> dict:
    """Buscar velas diez veces fuera de sus dos vecinas.

    Un precio que cae un 90 % y lo recupera entero al dia siguiente no
    es un movimiento de mercado, es un artefacto de la fuente. Titanium
    Metals cotizaba sobre 10.000 y el 2012-04-02 aparecio con un OHLC
    plano de 1,40; TNB alternaba entre 28.000 y 1,44 en 599 sesiones.

    Importan mas de lo que su numero sugiere: 2.002 filas de 28,9
    millones bastaban para que el indice equiponderado de
    `gold.mart_benchmark_returns` acumulara un 10 elevado a 50, porque
    una media no tiene defensa frente a un valor extremo.

    El criterio no mira el volumen a proposito: Banco Santander Chile
    marca 1.989 entre 20,3 y 20,4 con 14,7 millones de titulos
    negociados. Lo que delata el artefacto es la forma.
    """
    with engine.begin() as conn:
        _limpiar(conn, "precios_aislados")
        n = conn.execute(
            text(
                "WITH vecinos AS ("
                "  SELECT close, "
                "         lag(close) OVER (PARTITION BY company_id "
                "                          ORDER BY date) AS anterior, "
                "         lead(close) OVER (PARTITION BY company_id "
                "                           ORDER BY date) AS siguiente "
                "  FROM equity.price_daily) "
                "SELECT count(*) FROM vecinos "
                "WHERE close > 0 AND anterior > 0 AND siguiente > 0 "
                "  AND ((anterior > close * :f AND siguiente > close * :f) "
                "    OR (anterior * :f < close AND siguiente * :f < close))"
            ),
            {"f": FACTOR_PRECIO_AISLADO},
        ).scalar() or 0

        _persistir(
            conn,
            "equity",
            "precios_aislados",
            "equity.price_daily",
            100.0 if n == 0 else 0.0,
            n,
        )
        if n:
            logger.warning(
                "Precios aislados: %d velas fuera de escala respecto a "
                "sus dos vecinas",
                n,
            )

    return {"aislados": n}


def run_checks_datos() -> dict:
    """Ejecutar todos los checks de veracidad y completitud."""
    salida: dict[str, dict] = {}
    for nombre, funcion in [
        ("ohlc", check_ohlc_coherente),
        ("unidades", check_unidades),
        ("coherencia_fuentes", check_coherencia_fuentes),
        ("empalme_series", check_empalme_series),
        ("frescura_sla", check_frescura_sla),
        ("fallos_fetch", check_fallos_fetch),
        ("tablas_vacias", check_tablas_vacias),
        ("identidad_contable", check_identidad_contable),
        ("capitalizacion", check_capitalizacion),
        ("comercio_espejo", check_comercio_espejo),
        ("unidad_columna", check_unidades_de_columna),
        ("precios_cruzados", check_precios_cruzados),
        ("precios_aislados", check_precios_aislados),
    ]:
        try:
            salida[nombre] = funcion()
        except Exception as e:  # noqa: BLE001
            logger.error("Check %s fallo: %s", nombre, e)
            salida[nombre] = {"error": str(e)}
    return salida


# ─── Coherencia cruzada entre dominios ─────────────────────────────
# Comprobaciones que cruzan tablas distintas y que hasta la auditoría
# de fiabilidad solo se habían hecho a mano.

# Tolerancia del descuadre del balance, como fracción del activo.
TOLERANCIA_BALANCE = 0.01

# La capitalización es una foto y las acciones en circulación cambian,
# así que se admite un margen amplio antes de sospechar.
TOLERANCIA_CAPITALIZACION = 0.25

# El comercio espejo nunca cuadra del todo: las exportaciones se
# valoran FOB y las importaciones CIF, y las reexportaciones se
# cuentan dos veces. Un 40 % de desvío medio es lo normal en la
# literatura; por encima indica un problema de carga.
TOLERANCIA_ESPEJO = 45.0


def check_identidad_contable() -> dict:
    """Activo = pasivo + patrimonio.

    Es la comprobación más básica de un balance: si no cuadra, el dato
    está mal cargado. En la auditoría descuadraban 7 filas de 18.697.
    """
    with engine.begin() as conn:
        _limpiar(conn, "identidad_contable")
        total, descuadran = conn.execute(
            text(
                "SELECT count(*), count(*) FILTER ("
                "  WHERE abs(total_assets "
                "            - (total_liabilities + total_equity)) "
                "        > greatest(abs(total_assets) * :tol, 1000)) "
                "FROM equity.balance_sheet "
                "WHERE total_assets IS NOT NULL "
                "AND total_liabilities IS NOT NULL "
                "AND total_equity IS NOT NULL AND total_assets <> 0"
            ),
            {"tol": TOLERANCIA_BALANCE},
        ).first()

        pct_ok = 100.0 * (total - descuadran) / total if total else 100.0
        _persistir(
            conn, "equity", "identidad_contable", "balance",
            round(pct_ok, 2), descuadran,
        )
        if descuadran:
            logger.warning(
                "Identidad contable: %d balances de %d no cuadran",
                descuadran, total,
            )

    return {"comparados": total, "descuadran": descuadran}


def check_capitalizacion() -> dict:
    """Capitalizacion contra acciones en circulacion por precio.

    Detecta errores de unidad, como guardar la capitalizacion en
    moneda local bajo un nombre que promete dolares: Toyota figuraba
    con 34,5 billones, que eran yenes.
    """
    with engine.begin() as conn:
        _limpiar(conn, "capitalizacion")
        total, descuadran = conn.execute(
            text(
                "WITH u AS ("
                "  SELECT c.market_cap_usd AS mc, "
                "         c.shares_outstanding * ("
                "           SELECT p.close FROM equity.price_daily p "
                "           WHERE p.company_id = c.id "
                "           ORDER BY p.date DESC LIMIT 1"
                "         ) AS calculada "
                "  FROM equity.company c "
                "  WHERE c.market_cap_usd > 0 "
                "  AND c.shares_outstanding > 0 "
                "  AND c.currency_code = 'USD') "
                "SELECT count(*), count(*) FILTER ("
                "  WHERE abs(mc - calculada) > mc * :tol) "
                "FROM u WHERE calculada > 0"
            ),
            {"tol": TOLERANCIA_CAPITALIZACION},
        ).first()

        pct_ok = 100.0 * (total - descuadran) / total if total else 100.0
        _persistir(
            conn, "equity", "capitalizacion", "market_cap_vs_acciones",
            round(pct_ok, 2), descuadran,
        )
        if total and descuadran / total > 0.3:
            logger.warning(
                "Capitalizacion: %d de %d empresas descuadran mas del "
                "%.0f%% frente a acciones por precio",
                descuadran, total, TOLERANCIA_CAPITALIZACION * 100,
            )

    logger.info(
        "Capitalizacion: %d comparadas, %d descuadran", total, descuadran
    )
    return {"comparados": total, "descuadran": descuadran}


def check_comercio_espejo() -> dict:
    """Lo que A dice exportar a B frente a lo que B dice importar de A.

    Nunca cuadra del todo: las exportaciones se valoran FOB y las
    importaciones CIF, y las reexportaciones se cuentan dos veces. La
    medicion de referencia dio un 36,1 % de desvio medio sobre 194.477
    pares, que esta dentro de lo normal. Por encima del umbral indica
    un problema de carga, no una peculiaridad del comercio.
    """
    with engine.begin() as conn:
        _limpiar(conn, "comercio_espejo")
        pares, desvio = conn.execute(
            text(
                "WITH x AS ("
                "  SELECT reporter_code a, partner_code b, period, "
                "         value_usd_k v FROM trade.flow "
                "  WHERE flow = 'X' AND product_code = 'Total' "
                "  AND value_usd_k > 0), "
                "m AS ("
                "  SELECT partner_code a, reporter_code b, period, "
                "         value_usd_k v FROM trade.flow "
                "  WHERE flow = 'M' AND product_code = 'Total' "
                "  AND value_usd_k > 0) "
                "SELECT count(*), "
                "  avg(abs(x.v - m.v) "
                "      / nullif(greatest(x.v, m.v), 0)) * 100 "
                "FROM x JOIN m "
                "  ON x.a = m.a AND x.b = m.b AND x.period = m.period"
            )
        ).first()

        desvio = float(desvio or 0)
        cumple = desvio <= TOLERANCIA_ESPEJO
        _persistir(
            conn, "trade", "comercio_espejo", "exportaciones_vs_importaciones",
            round(100.0 - min(desvio, 100.0), 2), pares,
        )
        if not cumple:
            logger.warning(
                "Comercio espejo: %.1f%% de desvio medio sobre %d pares "
                "(el umbral es %.0f%%)",
                desvio, pares, TOLERANCIA_ESPEJO,
            )

    logger.info(
        "Comercio espejo: %d pares, %.1f%% de desvio medio", pares, desvio
    )
    return {"pares": pares, "desvio_pct": round(desvio, 2)}


# ─── Unidades declaradas en el nombre de la columna ────────────────
# Una columna que se llama `_usd` o `_pct` promete una unidad. Cuatro
# defectos distintos de la misma familia han llegado a producción por
# no comprobar esa promesa: `market_cap_usd` en yenes, `value_usd` en
# wones, `pct_held` como fracción y `GDP_NOMINAL` etiquetado
# `billion_usd` con dólares absolutos.

# Techo plausible de cada columna en dólares, con lo que justifica el
# número. Por encima, la magnitud delata una moneda local: el yen y el
# won son unas 150 y 1.400 unidades por dólar.
_TECHOS_USD = {
    # La mayor cotizada del mundo ronda los 5 billones.
    "equity.company.market_cap_usd": 2e13,
    # La mayor posición de BlackRock ronda los 400.000 millones.
    "equity.holder.value_usd": 2e12,
    "equity.insider_transaction.value_usd": 1e11,
    # El PIB de EE. UU. ronda los 27 billones.
    "country.profile.gdp_usd": 5e13,
    # La capitalización total del mercado cripto ronda los 3 billones.
    "crypto.market_dominance.total_market_cap_usd": 2e13,
    "crypto.price_daily.market_cap_usd": 5e12,
}

# Para las columnas `_usd` sin techo declarado. No pretende afinar,
# solo cazar lo absurdo.
TECHO_USD_POR_DEFECTO = 1e15

# Un porcentaje puede dispararse de verdad —la sorpresa de resultados
# llega a 769.900 % cuando la estimación roza cero—, así que el techo
# se pone alto: solo caza lo imposible.
TECHO_PCT = 1e7

# Por debajo de esta cantidad de filas la muestra no dice nada.
MINIMO_FILAS_UNIDAD = 100


def check_unidades_de_columna() -> dict:
    """Comprobar que una columna contiene lo que su nombre promete.

    Dos reglas, cada una nacida de un defecto real:

    - Una columna de porcentaje cuyo máximo no pasa de 1 está
      guardando fracciones. Es lo que le pasaba a
      `equity.holder.pct_held`: BlackRock figuraba con 0,08 en Apple
      en vez de 7,79.
    - Una columna en dólares cuya magnitud supera su techo plausible
      está en moneda local. Es lo que le pasaba a `market_cap_usd`
      (Toyota con 34,5 billones de yenes) y a `value_usd` (la posición
      de Vanguard en Samsung con 18 billones de wones).
    """
    resumen: dict[str, str] = {}
    with engine.begin() as conn:
        _limpiar(conn, "unidad_columna")

        # Las particiones se excluyen: el padre ya las agrega y de otro
        # modo cada tabla intraday aparecería 120 veces.
        columnas = conn.execute(
            text(
                "SELECT c.table_schema, c.table_name, c.column_name "
                "FROM information_schema.columns c "
                "JOIN pg_class p ON p.relname = c.table_name "
                "JOIN pg_namespace n ON n.oid = p.relnamespace "
                "  AND n.nspname = c.table_schema "
                "WHERE c.data_type IN "
                "      ('numeric', 'double precision', 'real') "
                "  AND p.relkind IN ('r', 'p') "
                "  AND NOT p.relispartition "
                "  AND (c.column_name LIKE '%%pct%%' "
                "       OR c.column_name LIKE '%%percent%%' "
                "       OR c.column_name LIKE '%%\\_usd') "
                "ORDER BY 1, 2, 3"
            )
        ).fetchall()

        for esquema, tabla, columna in columnas:
            ruta = f"{esquema}.{tabla}.{columna}"
            try:
                n, maximo = conn.execute(
                    text(
                        f"SELECT count({columna}), max(abs({columna})) "
                        f"FROM {esquema}.{tabla}"
                    )
                ).first()
            except Exception as e:  # noqa: BLE001
                logger.warning("unidad_columna %s: %s", ruta, e)
                continue

            if not n or n < MINIMO_FILAS_UNIDAD or maximo is None:
                continue
            maximo = float(maximo)

            if columna.endswith("_usd"):
                techo = _TECHOS_USD.get(ruta, TECHO_USD_POR_DEFECTO)
                problema = (
                    f"maximo {maximo:.3g} sobre un techo de {techo:.3g}: "
                    "parece moneda local"
                    if maximo > techo
                    else None
                )
            elif maximo <= 1:
                problema = (
                    f"maximo {maximo:.3g}: parece una fraccion, no un "
                    "porcentaje"
                )
            elif maximo > TECHO_PCT:
                problema = f"maximo {maximo:.3g}: fuera de rango"
            else:
                problema = None

            _persistir(
                conn,
                esquema,
                "unidad_columna",
                ruta,
                0.0 if problema else 100.0,
                n,
            )
            if problema:
                resumen[ruta] = problema
                logger.warning("Unidad de columna %s: %s", ruta, problema)

    logger.info(
        "Unidades de columna: %d sospechosas de %d revisadas",
        len(resumen),
        len(columnas),
    )
    return resumen
