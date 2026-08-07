-- equity.ratios_mv: vista materializada de ratios fundamentales.
-- Una fila por company_id con los ratios calculados a partir del
-- ultimo periodo fiscal disponible (annual o trimestral) y el
-- ultimo precio. Consumida por kairos_bot.features.ratios.
--
-- Crear con: psql -d stonks_db -f scripts/create_ratios_mv.sql
-- Refrescar: REFRESH MATERIALIZED VIEW CONCURRENTLY equity.ratios_mv;
--
-- Notas:
-- - **Los ratios que mezclan precio y contabilidad se calculan en
--   dolares.** El precio esta en la moneda de cotizacion y las cuentas
--   en la de reporte, y no son la misma: Central Puerto cotiza en
--   dolares y reporta en pesos (PER 0,006), Novo Nordisk reporta en
--   coronas y su ADR cotiza en dolares (PER 2,0 frente a 12,7 en
--   Copenhague, con el mismo BPA). Eran 620 PER no comparables de
--   2.285, y salian los primeros al ordenar por PER: justo donde uno
--   busca gangas.
-- - Si falta el tipo de cambio de alguna de las dos monedas, el ratio
--   sale NULL y `moneda_coherente` a FALSE. Es preferible no dar el
--   dato a darlo mintiendo.
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
        currency_code,
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
),
-- Ultimo USD/moneda de cada divisa, admitiendo el par guardado al
-- reves (existe USDJPY pero el euro se cotiza EURUSD). El DISTINCT ON
-- importa: con los dos pares presentes habria dos filas por moneda.
tipos_todos AS (
    SELECT p.quote_currency AS moneda, r.close AS valor
    FROM forex.rate_daily r
    JOIN forex.currency_pair p ON p.id = r.pair_id
    WHERE p.base_currency = 'USD'
      AND r.date = (SELECT max(r2.date) FROM forex.rate_daily r2
                     WHERE r2.pair_id = r.pair_id)
    UNION ALL
    SELECT p.base_currency, 1.0 / r.close
    FROM forex.rate_daily r
    JOIN forex.currency_pair p ON p.id = r.pair_id
    WHERE p.quote_currency = 'USD' AND r.close > 0
      AND r.date = (SELECT max(r2.date) FROM forex.rate_daily r2
                     WHERE r2.pair_id = r.pair_id)
    UNION ALL
    SELECT 'USD', 1.0
),
tipo AS (
    SELECT DISTINCT ON (moneda) moneda, valor
    FROM tipos_todos WHERE valor > 0 ORDER BY moneda, valor
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

    -- Moneda de las cuentas, distinta de la de cotizacion.
    i.currency_code                                           AS moneda_cuentas,
    -- NULL si la empresa no tiene cuentas: ahi no hay nada que
    -- convertir y decir FALSE seria confundir "no aplica" con "no
    -- cuadra".
    CASE WHEN i.company_id IS NOT NULL
         THEN (tc.valor IS NOT NULL AND tr.valor IS NOT NULL)
    END                                                       AS moneda_coherente,

    -- Valoracion. Precio y contabilidad se llevan a dolares antes de
    -- dividir; si falta el tipo de cambio de cualquiera de las dos
    -- monedas, el ratio sale NULL en vez de mezclar unidades.
    p.close                                                   AS last_close,
    CASE
        WHEN i.eps_diluted IS NOT NULL AND i.eps_diluted > 0
         AND tc.valor IS NOT NULL AND tr.valor IS NOT NULL
        THEN (p.close / tc.valor) / (i.eps_diluted / tr.valor)
    END                                                       AS pe_ratio,
    CASE
        WHEN b.total_equity IS NOT NULL AND b.total_equity > 0
         AND c.shares_outstanding IS NOT NULL
         AND c.shares_outstanding > 0
         AND tc.valor IS NOT NULL AND tr.valor IS NOT NULL
        THEN (p.close / tc.valor)
             / ((b.total_equity / tr.valor) / c.shares_outstanding)
    END                                                       AS pb_ratio,
    CASE
        WHEN i.revenue IS NOT NULL AND i.revenue > 0
         AND c.market_cap_usd IS NOT NULL
         AND tr.valor IS NOT NULL
        THEN c.market_cap_usd / (i.revenue / tr.valor)
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
    -- Tambien mezclaba: capitalizacion en dolares sobre flujo en
    -- moneda de reporte.
    CASE
        WHEN c.market_cap_usd IS NOT NULL AND c.market_cap_usd > 0
         AND cf.free_cash_flow IS NOT NULL
         AND tr.valor IS NOT NULL
        THEN (cf.free_cash_flow / tr.valor) / c.market_cap_usd
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
-- tc: tipo de la moneda de COTIZACION; tr: el de la de REPORTE.
LEFT JOIN tipo tc ON tc.moneda = c.currency_code
LEFT JOIN tipo tr ON tr.moneda = i.currency_code
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
