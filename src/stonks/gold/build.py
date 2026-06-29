"""Reconstrucción idempotente de la capa gold.

Puebla dimensiones y hechos derivados con INSERT...SELECT + ON CONFLICT
y refresca las vistas/materializadas. Es seguro re-ejecutar: dos
corridas dejan el mismo estado. Se invoca al final del pipeline.
"""

from sqlalchemy import text

from stonks.db import engine, get_session
from stonks.logger import get_logger
from stonks.models.meta import TransformRun

logger = get_logger("stonks.gold")

# Códigos posibles del S&P 500 en equity.market_index (según semilla)
SP500_CODES = ("SPX", "SPY", "GSPC", "^GSPC", "SP500")

# --- Dimensión fecha: un día por fecha con cotización disponible ---
_DIM_DATE = """
INSERT INTO gold.dim_date AS d
    (date_key, year, quarter, month, day_of_week, is_month_end,
     is_trading_day)
SELECT g::date,
       extract(year FROM g)::smallint,
       extract(quarter FROM g)::smallint,
       extract(month FROM g)::smallint,
       extract(isodow FROM g)::smallint,
       (g = (date_trunc('month', g) + interval '1 month -1 day')),
       TRUE
FROM generate_series(
        (SELECT min(date) FROM equity.price_daily),
        (SELECT max(date) FROM equity.price_daily),
        interval '1 day') AS g
ON CONFLICT (date_key) DO NOTHING
"""

# --- Dimensión empresa: clave subrogada = id; sector desnormalizado ---
_DIM_COMPANY = """
INSERT INTO gold.dim_company AS dc
    (company_key, company_id, ticker, name, sector_id, sector_name,
     country_code, currency_code, is_active, delisted_date)
SELECT c.id, c.id, c.ticker, c.name, c.sector_id, s.name,
       c.country_code, c.currency_code, c.is_active, c.delisted_date
FROM equity.company c
LEFT JOIN ref.sector s ON s.id = c.sector_id
ON CONFLICT (company_id) DO UPDATE SET
    ticker = EXCLUDED.ticker,
    name = EXCLUDED.name,
    sector_id = EXCLUDED.sector_id,
    sector_name = EXCLUDED.sector_name,
    country_code = EXCLUDED.country_code,
    currency_code = EXCLUDED.currency_code,
    is_active = EXCLUDED.is_active,
    delisted_date = EXCLUDED.delisted_date
"""

# --- Vista: universo point-in-time expandido a días de cotización ---
_VIEW_POOL = """
CREATE OR REPLACE VIEW gold.mart_pool_membership AS
SELECT m.index_id, m.company_id, d.date_key AS date
FROM gold.index_membership m
JOIN gold.dim_date d
  ON d.date_key >= m.start_date
 AND (m.end_date IS NULL OR d.date_key < m.end_date)
WHERE d.is_trading_day IS TRUE
"""

# --- Materializada: retorno diario del pool (EW honesto) vs SPY ---
_MV_BENCHMARK = f"""
CREATE MATERIALIZED VIEW IF NOT EXISTS gold.mart_benchmark_returns AS
WITH member_ret AS (
    SELECT pm.date,
           COALESCE(pd.adj_close, pd.close)
           / NULLIF(LAG(COALESCE(pd.adj_close, pd.close))
                    OVER (PARTITION BY pd.company_id ORDER BY pd.date), 0)
           - 1 AS ret
    FROM gold.mart_pool_membership pm
    JOIN equity.price_daily pd
      ON pd.company_id = pm.company_id AND pd.date = pm.date
)
SELECT date, 'equal_weight'::varchar(20) AS method, avg(ret) AS ret
FROM member_ret
WHERE ret IS NOT NULL
GROUP BY date
UNION ALL
SELECT ip.date, 'spy'::varchar(20),
       ip.close / NULLIF(LAG(ip.close) OVER (ORDER BY ip.date), 0) - 1
FROM equity.index_price ip
JOIN equity.market_index mi ON mi.id = ip.index_id
WHERE mi.code IN {SP500_CODES}
"""

_MV_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS ix_gold_benchmark_date_method
ON gold.mart_benchmark_returns (date, method)
"""


def build_gold() -> dict:
    """Reconstruir dimensiones, vistas y materializadas de gold."""
    session = get_session()
    run = TransformRun(domain="gold", target_layer="gold", status="running")
    session.add(run)
    session.commit()
    run_id = run.id
    session.close()

    resumen: dict[str, str] = {}
    try:
        with engine.begin() as conn:
            conn.execute(text(_DIM_DATE))
            conn.execute(text(_DIM_COMPANY))
            conn.execute(text(_VIEW_POOL))
            conn.execute(text(_MV_BENCHMARK))
            conn.execute(text(_MV_INDEX))
        # Refrescar la materializada fuera de la transacción DDL
        with engine.connect() as conn:
            conn.execute(
                text("REFRESH MATERIALIZED VIEW gold.mart_benchmark_returns")
            )
            conn.commit()
        resumen["status"] = "ok"
        _finish(run_id, "success")
        logger.info("Capa gold reconstruida")
    except Exception as e:  # noqa: BLE001
        resumen["status"] = f"error: {e}"
        _finish(run_id, "failed", {"msg": str(e)})
        logger.error("Fallo construyendo gold: %s", e)
    return resumen


def _finish(run_id: int, status: str, error_log: dict | None = None) -> None:
    """Cerrar el registro de auditoría."""
    from datetime import datetime

    session = get_session()
    run = session.query(TransformRun).filter_by(id=run_id).first()
    if run:
        run.finished_at = datetime.now()
        run.status = status
        run.error_log = error_log
        session.commit()
    session.close()
