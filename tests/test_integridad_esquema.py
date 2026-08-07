"""Tests de las invariantes de diseño que fijó la auditoría 2026-08.

Son comprobaciones sobre la base viva: verifican que las correcciones
estructurales siguen en pie. Si alguien vuelve a añadir una tabla sin
índice en su clave foránea, o un timestamp sin zona horaria, estos
tests lo detectan antes de que llegue a producción.
"""

from sqlalchemy import text

from tests.conftest import requires_db


@requires_db
def test_toda_clave_foranea_tiene_indice(db_conn):
    """Una FK sin índice convierte cualquier filtro en seq scan.

    La auditoría encontró 31 columnas así, incluidos todos los
    `source_id`.
    """
    filas = db_conn.execute(
        text(
            "SELECT n.nspname || '.' || t.relname, a.attname "
            "FROM pg_constraint con "
            "JOIN pg_class t ON t.oid = con.conrelid "
            "JOIN pg_namespace n ON n.oid = t.relnamespace "
            "JOIN pg_attribute a ON a.attrelid = t.oid "
            "  AND a.attnum = con.conkey[1] "
            "WHERE con.contype = 'f' "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM pg_index i "
            "  WHERE i.indrelid = t.oid "
            "  AND i.indkey[0] = con.conkey[1]"
            ")"
        )
    ).fetchall()
    assert filas == [], f"FK sin índice: {filas}"


@requires_db
def test_ningun_timestamp_sin_zona_horaria(db_conn):
    """En una BD de mercados globales, un naive datetime es un bug."""
    filas = db_conn.execute(
        text(
            "SELECT table_schema || '.' || table_name || '.' "
            "       || column_name "
            "FROM information_schema.columns "
            "WHERE table_schema NOT IN "
            "      ('pg_catalog', 'information_schema') "
            "AND data_type = 'timestamp without time zone' "
            "AND table_name NOT LIKE 'price_intraday_2%'"
        )
    ).fetchall()
    assert filas == [], f"timestamps sin tz: {filas}"


@requires_db
def test_toda_tabla_tiene_clave_primaria(db_conn):
    filas = db_conn.execute(
        text(
            "SELECT n.nspname || '.' || c.relname "
            "FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE c.relkind IN ('r', 'p') "
            "AND n.nspname NOT IN "
            "    ('pg_catalog', 'information_schema') "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM pg_constraint k "
            "  WHERE k.conrelid = c.oid AND k.contype = 'p'"
            ")"
        )
    ).fetchall()
    assert filas == [], f"tablas sin PK: {filas}"


@requires_db
def test_comercio_valida_ambos_extremos(db_conn):
    """`partner_code` no tenía FK y `reporter_code` sí.

    Ahora ambos apuntan a `ref.area`, que es el superset de países que
    admite agregados ('WLD') e históricos ('CSK').
    """
    fks = db_conn.execute(
        text(
            "SELECT a.attname, cl.relname "
            "FROM pg_constraint con "
            "JOIN pg_class t ON t.oid = con.conrelid "
            "JOIN pg_class cl ON cl.oid = con.confrelid "
            "JOIN pg_attribute a ON a.attrelid = t.oid "
            "  AND a.attnum = con.conkey[1] "
            "WHERE con.contype = 'f' "
            "AND t.relname = 'flow'"
        )
    ).fetchall()
    destinos = dict(fks)
    assert destinos.get("reporter_code") == "area"
    assert destinos.get("partner_code") == "area"
    assert destinos.get("product_code") == "hs_product"


@requires_db
def test_no_hay_codigos_de_area_huerfanos(db_conn):
    huerfanos = db_conn.execute(
        text(
            "SELECT count(*) FROM trade.flow f "
            "WHERE NOT EXISTS ("
            "  SELECT 1 FROM ref.area a WHERE a.code = f.partner_code"
            ")"
        )
    ).scalar()
    assert huerfanos == 0


@requires_db
def test_las_proyecciones_macro_estan_marcadas(db_conn):
    """Sin `is_forecast`, un backtest usa datos del futuro.

    Toda observación con fecha posterior a hoy tiene que estar marcada
    como proyección.
    """
    sin_marcar = db_conn.execute(
        text(
            "SELECT count(*) FROM macro.data_point "
            "WHERE date > CURRENT_DATE AND NOT is_forecast"
        )
    ).scalar()
    assert sin_marcar == 0


@requires_db
def test_las_materializadas_pueden_refrescarse_en_concurrente(db_conn):
    """REFRESH CONCURRENTLY exige un índice único en cada MV."""
    sin_indice = db_conn.execute(
        text(
            "SELECT n.nspname || '.' || c.relname "
            "FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE c.relkind = 'm' "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM pg_index i "
            "  WHERE i.indrelid = c.oid AND i.indisunique"
            ")"
        )
    ).fetchall()
    assert sin_indice == [], f"MV sin índice único: {sin_indice}"


@requires_db
def test_los_importes_no_usan_coma_flotante(db_conn):
    """Los precios y los importes van en NUMERIC, nunca en float."""
    flotantes = db_conn.execute(
        text(
            "SELECT table_schema || '.' || table_name || '.' "
            "       || column_name "
            "FROM information_schema.columns "
            "WHERE table_schema NOT IN "
            "      ('pg_catalog', 'information_schema') "
            "AND data_type IN ('double precision', 'real')"
        )
    ).fetchall()
    assert flotantes == [], f"columnas float: {flotantes}"


@requires_db
def test_el_esquema_esta_al_dia_con_alembic(db_conn):
    """La causa raíz del desfase v0.4.0 era no tener migraciones."""
    version = db_conn.execute(
        text("SELECT version_num FROM meta.alembic_version")
    ).scalar()
    assert version, "la BD no está sellada con ninguna revisión"


@requires_db
def test_los_esquemas_declarados_existen(db_conn):
    """`realestate` estaba en SCHEMAS y en los docs pero no en la BD."""
    from stonks.db import SCHEMAS

    existentes = {
        fila[0]
        for fila in db_conn.execute(
            text("SELECT nspname FROM pg_namespace")
        ).fetchall()
    }
    faltan = set(SCHEMAS) - existentes
    assert not faltan, f"esquemas declarados sin crear: {faltan}"


@requires_db
def test_las_claves_de_los_marts_no_admiten_duplicados(db_conn):
    """Los índices únicos de gold dependen de claves del silver.

    `gold.mart_crypto_overview` se indexa por `symbol`. Al ampliar el
    universo a 260 monedas, CoinGecko trajo el mismo activo con su id
    antiguo y el nuevo (SNX como 'havven' y como
    'synthetix-network-token'), aparecieron símbolos duplicados y el
    refresco de la vista empezó a fallar cada noche.
    """
    duplicados = db_conn.execute(
        text(
            "SELECT symbol, count(*) FROM crypto.coin "
            "GROUP BY symbol HAVING count(*) > 1"
        )
    ).fetchall()
    assert duplicados == [], f"símbolos duplicados: {duplicados}"


@requires_db
def test_las_materializadas_de_gold_estan_pobladas(db_conn):
    """Una MV vacía suele significar que su SQL nunca se ejecutó.

    Así se detectaron `mart_etf_category` (leía una columna que no
    existe) y `mart_yield_curve` (asumía formato ancho).
    """
    vacias = []
    nombres = db_conn.execute(
        text(
            "SELECT n.nspname || '.' || c.relname "
            "FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE c.relkind = 'm' AND n.nspname = 'gold'"
        )
    ).fetchall()
    for (nombre,) in nombres:
        n = db_conn.execute(text(f"SELECT count(*) FROM {nombre}")).scalar()
        if n == 0:
            vacias.append(nombre)
    assert vacias == [], f"materializadas vacías: {vacias}"
