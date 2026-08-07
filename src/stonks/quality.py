"""Checks de calidad de datos → meta.data_quality.

Registra, por dominio, la cobertura (países, entidades), la frescura
(lag del dato más reciente), la integridad (NULLs, FKs huérfanas) y
la plausibilidad (outliers). Es informativo y se ejecuta al final de
build_gold. Idempotente: borra sus filas previas y reinserta.
"""

from datetime import datetime

from sqlalchemy import text

from stonks.db import engine
from stonks.logger import get_logger

logger = get_logger("stonks.quality")

# ─── 1. Cobertura por dominio ──────────────────────────────────────
# (dominio, entidad, consulta de conteo, consulta de año/fecha máx.)
_CHECKS = [
    (
        "world_panel",
        "gold.mart_country_year",
        "SELECT count(DISTINCT country_code) FROM gold.mart_country_year",
        "SELECT max(year) FROM gold.mart_country_year",
    ),
    (
        "trade",
        "trade.flow",
        "SELECT count(DISTINCT reporter_code) FROM trade.flow",
        "SELECT max(period) FROM trade.flow",
    ),
    (
        "energy",
        "energy.balance",
        "SELECT count(DISTINCT country_code) FROM energy.balance",
        "SELECT max(period) FROM energy.balance",
    ),
    (
        "macro",
        "macro.series",
        "SELECT count(DISTINCT country_code) FROM macro.series",
        "SELECT extract(year FROM max(date)) FROM macro.data_point",
    ),
    (
        "equity",
        "equity.price_daily",
        "SELECT count(DISTINCT company_id) FROM equity.price_daily",
        "SELECT max(date) FROM equity.price_daily",
    ),
    (
        "fi",
        "fi.yield_curve",
        "SELECT count(DISTINCT country_code) FROM fi.yield_curve",
        "SELECT max(date) FROM fi.yield_curve",
    ),
    (
        "commodity",
        "commodity.price_daily",
        "SELECT count(DISTINCT commodity_id) FROM commodity.price_daily",
        "SELECT max(date) FROM commodity.price_daily",
    ),
    (
        "forex",
        "forex.rate_daily",
        "SELECT count(DISTINCT pair_id) FROM forex.rate_daily",
        "SELECT max(date) FROM forex.rate_daily",
    ),
    (
        "agri",
        "agri.production",
        "SELECT count(DISTINCT country_code) FROM agri.production",
        "SELECT max(period) FROM agri.production",
    ),
    (
        "gold_pit",
        "gold.fact_fundamentals_pit",
        "SELECT count(DISTINCT company_id) FROM gold.fact_fundamentals_pit",
        "SELECT max(filed_date) FROM gold.fact_fundamentals_pit",
    ),
]

# ─── 2. Auditoría de NULLs críticos ───────────────────────────────
# (dominio, tabla, columna que debería estar rellena, total query)
_NULL_AUDIT = [
    (
        "equity",
        "equity.company",
        "country_code",
        "SELECT count(*) FROM equity.company",
    ),
    (
        "equity",
        "equity.company",
        "sector_id",
        "SELECT count(*) FROM equity.company",
    ),
    (
        "macro",
        "macro.series",
        "country_code",
        "SELECT count(*) FROM macro.series",
    ),
    (
        "gold",
        "gold.dim_company",
        "sector_name",
        "SELECT count(*) FROM gold.dim_company",
    ),
    (
        "gold",
        "gold.dim_company",
        "country_code",
        "SELECT count(*) FROM gold.dim_company",
    ),
]

# ─── 3. FKs huérfanas ─────────────────────────────────────────────
# (dominio, descripción, query que devuelve nº de huérfanas)
_ORPHAN_CHECKS = [
    (
        "equity",
        "price_daily→company",
        "SELECT count(*) FROM equity.price_daily pd "
        "LEFT JOIN equity.company c ON c.id=pd.company_id "
        "WHERE c.id IS NULL",
    ),
    (
        "macro",
        "data_point→series",
        "SELECT count(*) FROM macro.data_point dp "
        "LEFT JOIN macro.series s ON s.id=dp.series_id "
        "WHERE s.id IS NULL",
    ),
    (
        "trade",
        "flow.reporter→country",
        "SELECT count(*) FROM trade.flow f "
        "LEFT JOIN ref.country c ON c.code=f.reporter_code "
        "WHERE c.code IS NULL",
    ),
    (
        "gold_pit",
        "pit→company",
        "SELECT count(*) FROM gold.fact_fundamentals_pit p "
        "LEFT JOIN equity.company c ON c.id=p.company_id "
        "WHERE c.id IS NULL",
    ),
    (
        "macro",
        "vintage→series",
        "SELECT count(*) FROM macro.data_point_vintage v "
        "LEFT JOIN macro.series s ON s.id=v.series_id "
        "WHERE s.id IS NULL",
    ),
]

# ─── 4. Outliers (rangos plausibles) ───────────────────────────────
# (dominio, descripción, query que devuelve nº fuera de rango)
_OUTLIER_CHECKS = [
    (
        "world_panel",
        "gdp_per_capita fuera de 100-200k",
        "SELECT count(*) FROM gold.mart_country_year "
        "WHERE gdp_per_capita_usd IS NOT NULL "
        "AND gdp_per_capita_usd NOT BETWEEN 100 AND 200000",
    ),
    (
        "world_panel",
        "inflación fuera de -30..1000",
        "SELECT count(*) FROM gold.mart_country_year "
        "WHERE inflation_pct IS NOT NULL "
        "AND inflation_pct NOT BETWEEN -30 AND 1000",
    ),
    (
        "world_panel",
        "paro fuera de 0..99",
        "SELECT count(*) FROM gold.mart_country_year "
        "WHERE unemployment_pct IS NOT NULL "
        "AND unemployment_pct NOT BETWEEN 0 AND 99",
    ),
    (
        "equity",
        "precio ≤ 0",
        "SELECT count(*) FROM equity.price_daily WHERE close <= 0",
    ),
    (
        "fi",
        "yield fuera de -5..50",
        "SELECT count(*) FROM fi.yield_curve "
        "WHERE yield_pct IS NOT NULL "
        "AND yield_pct NOT BETWEEN -5 AND 50",
    ),
]


def check_world_quality() -> dict:
    """Calcular cobertura/frescura por dominio y guardar en meta."""
    resumen: dict[str, dict] = {}
    domains = [c[0] for c in _CHECKS]
    with engine.begin() as conn:
        conn.execute(
            text(
                "DELETE FROM meta.data_quality WHERE domain IN "
                + "("
                + ",".join(f"'{d}'" for d in domains)
                + ")"
            )
        )
        for domain, entidad, q_cnt, q_fresh in _CHECKS:
            try:
                cnt = conn.execute(text(q_cnt)).scalar() or 0
                anio = conn.execute(text(q_fresh)).scalar()
                target = (
                    200
                    if domain
                    in (
                        "world_panel",
                        "trade",
                        "energy",
                        "macro",
                        "agri",
                    )
                    else cnt
                )  # equity/fi: 100% de lo que hay
                score = round(min(cnt / max(target, 1), 1.0) * 100, 1)
                fresh = None
                if anio:
                    if hasattr(anio, "year"):
                        lag = (datetime.now().date() - anio).days
                    else:
                        lag = datetime.now().year - int(anio)
                    fresh = max(0, lag)
                conn.execute(
                    text(
                        "INSERT INTO meta.data_quality "
                        "(domain, entity_type, entity_id, "
                        " completeness_score, freshness_days, "
                        " last_assessed) VALUES "
                        "(:d, 'panel', :e, :s, :f, now())"
                    ),
                    {"d": domain, "e": entidad, "s": score, "f": fresh},
                )
                resumen[domain] = {"entidades": cnt, "anio": anio}
            except Exception as e:  # noqa: BLE001
                logger.warning("quality %s: %s", domain, e)
    logger.info("Cobertura por dominio: %s", resumen)
    return resumen


def check_null_audit() -> dict:
    """Auditar NULLs en columnas que deberían estar rellenas."""
    resumen: dict[str, dict] = {}
    with engine.begin() as conn:
        conn.execute(
            text(
                "DELETE FROM meta.data_quality "
                "WHERE entity_type = 'null_audit'"
            )
        )
        for domain, tabla, col, q_total in _NULL_AUDIT:
            try:
                total = conn.execute(text(q_total)).scalar() or 0
                nulos = (
                    conn.execute(
                        text(
                            f"SELECT count(*) FROM {tabla} WHERE {col} IS NULL"
                        )
                    ).scalar()
                    or 0
                )
                pct = round((1 - nulos / max(total, 1)) * 100, 1)
                conn.execute(
                    text(
                        "INSERT INTO meta.data_quality "
                        "(domain, entity_type, entity_id, "
                        " completeness_score, last_assessed) "
                        "VALUES (:d, 'null_audit', :e, :s, now())"
                    ),
                    {"d": domain, "e": f"{tabla}.{col}", "s": pct},
                )
                resumen[f"{tabla}.{col}"] = {
                    "total": total,
                    "nulos": nulos,
                    "pct": pct,
                }
            except Exception as e:  # noqa: BLE001
                logger.warning("null_audit %s.%s: %s", tabla, col, e)
    logger.info("Auditoría NULLs: %s", resumen)
    return resumen


def check_orphan_fks() -> dict:
    """Detectar referencias huérfanas en FKs principales."""
    resumen: dict[str, int] = {}
    with engine.begin() as conn:
        conn.execute(
            text(
                "DELETE FROM meta.data_quality WHERE entity_type = 'orphan_fk'"
            )
        )
        for domain, desc, q in _ORPHAN_CHECKS:
            try:
                n = conn.execute(text(q)).scalar() or 0
                score = 100.0 if n == 0 else 0.0
                conn.execute(
                    text(
                        "INSERT INTO meta.data_quality "
                        "(domain, entity_type, entity_id, "
                        " completeness_score, source_count, "
                        " last_assessed) VALUES "
                        "(:d, 'orphan_fk', :e, :s, :n, now())"
                    ),
                    {"d": domain, "e": desc, "s": score, "n": n},
                )
                resumen[desc] = n
                if n > 0:
                    logger.warning("FK huérfana %s: %d filas", desc, n)
            except Exception as e:  # noqa: BLE001
                logger.warning("orphan_fk %s: %s", desc, e)
    logger.info("FKs huérfanas: %s", resumen)
    return resumen


def check_outliers() -> dict:
    """Detectar valores fuera de rangos plausibles."""
    resumen: dict[str, int] = {}
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM meta.data_quality WHERE entity_type = 'outlier'")
        )
        for domain, desc, q in _OUTLIER_CHECKS:
            try:
                n = conn.execute(text(q)).scalar() or 0
                score = 100.0 if n == 0 else round(max(0, 100 - n), 1)
                conn.execute(
                    text(
                        "INSERT INTO meta.data_quality "
                        "(domain, entity_type, entity_id, "
                        " completeness_score, source_count, "
                        " last_assessed) VALUES "
                        "(:d, 'outlier', :e, :s, :n, now())"
                    ),
                    {"d": domain, "e": desc, "s": score, "n": n},
                )
                resumen[desc] = n
                if n > 0:
                    logger.warning("Outlier %s: %d filas", desc, n)
            except Exception as e:  # noqa: BLE001
                logger.warning("outlier %s: %s", desc, e)
    logger.info("Outliers: %s", resumen)
    return resumen


def check_source_coverage() -> dict:
    """Contar filas exitosas por fuente de datos."""
    resumen: dict[str, int] = {}
    with engine.begin() as conn:
        conn.execute(
            text(
                "DELETE FROM meta.data_quality "
                "WHERE entity_type = 'source_coverage'"
            )
        )
        rows = conn.execute(
            text(
                "SELECT ds.name, count(*) AS n "
                "FROM meta.fetch_run fr "
                "JOIN meta.data_source ds ON ds.id = fr.source_id "
                "WHERE fr.status = 'success' "
                "GROUP BY ds.name ORDER BY n DESC"
            )
        ).fetchall()
        for name, n in rows:
            conn.execute(
                text(
                    "INSERT INTO meta.data_quality "
                    "(domain, entity_type, entity_id, "
                    " source_count, last_assessed) VALUES "
                    "('sources', 'source_coverage', :e, :n, now())"
                ),
                {"e": name, "n": n},
            )
            resumen[name] = n
    logger.info("Cobertura por fuente: %s", resumen)
    return resumen


def check_indicator_emptiness() -> dict:
    """Indicadores registrados sin data_points (fantasma)."""
    resumen: dict[str, int] = {}
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT i.code, i.category "
                "FROM macro.indicator i "
                "WHERE NOT EXISTS ("
                "  SELECT 1 FROM macro.series s "
                "  JOIN macro.data_point dp "
                "    ON dp.series_id = s.id "
                "  WHERE s.indicator_id = i.id"
                ") ORDER BY i.category, i.code"
            )
        ).fetchall()
        for _code, cat in rows:
            cat_key = cat or "sin_categoria"
            resumen[cat_key] = resumen.get(cat_key, 0) + 1
    total = sum(resumen.values())
    logger.info(
        "Indicadores fantasma: %d (por cat: %s)",
        total,
        resumen,
    )
    return {"total_fantasma": total, "por_categoria": resumen}


def check_mart_column_coverage() -> dict:
    """Cobertura de cada columna del mart_country_year."""
    resumen: dict[str, dict] = {}
    cols_query = (
        "SELECT a.attname FROM pg_attribute a "
        "JOIN pg_class c ON c.oid = a.attrelid "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'gold' "
        "AND c.relname = 'mart_country_year' "
        "AND a.attnum > 0 AND NOT a.attisdropped "
        "AND a.attname NOT IN ('country_code','year') "
        "ORDER BY a.attnum"
    )
    with engine.connect() as conn:
        cols = [r[0] for r in conn.execute(text(cols_query))]
        total_countries = (
            conn.execute(
                text(
                    "SELECT count(DISTINCT country_code) "
                    "FROM gold.mart_country_year"
                )
            ).scalar()
            or 0
        )
        for col in cols:
            n = (
                conn.execute(
                    text(
                        "SELECT count(DISTINCT country_code) "
                        "FROM gold.mart_country_year "
                        f"WHERE {col} IS NOT NULL"
                    )
                ).scalar()
                or 0
            )
            pct = round(n / max(total_countries, 1) * 100, 1)
            resumen[col] = {
                "countries": n,
                "pct": pct,
            }
            if n < 50:
                logger.warning(
                    "Baja cobertura: %s (%d países, %.1f%%)",
                    col,
                    n,
                    pct,
                )
    logger.info(
        "Cobertura mart: %d columnas, %d con <50 países",
        len(resumen),
        sum(1 for v in resumen.values() if v["countries"] < 50),
    )
    return resumen


def check_temporal_gaps() -> dict:
    """Detectar huecos >2 años en indicadores clave."""
    indicadores_clave = [
        "IMF_NGDPD",
        "IMF_PCPIPCH",
        "IMF_LUR",
    ]
    resumen: dict[str, list] = {}
    with engine.connect() as conn:
        for code in indicadores_clave:
            rows = conn.execute(
                text(
                    "WITH años AS ("
                    "  SELECT s.country_code,"
                    "    extract(year FROM dp.date)::int AS y"
                    "  FROM macro.data_point dp"
                    "  JOIN macro.series s"
                    "    ON s.id = dp.series_id"
                    "  JOIN macro.indicator i"
                    "    ON i.id = s.indicator_id"
                    "  WHERE i.code = :code"
                    "), gaps AS ("
                    "  SELECT country_code, y,"
                    "    lead(y) OVER ("
                    "      PARTITION BY country_code"
                    "      ORDER BY y"
                    "    ) - y AS gap"
                    "  FROM años"
                    ") SELECT country_code, y, gap "
                    "FROM gaps WHERE gap > 2 "
                    "ORDER BY gap DESC LIMIT 20"
                ),
                {"code": code},
            ).fetchall()
            gaps = [{"country": r[0], "year": r[1], "gap": r[2]} for r in rows]
            resumen[code] = gaps
            if gaps:
                logger.warning(
                    "Huecos en %s: %d países afectados",
                    code,
                    len(gaps),
                )
    return resumen


def _run_checks_datos() -> dict:
    """Puente hacia los checks de veracidad."""
    from stonks.quality_datos import run_checks_datos

    return run_checks_datos()


def run_all_checks() -> dict:
    """Ejecutar todos los checks de calidad (safe, no bloquea)."""
    results = {}
    for name, fn in [
        ("cobertura", check_world_quality),
        ("null_audit", check_null_audit),
        ("orphan_fk", check_orphan_fks),
        ("outliers", check_outliers),
        ("sources", check_source_coverage),
        ("indicadores_fantasma", check_indicator_emptiness),
        ("cobertura_mart", check_mart_column_coverage),
        ("huecos_temporales", check_temporal_gaps),
        # Veracidad y completitud: viven en quality_datos
        # para no engordar mas este modulo.
        ("datos", _run_checks_datos),
    ]:
        try:
            results[name] = fn()
        except Exception as e:  # noqa: BLE001
            logger.error("Check %s falló: %s", name, e)
            results[name] = {"error": str(e)}
    return results
