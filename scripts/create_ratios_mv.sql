-- equity.ratios_mv: vista materializada de ratios fundamentales.
-- Una fila por company_id con los ratios calculados a partir del
-- ultimo periodo fiscal disponible (annual o trimestral) y el
-- ultimo precio. Consumida por kairos_bot.features.ratios.
--
-- Crear con: psql -d stonks_db -f scripts/create_ratios_mv.sql
-- Refrescar: REFRESH MATERIALIZED VIEW CONCURRENTLY equity.ratios_mv;
--
-- Notas:
-- - "Ultimo periodo" = el de mayor period_end_date por company.
-- - Si no hay estados (pre-2021 para muchos tickers), la fila no
--   aparece. Es intencional: sin datos no hay ratio.
-- - TTM mejorado (suma 4 ultimos quarters) queda para una V2.

BEGIN;

DROP MATERIALIZED VIEW IF EXISTS equity.ratios_mv CASCADE;

CREATE MATERIALIZED VIEW equity.ratios_mv AS
WITH latest_income AS (
    SELECT DISTINCT ON (company_id)
        company_id,
        period_end_date        AS income_period,
        revenue,
        gross_profit,
        operating_income,
        net_income,
        ebitda,
        eps_diluted,
        shares_diluted
    FROM equity.income_statement
    WHERE net_income IS NOT NULL
    ORDER BY company_id, period_end_date DESC NULLS LAST
),
latest_balance AS (
    SELECT DISTINCT ON (company_id)
        company_id,
        period_end_date        AS balance_period,
        total_assets,
        total_liabilities,
        total_equity,
        total_stockholders_equity,
        short_term_debt,
        long_term_debt,
        cash_and_equivalents
    FROM equity.balance_sheet
    WHERE total_assets IS NOT NULL
    ORDER BY company_id, period_end_date DESC NULLS LAST
),
latest_cashflow AS (
    SELECT DISTINCT ON (company_id)
        company_id,
        period_end_date        AS cashflow_period,
        operating_cash_flow,
        free_cash_flow,
        capital_expenditure,
        dividends_paid
    FROM equity.cash_flow
    ORDER BY company_id, period_end_date DESC NULLS LAST
),
latest_price AS (
    SELECT DISTINCT ON (company_id)
        company_id,
        date                   AS price_date,
        close,
        adj_close
    FROM equity.price_daily
    ORDER BY company_id, date DESC
)
SELECT
    c.id                       AS company_id,
    c.ticker,
    c.sector_id,
    c.country_code,
    c.currency_code,
    c.market_cap_usd,
    c.shares_outstanding,

    -- Periodos de referencia (para auditar staleness)
    p.price_date,
    i.income_period,
    b.balance_period,
    cf.cashflow_period,

    -- Valoracion
    p.close                                                   AS last_close,
    CASE
        WHEN i.eps_diluted IS NOT NULL AND i.eps_diluted > 0
        THEN p.close / i.eps_diluted
    END                                                       AS pe_ratio,
    CASE
        WHEN b.total_equity IS NOT NULL AND b.total_equity > 0
         AND c.shares_outstanding IS NOT NULL
         AND c.shares_outstanding > 0
        THEN p.close / (b.total_equity / c.shares_outstanding)
    END                                                       AS pb_ratio,
    CASE
        WHEN i.revenue IS NOT NULL AND i.revenue > 0
         AND c.market_cap_usd IS NOT NULL
        THEN c.market_cap_usd / i.revenue
    END                                                       AS ps_ratio,

    -- Rentabilidad
    CASE
        WHEN b.total_equity IS NOT NULL AND b.total_equity > 0
        THEN i.net_income / b.total_equity
    END                                                       AS roe,
    CASE
        WHEN b.total_assets IS NOT NULL AND b.total_assets > 0
        THEN i.net_income / b.total_assets
    END                                                       AS roa,
    CASE
        WHEN b.total_equity IS NOT NULL
         AND (COALESCE(b.long_term_debt, 0)
              + COALESCE(b.short_term_debt, 0)
              + b.total_equity) > 0
         AND i.operating_income IS NOT NULL
        THEN (i.operating_income * 0.79)  -- NOPAT aprox (tax 21%)
             / (COALESCE(b.long_term_debt, 0)
                + COALESCE(b.short_term_debt, 0)
                + b.total_equity)
    END                                                       AS roic,

    -- Margenes
    CASE
        WHEN i.revenue IS NOT NULL AND i.revenue > 0
        THEN i.gross_profit / i.revenue
    END                                                       AS gross_margin,
    CASE
        WHEN i.revenue IS NOT NULL AND i.revenue > 0
        THEN i.operating_income / i.revenue
    END                                                       AS operating_margin,
    CASE
        WHEN i.revenue IS NOT NULL AND i.revenue > 0
        THEN i.net_income / i.revenue
    END                                                       AS net_margin,

    -- Apalancamiento y liquidez
    CASE
        WHEN b.total_equity IS NOT NULL AND b.total_equity > 0
        THEN (COALESCE(b.short_term_debt, 0)
              + COALESCE(b.long_term_debt, 0))
             / b.total_equity
    END                                                       AS debt_equity,
    CASE
        WHEN b.total_assets IS NOT NULL AND b.total_assets > 0
        THEN (COALESCE(b.short_term_debt, 0)
              + COALESCE(b.long_term_debt, 0))
             / b.total_assets
    END                                                       AS debt_assets,

    -- Flujo de caja
    CASE
        WHEN c.market_cap_usd IS NOT NULL AND c.market_cap_usd > 0
         AND cf.free_cash_flow IS NOT NULL
        THEN cf.free_cash_flow / c.market_cap_usd
    END                                                       AS fcf_yield,

    -- Datos crudos (utiles para features derivadas)
    i.revenue,
    i.net_income,
    i.ebitda,
    i.eps_diluted,
    b.total_equity,
    b.total_assets,
    cf.free_cash_flow,
    cf.operating_cash_flow

FROM equity.company c
LEFT JOIN latest_price    p  ON p.company_id  = c.id
LEFT JOIN latest_income   i  ON i.company_id  = c.id
LEFT JOIN latest_balance  b  ON b.company_id  = c.id
LEFT JOIN latest_cashflow cf ON cf.company_id = c.id
WHERE c.is_active = TRUE;

-- Indices para consultas por ticker / sector / rankings.
CREATE UNIQUE INDEX ix_ratios_mv_company
    ON equity.ratios_mv (company_id);
CREATE INDEX ix_ratios_mv_ticker
    ON equity.ratios_mv (ticker);
CREATE INDEX ix_ratios_mv_sector
    ON equity.ratios_mv (sector_id);
CREATE INDEX ix_ratios_mv_pe
    ON equity.ratios_mv (pe_ratio)
    WHERE pe_ratio IS NOT NULL;
CREATE INDEX ix_ratios_mv_roe
    ON equity.ratios_mv (roe)
    WHERE roe IS NOT NULL;

COMMIT;
