"""Invariantes de veracidad y completitud de los datos.

Hermano de `test_integridad_esquema.py`, que vigila la estructura.
Aquí se vigila el contenido: que los precios sean posibles, que las
unidades no mientan, que las tablas de hechos tengan hechos y que las
fuentes concuerden entre sí.

Cada test nació de un defecto real de la auditoría de datos de
2026-08. Si alguno vuelve a fallar, es que el defecto ha vuelto.
"""

from sqlalchemy import text

from tests.conftest import requires_db


@requires_db
def test_ningun_precio_es_negativo(db_conn):
    """Un precio negativo no existe en ningún mercado.

    Había 22.166 filas en 19 empresas, con un mínimo de −246.247.
    Venían del ajuste retroactivo por dividendos que aplicaba yfinance
    con `auto_adjust=True`, guardado en la columna `close`.
    """
    negativos = db_conn.execute(
        text("SELECT count(*) FROM equity.price_daily WHERE close < 0")
    ).scalar()
    assert negativos == 0, f"{negativos} precios negativos"


@requires_db
def test_el_maximo_del_dia_no_baja_del_minimo(db_conn):
    """Una vela con `high < low` es imposible.

    Había 10.672 filas así, efecto colateral de los precios negativos:
    al invertirse el signo, se invierte el orden.
    """
    imposibles = db_conn.execute(
        text("SELECT count(*) FROM equity.price_daily WHERE high < low")
    ).scalar()
    assert imposibles == 0, f"{imposibles} velas con high < low"


@requires_db
def test_el_cierre_cae_dentro_del_rango_del_dia(db_conn):
    """El cierre tiene que estar entre el mínimo y el máximo."""
    fuera = db_conn.execute(
        text(
            "SELECT count(*) FROM equity.price_daily "
            "WHERE close < low OR close > high"
        )
    ).scalar()
    assert fuera == 0, f"{fuera} cierres fuera del rango"


@requires_db
def test_las_unidades_declaradas_cuadran_con_la_magnitud(db_conn):
    """`GDP_NOMINAL` decía `billion_usd` con valores en USD absolutos.

    La mediana era 8,2e9: quien confiara en la etiqueta se equivocaba
    por un factor de mil millones.
    """
    from stonks.quality_datos import _RANGOS_UNIDAD

    filas = db_conn.execute(
        text(
            "SELECT i.code, i.unit, "
            "  percentile_cont(0.5) WITHIN GROUP "
            "    (ORDER BY abs(d.value)) "
            "FROM macro.data_point d "
            "JOIN macro.series s ON s.id = d.series_id "
            "JOIN macro.indicator i ON i.id = s.indicator_id "
            "WHERE i.unit IS NOT NULL AND d.value <> 0 "
            "GROUP BY i.code, i.unit HAVING count(*) > 100"
        )
    ).fetchall()

    implausibles = []
    for code, unidad, mediana in filas:
        rango = _RANGOS_UNIDAD.get(unidad)
        if rango is None or mediana is None:
            continue
        if not rango[0] <= float(mediana) <= rango[1]:
            implausibles.append(f"{code} ({unidad}): {float(mediana):.3g}")

    assert implausibles == [], f"unidades implausibles: {implausibles}"


@requires_db
def test_las_tablas_de_hechos_tienen_hechos(db_conn):
    """Una tabla de hechos vacía es un fetcher que falla en silencio.

    `crypto.price_intraday`, `forex.rate_intraday` y
    `commodity.price_intraday` estuvieron a cero mientras su fetcher
    fallaba doce veces seguidas sin que nada lo dijera.
    """
    from stonks.quality_datos import _MINIMOS

    bajas = []
    for tabla, minimo in sorted(_MINIMOS.items()):
        n = db_conn.execute(
            text(f"SELECT count(*) FROM {tabla}")
        ).scalar()
        if n < minimo:
            bajas.append(f"{tabla}: {n} de {minimo}")

    assert bajas == [], f"tablas por debajo del mínimo: {bajas}"


@requires_db
def test_ninguna_serie_de_crypto_empalma_dos_activos(db_conn):
    """Cuatro `coin_id` contenían dos monedas distintas.

    COMP tenía un bloque de 2018-2022 con máximo 0,0033 y otro de 2026
    con 17,49: el primero no podía ser Compound, que salió en junio de
    2020 y cotiza en dólares.
    """
    empalmes = db_conn.execute(
        text(
            "WITH saltos AS ("
            "  SELECT c.symbol, p.date, "
            "    p.date - lag(p.date) OVER w AS hueco, "
            "    p.close, lag(p.close) OVER w AS previo "
            "  FROM crypto.price_daily p "
            "  JOIN crypto.coin c ON c.id = p.coin_id "
            "  WHERE p.close > 0 "
            "  WINDOW w AS (PARTITION BY p.coin_id ORDER BY p.date)) "
            "SELECT symbol, hueco FROM saltos "
            "WHERE hueco > 90 AND previo > 0 "
            "  AND (close / previo > 100 OR close / previo < 0.01)"
        )
    ).fetchall()
    assert empalmes == [], f"series empalmadas: {empalmes}"


@requires_db
def test_ningun_dominio_incumple_su_sla_de_frescura(db_conn):
    """El SLA estaba escrito en prosa y nadie lo comprobaba."""
    from stonks.quality_datos import _SLA

    fuera = []
    for _dominio, tabla, columna, maximo in _SLA:
        dias = db_conn.execute(
            text(f"SELECT CURRENT_DATE - max({columna}) FROM {tabla}")
        ).scalar()
        if dias is not None and int(dias) > maximo:
            fuera.append(f"{tabla}: {int(dias)} días (máx {maximo})")

    assert fuera == [], f"fuera de SLA: {fuera}"


@requires_db
def test_el_world_bank_y_el_fmi_miden_lo_mismo(db_conn):
    """Dos organismos midiendo el PIB per cápita deben coincidir.

    Es la prueba directa de veracidad: si divergen mucho, uno de los
    dos está mal cargado. En la auditoría el desvío medio era del
    3,57 % sobre 190 países, lo esperable entre metodologías.
    """
    fila = db_conn.execute(
        text(
            "WITH wb AS ("
            "  SELECT s.country_code, d.date, d.value v "
            "  FROM macro.data_point d "
            "  JOIN macro.series s ON s.id = d.series_id "
            "  JOIN macro.indicator i ON i.id = s.indicator_id "
            "  WHERE i.code = 'GDP_PER_CAPITA' AND NOT d.is_forecast), "
            "imf AS ("
            "  SELECT s.country_code, d.date, d.value v "
            "  FROM macro.data_point d "
            "  JOIN macro.series s ON s.id = d.series_id "
            "  JOIN macro.indicator i ON i.id = s.indicator_id "
            "  WHERE i.code = 'IMF_NGDPDPC' AND NOT d.is_forecast) "
            "SELECT count(*), "
            "  avg(abs(wb.v - imf.v) / nullif(abs(imf.v), 0)) * 100 "
            "FROM wb JOIN imf "
            "  ON wb.country_code = imf.country_code "
            " AND wb.date = imf.date"
        )
    ).first()

    comparadas, desvio = fila
    assert comparadas > 100, "muy pocas observaciones para comparar"
    assert float(desvio) < 15, (
        f"desvío medio del {float(desvio):.1f}% entre World Bank y FMI"
    )


@requires_db
def test_los_precios_no_se_truncan_a_cero(db_conn):
    """`NUMERIC(14,4)` mandaba a cero las acciones sub-céntimo.

    Eran 29.443 filas en 48 empresas: HCMC, MMEX y GTCH cotizan a
    0,0001 $, que con cuatro decimales es indistinguible de nada.
    """
    escala = db_conn.execute(
        text(
            "SELECT numeric_scale FROM information_schema.columns "
            "WHERE table_schema = 'equity' "
            "AND table_name = 'price_daily' AND column_name = 'close'"
        )
    ).scalar()
    assert escala >= 10, f"escala insuficiente: {escala} decimales"


@requires_db
def test_el_cierre_ajustado_esta_poblado(db_conn):
    """`adj_close` estuvo vacía en los 24 millones de filas.

    yfinance aplica `auto_adjust=True` por defecto: devuelve el cierre
    ya ajustado en `Close` y no devuelve `Adj Close`. La columna
    `close` guardaba entonces el ajustado, y la que decía llamarse
    ajustada estaba a nulo.

    Se mide solo sobre las empresas que siguen cotizando: las
    deslistadas conservan la serie antigua porque su ticker ya no
    resuelve en yfinance y no hay forma de volver a descargarla (2.279
    empresas, el 18,6 % de las filas).

    Aun asi el listón no es del 100 %: tras la recarga el valor
    medido es del 90,4 %. El resto son tramos antiguos que yfinance
    ya no sirve ni con `period="max"`. El umbral está justo por debajo
    de lo medido para detectar una regresión, no para exigir una
    perfección que la fuente no da.
    """
    total, con_adj = db_conn.execute(
        text(
            "SELECT count(*), count(p.adj_close) "
            "FROM equity.price_daily p "
            "WHERE EXISTS ("
            "  SELECT 1 FROM equity.price_daily r "
            "  WHERE r.company_id = p.company_id "
            "  AND r.date > CURRENT_DATE - 30)"
        )
    ).first()
    pct = 100.0 * con_adj / total if total else 0
    assert pct > 85, (
        f"solo el {pct:.1f}% de las filas de empresas activas "
        "tiene adj_close"
    )


# ── Capa gold: lógica de negocio ─────────────────


@requires_db
def test_los_marts_se_recrean_en_cada_build(db_conn):
    """`CREATE MV IF NOT EXISTS` los congelaba para siempre.

    Once de los catorce marts conservaban la definición SQL con la que
    se crearon: cambiar `gold/build.py` no tenía ningún efecto y el
    build terminaba diciendo que todo había ido bien. No había forma
    de saber si el SQL del repositorio era el que estaba en la base.
    """
    import inspect

    from stonks.gold import build

    fuente = inspect.getsource(build)
    assert "CREATE MATERIALIZED VIEW IF NOT EXISTS" not in fuente.replace(
        "`CREATE MATERIALIZED VIEW IF NOT EXISTS`", ""
    ), "algún mart volvería a congelarse"


@requires_db
def test_ninguna_empresa_cotiza_antes_de_existir(db_conn):
    """`mart_company_macro` era un producto cartesiano.

    El JOIN emparejaba solo por país, sin noción temporal: el mart iba
    de 1750 a 2031 y el 43 % de sus filas eran anteriores a 1900, con
    Apple cotizando en el siglo XVIII.
    """
    imposibles = db_conn.execute(
        text(
            "SELECT count(*) FROM gold.mart_company_macro WHERE year < 1900"
        )
    ).scalar()
    assert imposibles == 0, f"{imposibles} filas anteriores a 1900"


@requires_db
def test_el_calendario_bursatil_no_cuenta_fines_de_semana(db_conn):
    """`is_trading_day` estaba puesto a TRUE a ciegas.

    Los 6.740 fines de semana figuraban como hábiles, y quien contara
    días de mercado obtenía 365 al año en lugar de ~252: las
    anualizaciones de volatilidad y de Sharpe salían desviadas un 20 %.
    """
    findes = db_conn.execute(
        text(
            "SELECT count(*) FROM gold.dim_date "
            "WHERE day_of_week IN (6, 7) AND is_trading_day"
        )
    ).scalar()
    assert findes == 0, f"{findes} fines de semana marcados como hábiles"

    # Un año bursátil estadounidense tiene entre 250 y 253 sesiones.
    sesiones = db_conn.execute(
        text(
            "SELECT count(*) FROM gold.dim_date "
            "WHERE year = 2024 AND is_trading_day"
        )
    ).scalar()
    assert 245 <= sesiones <= 255, f"2024 tiene {sesiones} sesiones"


@requires_db
def test_los_marts_macro_distinguen_las_proyecciones(db_conn):
    """`is_forecast` no llegaba a gold.

    La primera auditoría añadió la marca a `macro.data_point`, pero
    `gold/build.py` no la mencionaba: `stonks world ESP` mostraba la
    previsión del FMI para 2026 igual que un dato realizado.
    """
    # `information_schema.columns` no lista las vistas
    # materializadas; hay que ir a pg_attribute.
    tiene = db_conn.execute(
        text(
            "SELECT count(*) FROM pg_attribute a "
            "JOIN pg_class c ON c.oid = a.attrelid "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'gold' "
            "AND c.relname = 'mart_country_year' "
            "AND a.attname = 'is_forecast' AND a.attnum > 0"
        )
    ).scalar()
    assert tiene == 1, "mart_country_year no distingue las proyecciones"

    proyectados = db_conn.execute(
        text(
            "SELECT count(*) FROM gold.mart_country_year WHERE is_forecast"
        )
    ).scalar()
    assert proyectados > 0, "ningún año marcado como proyección"


@requires_db
def test_el_resumen_de_crypto_cubre_todo_el_universo(db_conn):
    """`mart_crypto_overview` devolvía 4 monedas de 246.

    Filtraba por `max(date)` global en vez de por moneda, y como no
    todas tienen barra el mismo día el JOIN interno eliminaba el 98 %.
    """
    en_mart, en_universo = db_conn.execute(
        text(
            "SELECT (SELECT count(*) FROM gold.mart_crypto_overview), "
            "       (SELECT count(DISTINCT coin_id) "
            "        FROM crypto.price_daily)"
        )
    ).first()
    cobertura = 100.0 * en_mart / en_universo if en_universo else 0
    assert cobertura > 90, (
        f"el mart solo cubre el {cobertura:.0f}% de las monedas"
    )


@requires_db
def test_la_capitalizacion_esta_en_dolares(db_conn):
    """`market_cap_usd` contenía la capitalización en moneda local.

    Toyota figuraba con 34,5 billones, que son yenes; su valor real
    ronda los 230.000 millones de dólares. La media de las coreanas
    salía a 148.667 "miles de millones de dólares".
    """
    # Ninguna empresa del mundo vale más de 20 billones de dólares.
    disparadas = db_conn.execute(
        text(
            "SELECT count(*) FROM equity.company "
            "WHERE market_cap_usd > 2e13"
        )
    ).scalar()
    assert disparadas == 0, (
        f"{disparadas} capitalizaciones imposibles: siguen en moneda local"
    )


@requires_db
def test_el_point_in_time_no_tiene_fechas_imposibles(db_conn):
    """Había 272 filas con el periodo cerrando en 2105 o en 6016.

    Son erratas de las propias presentaciones ante la SEC, pero
    envenenan cualquier consulta point-in-time por rango de fechas.
    """
    imposibles = db_conn.execute(
        text(
            "SELECT count(*) FROM gold.fact_fundamentals_pit "
            "WHERE period_end_date < DATE '1970-01-01' "
            "   OR period_end_date > CURRENT_DATE + 400 "
            "   OR filed_date > CURRENT_DATE"
        )
    ).scalar()
    assert imposibles == 0, f"{imposibles} fechas imposibles en el PIT"


# ── La documentación describe la base ────────────


@requires_db
def test_todas_las_tablas_estan_documentadas(db_conn):
    """El diccionario se había quedado 23 tablas por detrás.

    Faltaba todo lo que añadieron las dos primeras auditorías
    (`ref.area`, `ref.legal_entity`, `deriv.cot_*`, `realestate.*`,
    `calendar.*`, las cuatro intraday y los cuatro marts nuevos), y
    seguía describiendo `alt.housing_index`, retirada.

    Se regenera con `scripts/gen_data_dictionary.py`.
    """
    from pathlib import Path

    diccionario = (
        Path(__file__).parent.parent / "docs" / "DATA_DICTIONARY.md"
    )
    texto = diccionario.read_text(encoding="utf-8")

    tablas = db_conn.execute(
        text(
            "SELECT n.nspname || '.' || c.relname "
            "FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE c.relkind IN ('r', 'p', 'm') "
            "AND n.nspname NOT IN "
            "    ('pg_catalog', 'information_schema', 'pg_toast') "
            "AND c.relname NOT LIKE '%_intraday_2%' "
            "ORDER BY 1"
        )
    ).fetchall()

    faltan = [t[0] for t in tablas if t[0] not in texto]
    assert faltan == [], f"tablas sin documentar: {faltan}"


@requires_db
def test_todos_los_indicadores_declaran_su_unidad(db_conn):
    """Ni un solo `macro.indicator` con `unit` a NULL.

    Eran 1.670 de 1.835 (el 91 %), y mientras lo fueran el check de
    plausibilidad de unidades solo podía auditar el 9 % del catálogo.

    `desconocida` es una respuesta válida —hay indicadores cuya unidad
    no dice ni el nombre ni la fuente—, pero NULL no lo es: no
    distingue "no se sabe" de "no se ha mirado". Lo rellena
    `stonks.seed.unidades.aplicar_unidades()`, que corre dentro de
    `seed_all()`.
    """
    sin_unidad, desconocidas, total = db_conn.execute(
        text(
            "SELECT count(*) FILTER (WHERE unit IS NULL), "
            "       count(*) FILTER (WHERE unit = 'desconocida'), "
            "       count(*) FROM macro.indicator"
        )
    ).first()

    assert sin_unidad == 0, (
        f"{sin_unidad} indicadores de {total} sin unidad declarada; "
        "ejecuta stonks.seed.unidades.aplicar_unidades()"
    )
    # Y que la etiqueta de escape no se convierta en la respuesta
    # cómoda para todo: rondaba el 2 % al cerrar la certificación.
    assert desconocidas < total * 0.10, (
        f"{desconocidas} de {total} indicadores marcados como "
        "'desconocida': la inferencia de unidades ha dejado de "
        "funcionar"
    )


@requires_db
def test_los_paises_tienen_region(db_conn):
    """`ref.country.region` poblada, y en un solo idioma.

    Tenía UN valor de 250 filas, así que no había mapa ni agregado por
    continente posible: de lo primero que pide cualquier tablero.

    La segunda mitad importa igual: la única fila que había decía
    "Europe" mientras el resto pasó a "Europa" al cargar la
    clasificación M49, y un `GROUP BY region` habría partido el
    continente en dos sin que nadie lo notara.
    """
    sin_region, total = db_conn.execute(
        text(
            "SELECT count(*) FILTER (WHERE region IS NULL), count(*) "
            "FROM ref.country"
        )
    ).first()

    assert sin_region == 0, (
        f"{sin_region} países de {total} sin región; ejecuta "
        "stonks.seed.reference.seed_regiones()"
    )

    regiones = {
        f[0]
        for f in db_conn.execute(
            text("SELECT DISTINCT region FROM ref.country")
        ).fetchall()
    }
    # Las seis de la M49 en español. Si aparece una séptima es que se
    # ha colado otra nomenclatura.
    esperadas = {
        "África",
        "América",
        "Asia",
        "Europa",
        "Oceanía",
        "Antártida",
    }
    assert regiones <= esperadas, (
        f"regiones fuera de la clasificación M49: {regiones - esperadas}"
    )


@requires_db
def test_el_indice_equiponderado_no_tiene_saltos_imposibles(db_conn):
    """Ningún retorno diario del pool por encima del ±25 %.

    La serie equiponderada llegó a marcar un +2.539 % en un día porque
    `avg()` no tiene defensa frente a un valor extremo: bastaba una
    vela corrupta de las 494 del pool. Compuesta daba un índice de
    10⁵⁰, y cualquier backtest que la usara era ficción.

    El ±25 % es holgado a propósito: el peor día real de la serie es
    un 12,5 %, y ni el lunes negro de 1987 llegó al 25 % en un
    equiponderado del S&P 500.
    """
    peor = db_conn.execute(
        text(
            "SELECT max(abs(ret)) FROM gold.mart_benchmark_returns "
            "WHERE method = 'equal_weight'"
        )
    ).scalar()

    assert float(peor) <= 0.25, (
        f"el peor día del equiponderado es {float(peor) * 100:.1f} %: "
        "hay una vela corrupta entre los miembros del pool"
    )
