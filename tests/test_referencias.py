"""Contraste de la base contra valores reales conocidos.

Los otros tests comprueban que los datos son **coherentes**: que un
precio no es negativo, que un balance cuadra, que una unidad tiene la
magnitud que declara. Eso detecta corrupción, pero no detecta que una
serie entera esté equivocada de forma consistente.

Estos comprueban que los datos son **ciertos**, contra valores que se
verificaron a mano en la fuente original. Es la única forma de
distinguir "la base es internamente coherente" de "la base dice la
verdad".

El corpus vive en `tests/referencias.yml`, con la URL o la publicación
donde se comprobó cada cifra para poder repetirlo dentro de un año.
"""

from pathlib import Path

import pytest
import yaml
from sqlalchemy import text

from tests.conftest import requires_db

CORPUS = Path(__file__).parent / "referencias.yml"


def _cargar() -> list[dict]:
    """Leer el corpus de referencias."""
    with open(CORPUS, encoding="utf-8") as f:
        return yaml.safe_load(f) or []


REFERENCIAS = _cargar()


def _identificador(ref: dict) -> str:
    """Nombre legible para el informe de pytest."""
    return f"{ref['dominio']}: {ref['descripcion']}"


@requires_db
@pytest.mark.parametrize(
    "ref", REFERENCIAS, ids=[_identificador(r) for r in REFERENCIAS]
)
def test_la_base_coincide_con_la_realidad(db_conn, ref):
    """Contrastar un dato de la base contra su valor real.

    Si este test falla, o bien la carga está mal, o bien la fuente ha
    revisado la cifra. Las dos posibilidades merecen mirarse: la
    segunda no es un error, pero sí una decisión sobre qué vintage se
    quiere conservar.
    """
    obtenido = db_conn.execute(text(ref["consulta"])).scalar()

    assert obtenido is not None, (
        f"la consulta no devolvió ningún valor.\n"
        f"Referencia: {ref['referencia']}"
    )

    esperado = float(ref["esperado"])
    obtenido = float(obtenido)
    desvio = abs(obtenido - esperado) / abs(esperado) * 100

    assert desvio <= ref["tolerancia_pct"], (
        f"{ref['descripcion']}\n"
        f"  esperado : {esperado:,.4f}\n"
        f"  obtenido : {obtenido:,.4f}\n"
        f"  desvío   : {desvio:.2f}% "
        f"(tolerancia {ref['tolerancia_pct']}%)\n"
        f"  fuente   : {ref['referencia']}"
    )


# ─── Dominios sin referencia pública fácil ─────────────────────────
# Para opciones, accionistas e insiders no hay una cifra publicada que
# contrastar: son fotos de un momento que nadie archiva. Lo que sí se
# puede comprobar es que guarden algo posible, y eso es lo que hacen
# los tres tests siguientes. Se declaran como lo que son —
# verificación estructural, no contraste externo— para que en la
# certificación no se cuenten como lo segundo.


@requires_db
def test_los_strikes_rodean_el_precio_del_subyacente(db_conn):
    """Una cadena de opciones cubre precios a ambos lados del spot.

    Si todos los strikes quedaran por encima o por debajo, o el precio
    del subyacente estuviera en otra unidad, esto lo delata.
    """
    filas = db_conn.execute(
        text(
            "SELECT c.ticker, min(o.strike), max(o.strike), "
            "  (SELECT p.close FROM equity.price_daily p "
            "    WHERE p.company_id = o.company_id "
            "    ORDER BY p.date DESC LIMIT 1) AS spot "
            "FROM deriv.option_snapshot o "
            "JOIN equity.company c ON c.id = o.company_id "
            "GROUP BY c.ticker, o.company_id "
            "HAVING count(*) > 50"
        )
    ).fetchall()

    assert filas, "no hay cadenas de opciones que comprobar"

    fuera = [
        f"{t}: strikes {float(mn):.2f}-{float(mx):.2f}, spot {float(s):.2f}"
        for t, mn, mx, s in filas
        if s and not (float(mn) <= float(s) <= float(mx))
    ]
    # Un valor recién desplomado puede dejar el spot fuera del rango de
    # strikes heredado, así que se tolera una minoría.
    assert len(fuera) <= len(filas) * 0.1, (
        f"{len(fuera)} de {len(filas)} cadenas no rodean su subyacente:\n"
        + "\n".join(fuera[:5])
    )


@requires_db
def test_las_participaciones_estan_en_porcentaje_y_son_posibles(db_conn):
    """`pct_held` en 0-100 y coherente con el capital de la empresa.

    Ningún accionista puede tener más del 100 % de una empresa, y esa
    parte se cumple sin excepciones.

    La suma por empresa es otra historia: en 17 de 3.525 empresas pasa
    del 100 %, con Duos Technologies llegando al 526 %. No es un error
    de carga sino de la fuente: Yahoo calcula `pctHeld` contra un
    número de acciones desactualizado, y en las small caps que han
    hecho un contrasplit el denominador se queda corto. Por eso el
    test acota la proporción de empresas afectadas en vez de exigir
    cero: sirve para detectar que el problema se extienda, no para
    fingir que no existe.
    """
    peor_individual = db_conn.execute(
        text("SELECT max(pct_held) FROM equity.holder")
    ).scalar()

    assert float(peor_individual) <= 100, (
        f"hay un accionista con el {float(peor_individual):.1f} % de "
        "una empresa"
    )
    # El reverso: si volvieran a guardarse fracciones, el máximo de
    # toda la tabla no llegaría ni a 1.
    assert float(peor_individual) > 1, (
        f"el mayor pct_held es {float(peor_individual):.4f}: parece "
        "que se volvieron a guardar fracciones"
    )

    total, pasan = db_conn.execute(
        text(
            "WITH ultima AS ("
            "  SELECT h.company_id, sum(h.pct_held) AS suma "
            "  FROM equity.holder h "
            "  WHERE h.holder_type = 'institutional' "
            "    AND h.snapshot_date = ("
            "      SELECT max(h2.snapshot_date) FROM equity.holder h2 "
            "      WHERE h2.company_id = h.company_id) "
            "  GROUP BY h.company_id) "
            "SELECT count(*), count(*) FILTER (WHERE suma > 100) "
            "FROM ultima"
        )
    ).first()

    assert pasan <= total * 0.02, (
        f"{pasan} de {total} empresas suman más del 100 % en manos "
        "institucionales; el ruido de la fuente rondaba las 17"
    )


@requires_db
def test_los_importes_de_insiders_son_posibles(db_conn):
    """El precio implícito de una operación no puede ser absurdo.

    Se compara el importe dividido entre las acciones contra el precio
    de mercado de ese día. Por debajo es normal —las opciones se
    ejercen a un strike inferior—, pero cien veces por encima no
    corresponde a ninguna convención: es basura de la fuente, como los
    23,5 millones por acción que Yahoo daba para HYEX.
    """
    imposibles = db_conn.execute(
        text(
            "WITH implicito AS ("
            "  SELECT i.value_usd / nullif(i.shares, 0) AS precio, "
            "    (SELECT p.close FROM equity.price_daily p "
            "      WHERE p.company_id = i.company_id "
            "        AND p.date <= i.start_date "
            "      ORDER BY p.date DESC LIMIT 1) AS mercado "
            "  FROM equity.insider_transaction i "
            "  WHERE i.value_usd IS NOT NULL AND i.shares > 0) "
            "SELECT count(*) FROM implicito "
            "WHERE mercado > 0 AND precio > mercado * 100"
        )
    ).scalar()

    assert imposibles == 0, (
        f"{imposibles} operaciones de insider con un precio implícito "
        "de más de cien veces el de mercado"
    )


@requires_db
def test_el_corpus_cubre_los_dominios_con_datos(db_conn):
    """Todo esquema con datos propios debe tener al menos una
    referencia.

    Es lo que impide que un dominio entero se quede sin contrastar,
    como estaban `agri`, `energy`, `deriv` y `realestate` hasta la
    auditoría de certificación.
    """
    # Esquemas que no contienen datos de mercado, sino metadatos,
    # catálogos, aterrizaje crudo o vistas derivadas del resto.
    SIN_REFERENCIA_PROPIA = {
        "meta",      # auditoría de la propia carga
        "ref",       # catálogos (países, divisas, bolsas)
        "bronze",    # copia cruda de la fuente
        "gold",      # se deriva de silver, que sí se contrasta
        "public",
        "calendar",  # fechas de publicación, no magnitudes
        "alt",       # sentimiento, sin referencia pública estable
    }

    con_datos = {
        fila[0]
        for fila in db_conn.execute(
            text(
                "SELECT DISTINCT n.nspname FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE c.relkind = 'r' AND c.reltuples > 100 "
                "AND n.nspname NOT IN "
                "    ('pg_catalog', 'information_schema', 'pg_toast')"
            )
        ).fetchall()
    } - SIN_REFERENCIA_PROPIA

    cubiertos = {r["dominio"] for r in REFERENCIAS}
    faltan = con_datos - cubiertos

    assert faltan == set(), (
        f"esquemas con datos y sin ninguna referencia externa: "
        f"{sorted(faltan)}"
    )


# ─── Certificación ─────────────────────────────────────────────────


@requires_db
def test_ninguna_tabla_se_queda_sin_certificar(db_conn):
    """Toda tabla de datos declara cómo se ha verificado.

    Es la pieza que sostiene el resto: hace imposible añadir una tabla
    y olvidarse de decir cómo se comprueba. Si falla, o bien añades un
    valor a `tests/referencias.yml` —lo preferible— o bien declaras la
    tabla en `config/certificacion.yml` con su método o su motivo.

    Recertifica antes de mirar, porque la foto guardada envejece en
    cuanto alguien crea una tabla.
    """
    from stonks.certificacion import SIN_CERTIFICAR, certificar

    pendientes = [
        r["tabla"]
        for r in certificar(por="pytest")
        if r["estado"] == SIN_CERTIFICAR
    ]

    assert pendientes == [], (
        "tablas sin declarar cómo se verifican: "
        f"{pendientes}"
    )


@requires_db
def test_lo_no_verificable_lleva_motivo(db_conn):
    """Declarar algo como no verificable exige explicar por qué.

    Sin esta comprobación, `no_verificable` sería la salida cómoda
    para cualquier tabla incómoda.
    """
    sin_motivo = db_conn.execute(
        text(
            "SELECT schema_name || '.' || table_name "
            "FROM meta.table_certification "
            "WHERE estado = 'no_verificable' "
            "  AND (motivo IS NULL OR length(motivo) < 40)"
        )
    ).fetchall()

    assert sin_motivo == [], (
        f"tablas marcadas como no verificables sin motivo escrito: "
        f"{[f[0] for f in sin_motivo]}"
    )


@requires_db
def test_los_precios_cuadran_con_una_segunda_fuente(db_conn):
    """Contrastar una muestra de precios contra Tiingo.

    Todos los precios de renta variable vienen de yfinance, así que un
    error suyo sería indetectable desde dentro: la base estaría
    perfectamente de acuerdo consigo misma y equivocada. Esto es lo
    único que rompe ese círculo.

    Queda en `skip` mientras no exista `STONKS_TIINGO_KEY` (gratuita en
    tiingo.com/account/api/token) y se activa solo cuando se registre.
    """
    from stonks.fetchers.tiingo import SinClaveTiingo, TiingoFetcher

    try:
        salida = TiingoFetcher().comparar_precios(muestra=10)
    except SinClaveTiingo:
        pytest.skip(
            "sin STONKS_TIINGO_KEY: no hay segunda fuente de precios"
        )

    assert salida["comparados"] > 0, (
        "Tiingo no devolvió ningún precio comparable"
    )
    # Dos proveedores nunca coinciden al céntimo, pero sí en el 95 % de
    # los cierres si ambos están bien.
    limite = salida["comparados"] * 0.05
    assert salida["divergentes"] <= limite, (
        f"{salida['divergentes']} de {salida['comparados']} precios "
        f"divergen más del 1 % respecto a Tiingo. "
        f"El peor: {salida['peor']}"
    )


@requires_db
def test_los_ratios_no_mezclan_dos_monedas(db_conn):
    """Precio y contabilidad, o en la misma moneda o no hay ratio.

    El precio está en la moneda de cotización y las cuentas en la de
    reporte, y no son la misma: Central Puerto cotiza en dólares y
    reporta en pesos, Novo Nordisk reporta en coronas y su ADR cotiza
    en dólares. Dividir uno entre otro daba PER de 0,006 y de 2,0
    —frente a 12,7 en Copenhague con el mismo BPA—, y esos valores
    salen los primeros al ordenar por PER: justo donde uno busca
    gangas.

    `equity.ratios_mv` los calcula ahora en dólares y deja el ratio a
    NULL cuando falta el tipo de cambio de cualquiera de las dos
    monedas. Este test comprueba las dos mitades de esa promesa.
    """
    mezclados = db_conn.execute(
        text(
            "SELECT count(*) FROM equity.ratios_mv "
            "WHERE moneda_coherente IS NOT TRUE "
            "  AND (pe_ratio IS NOT NULL OR pb_ratio IS NOT NULL)"
        )
    ).scalar()

    assert mezclados == 0, (
        f"{mezclados} filas con PER o P/VC calculado sin saber en qué "
        "moneda están las cuentas"
    )

    # Y el reverso: si el flag se pusiera a TRUE por defecto, el test
    # anterior pasaría sin comprobar nada.
    coherentes = db_conn.execute(
        text(
            "SELECT count(*) FROM equity.ratios_mv "
            "WHERE moneda_coherente IS FALSE"
        )
    ).scalar()
    assert coherentes > 0, (
        "ninguna fila marcada como incoherente: la bandera no se está "
        "calculando"
    )


@requires_db
def test_el_beneficio_por_accion_no_se_queda_congelado(db_conn):
    """El BPA guardado tiene que cuadrar con el beneficio declarado.

    Booking figuraba con un BPA de 165,57 cuando Yahoo ya daba 6,62
    tras el split, porque el fetcher de fundamentales hacía
    `if exists: continue` y no volvía a mirar un periodo ya cargado.
    Un split cambia todo el histórico de BPA, así que el dato se
    quedaba congelado para siempre y el PER salía 1,25 en un valor que
    cotiza a 31 veces beneficios.

    La comprobación es indirecta —`shares_outstanding` es el recuento
    de hoy, no el del cierre del ejercicio, y en las cotizadas con
    varias clases de acción sólo cuenta la cotizada—, así que el
    umbral es generoso: sólo caza desfases de orden de magnitud.
    """
    desfasados = db_conn.execute(
        text(
            "WITH ultimo AS ("
            "  SELECT DISTINCT ON (i.company_id) "
            "         i.eps_diluted, "
            "         i.net_income / nullif(c.shares_outstanding, 0) "
            "           AS implicito "
            "  FROM equity.income_statement i "
            "  JOIN equity.company c ON c.id = i.company_id "
            "  WHERE i.eps_diluted > 0 AND i.net_income > 0 "
            "    AND c.shares_outstanding > 0 "
            "    AND c.country_code = 'USA' AND c.ticker !~ '\\.' "
            "  ORDER BY i.company_id, i.period_end_date DESC NULLS LAST) "
            "SELECT count(*) FROM ultimo "
            "WHERE eps_diluted > implicito * 10"
        )
    ).scalar()

    assert desfasados == 0, (
        f"{desfasados} empresas estadounidenses con un BPA diez veces "
        "mayor que el que implica su beneficio: probable dato anterior "
        "a un split que nadie ha vuelto a cargar"
    )
