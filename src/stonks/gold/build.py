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

# --- Economía mundial: dimensión país ---
_DIM_COUNTRY = """
INSERT INTO gold.dim_country AS d
    (country_code, name, region, sub_region, income_group)
SELECT code, name, region, sub_region, income_group
FROM ref.country
ON CONFLICT (country_code) DO UPDATE SET
    name = EXCLUDED.name,
    region = EXCLUDED.region,
    sub_region = EXCLUDED.sub_region,
    income_group = EXCLUDED.income_group
"""

# --- Panel ancho país × año, cross-dominio (macro + energía + comercio) ---
_MV_COUNTRY_YEAR = """
CREATE MATERIALIZED VIEW IF NOT EXISTS gold.mart_country_year AS
WITH macro_p AS (
    SELECT
        s.country_code,
        extract(year FROM dp.date)::smallint AS year,
        max(dp.value) FILTER (WHERE i.code = 'IMF_NGDPD') AS gdp_usd_bn,
        max(dp.value) FILTER (WHERE i.code = 'IMF_NGDPDPC')
            AS gdp_per_capita_usd,
        max(dp.value) FILTER (WHERE i.code = 'IMF_NGDP_RPCH')
            AS gdp_growth_pct,
        max(dp.value) FILTER (WHERE i.code = 'IMF_PPPGDP') AS gdp_ppp_bn,
        max(dp.value) FILTER (WHERE i.code = 'IMF_PCPIPCH')
            AS inflation_pct,
        max(dp.value) FILTER (WHERE i.code = 'IMF_LUR')
            AS unemployment_pct,
        max(dp.value) FILTER (WHERE i.code = 'IMF_LP') AS population_mn,
        max(dp.value) FILTER (WHERE i.code = 'IMF_GGXWDG_NGDP')
            AS gov_debt_pct_gdp,
        max(dp.value) FILTER (WHERE i.code = 'IMF_GGXCNL_NGDP')
            AS gov_balance_pct_gdp,
        max(dp.value) FILTER (WHERE i.code = 'IMF_BCA_NGDPD')
            AS current_account_pct_gdp,
        max(dp.value) FILTER (WHERE i.code = 'IMF_PPPPC')
            AS gdp_ppp_per_capita,
        max(dp.value) FILTER (WHERE i.code = 'IMF_PPPSH')
            AS share_world_gdp_ppp_pct,
        max(dp.value) FILTER (WHERE i.code = 'IMF_NGS_GDP')
            AS savings_pct_gdp,
        max(dp.value) FILTER (WHERE i.code = 'IMF_NI_GDP')
            AS investment_pct_gdp,
        max(dp.value) FILTER (WHERE i.code = 'IMF_rev')
            AS gov_revenue_pct_gdp,
        max(dp.value) FILTER (WHERE i.code = 'IMF_exp')
            AS gov_expenditure_pct_gdp,
        max(dp.value) FILTER (WHERE i.code = 'OWID_CO2') AS co2_mt,
        max(dp.value) FILTER (WHERE i.code = 'OWID_CO2_PC')
            AS co2_per_capita_t,
        max(dp.value) FILTER (WHERE i.code = 'OWID_CO2_SHARE')
            AS co2_share_global_pct,
        max(dp.value) FILTER (WHERE i.code = 'OWID_GHG') AS ghg_mt,
        -- Salud (WHO GHO)
        max(dp.value) FILTER (WHERE i.code = 'WHO_WHOSIS_000001')
            AS life_expectancy_yrs,
        max(dp.value) FILTER (WHERE i.code = 'WHO_MDG_0000000001')
            AS infant_mortality_per_1000,
        max(dp.value) FILTER (WHERE i.code = 'WHO_GHED_CHEGDP_SHA2011')
            AS health_exp_pct_gdp,
        -- Desigualdad renta/riqueza (WID.world; cuotas ×100 a %)
        max(dp.value) FILTER (WHERE i.code = 'WID_INC_TOP1') * 100
            AS income_top1_pct,
        max(dp.value) FILTER (WHERE i.code = 'WID_INC_TOP10') * 100
            AS income_top10_pct,
        max(dp.value) FILTER (WHERE i.code = 'WID_WEALTH_TOP1') * 100
            AS wealth_top1_pct,
        max(dp.value) FILTER (WHERE i.code = 'WID_INC_GINI')
            AS income_gini,
        -- Tipo de política monetaria (BIS)
        max(dp.value) FILTER (WHERE i.code = 'BIS_POLICY_RATE')
            AS policy_rate_pct,
        -- Educación (World Bank WDI)
        max(dp.value) FILTER (
            WHERE i.code = 'WB_SE.XPD.TOTL.GD.ZS')
            AS education_exp_pct_gdp,
        max(dp.value) FILTER (
            WHERE i.code = 'WB_SE.TER.ENRR')
            AS tertiary_enrollment_pct,
        -- Infraestructura (World Bank WDI)
        max(dp.value) FILTER (
            WHERE i.code = 'WB_IT.NET.USER.ZS')
            AS internet_users_pct,
        max(dp.value) FILTER (
            WHERE i.code = 'WB_IT.CEL.SETS.P2')
            AS mobile_per_100,
        -- I+D (World Bank WDI)
        max(dp.value) FILTER (
            WHERE i.code = 'WB_GB.XPD.RSDV.GD.ZS')
            AS rd_exp_pct_gdp,
        -- Pobreza (World Bank WDI)
        max(dp.value) FILTER (
            WHERE i.code = 'WB_SI.POV.DDAY')
            AS poverty_190_pct,
        -- Governance (World Bank WGI, score 0-100)
        max(dp.value) FILTER (
            WHERE i.code = 'WB_GOV_WGI_CC_SC')
            AS corruption_control_score,
        max(dp.value) FILTER (
            WHERE i.code = 'WB_GOV_WGI_GE_SC')
            AS gov_effectiveness_score,
        max(dp.value) FILTER (
            WHERE i.code = 'WB_GOV_WGI_PV_SC')
            AS political_stability_score,
        max(dp.value) FILTER (
            WHERE i.code = 'WB_GOV_WGI_RL_SC')
            AS rule_of_law_score,
        max(dp.value) FILTER (
            WHERE i.code = 'WB_GOV_WGI_RQ_SC')
            AS regulatory_quality_score,
        max(dp.value) FILTER (
            WHERE i.code = 'WB_GOV_WGI_VA_SC')
            AS voice_accountability_score,
        -- Turismo (World Bank WDI)
        max(dp.value) FILTER (
            WHERE i.code = 'WB_ST.INT.ARVL')
            AS tourism_arrivals,
        max(dp.value) FILTER (
            WHERE i.code = 'WB_ST.INT.RCPT.CD') / 1e9
            AS tourism_receipts_usd_bn,
        max(dp.value) FILTER (
            WHERE i.code = 'WB_ST.INT.XPND.CD') / 1e9
            AS tourism_expenditure_usd_bn,
        -- Migración (World Bank WDI)
        max(dp.value) FILTER (
            WHERE i.code = 'WB_SM.POP.NETM')
            AS net_migration,
        max(dp.value) FILTER (
            WHERE i.code = 'WB_SM.POP.TOTL')
            AS migrant_stock,
        max(dp.value) FILTER (
            WHERE i.code = 'WB_SM.POP.TOTL.ZS')
            AS migrant_stock_pct,
        max(dp.value) FILTER (
            WHERE i.code = 'WB_SM.POP.RHCR.EA')
            AS refugees_hosted,
        -- FDI (World Bank WDI, BoP USD)
        max(dp.value) FILTER (
            WHERE i.code = 'WB_BX.KLT.DINV.CD.WD')
            / 1e9 AS fdi_inflows_usd_bn,
        max(dp.value) FILTER (
            WHERE i.code = 'WB_BM.KLT.DINV.CD.WD')
            / 1e9 AS fdi_outflows_usd_bn,
        max(dp.value) FILTER (
            WHERE i.code = 'WB_BN.KLT.DINV.CD')
            / 1e9 AS fdi_net_usd_bn,
        -- BOP componentes (World Bank WDI, BoP USD)
        max(dp.value) FILTER (
            WHERE i.code = 'WB_BX.GSR.MRCH.CD')
            / 1e9 AS bop_goods_exports_bn,
        max(dp.value) FILTER (
            WHERE i.code = 'WB_BM.GSR.MRCH.CD')
            / 1e9 AS bop_goods_imports_bn,
        max(dp.value) FILTER (
            WHERE i.code = 'WB_BX.GSR.NFSV.CD')
            / 1e9 AS bop_services_exports_bn,
        max(dp.value) FILTER (
            WHERE i.code = 'WB_BM.GSR.NFSV.CD')
            / 1e9 AS bop_services_imports_bn,
        max(dp.value) FILTER (
            WHERE i.code = 'WB_BN.GSR.FCTY.CD')
            / 1e9 AS bop_primary_income_net_bn,
        -- Reservas (World Bank WDI)
        max(dp.value) FILTER (
            WHERE i.code = 'WB_FI.RES.TOTL.CD')
            / 1e9 AS reserves_total_usd_bn,
        max(dp.value) FILTER (
            WHERE i.code = 'WB_FI.RES.TOTL.MO')
            AS reserves_months_imports,
        -- Remesas (World Bank WDI)
        max(dp.value) FILTER (
            WHERE i.code = 'WB_BX.TRF.PWKR.CD.DT')
            / 1e9 AS remittances_received_usd_bn,
        -- Corrupción (Transparency International, 0-100)
        max(dp.value) FILTER (
            WHERE i.code = 'TI_CPI')
            AS ti_cpi_score,
        -- Libertad (Freedom House)
        max(dp.value) FILTER (
            WHERE i.code = 'FH_TOTAL')
            AS fh_freedom_score,
        max(dp.value) FILTER (
            WHERE i.code = 'FH_PR')
            AS fh_political_rights,
        max(dp.value) FILTER (
            WHERE i.code = 'FH_CL')
            AS fh_civil_liberties,
        -- Demografía WB (complementa IMF_LP)
        max(dp.value) FILTER (
            WHERE i.code = 'POPULATION')
            AS population_total,
        max(dp.value) FILTER (
            WHERE i.code = 'POPULATION_GROWTH')
            AS pop_growth_pct,
        max(dp.value) FILTER (
            WHERE i.code = 'URBAN_POPULATION_PCT')
            AS urban_pop_pct,
        max(dp.value) FILTER (
            WHERE i.code = 'WB_SP.DYN.TFRT.IN')
            AS fertility_rate,
        -- Trabajo WB (complementa IMF)
        max(dp.value) FILTER (
            WHERE i.code = 'LABOR_FORCE')
            AS labor_force_total,
        max(dp.value) FILTER (
            WHERE i.code = 'WB_SL.TLF.CACT.ZS')
            AS labor_participation_pct,
        -- Apertura comercial WB
        max(dp.value) FILTER (
            WHERE i.code = 'EXPORTS_PCT_GDP')
            AS exports_pct_gdp,
        max(dp.value) FILTER (
            WHERE i.code = 'IMPORTS_PCT_GDP')
            AS imports_pct_gdp,
        max(dp.value) FILTER (
            WHERE i.code = 'WB_NE.TRD.GNFS.ZS')
            AS trade_openness_pct,
        -- Fiscal WB
        max(dp.value) FILTER (
            WHERE i.code = 'TAX_REVENUE_PCT_GDP')
            AS tax_revenue_pct_gdp,
        -- Desarrollo financiero WB
        max(dp.value) FILTER (
            WHERE i.code = 'MARKET_CAP_PCT_GDP')
            AS market_cap_pct_gdp,
        max(dp.value) FILTER (
            WHERE i.code = 'BROAD_MONEY_PCT_GDP')
            AS broad_money_pct_gdp,
        max(dp.value) FILTER (
            WHERE i.code = 'DOMESTIC_CREDIT_PCT_GDP')
            AS credit_private_pct_gdp,
        max(dp.value) FILTER (
            WHERE i.code = 'INTEREST_RATE_LENDING')
            AS lending_rate,
        max(dp.value) FILTER (
            WHERE i.code = 'INTEREST_RATE_DEPOSIT')
            AS deposit_rate,
        max(dp.value) FILTER (
            WHERE i.code = 'REAL_INTEREST_RATE')
            AS real_interest_rate,
        -- Medio ambiente WB
        max(dp.value) FILTER (
            WHERE i.code = 'RENEWABLE_ENERGY_PCT')
            AS renewable_energy_pct,
        -- Gasto militar (SIPRI)
        max(dp.value) FILTER (
            WHERE i.code = 'SIPRI_MILEX_USD')
            AS military_exp_usd_mn,
        max(dp.value) FILTER (
            WHERE i.code = 'SIPRI_MILEX_GDP')
            AS military_exp_pct_gdp,
        max(dp.value) FILTER (
            WHERE i.code = 'SIPRI_MILEX_PC')
            AS military_exp_pc,
        -- Desarrollo humano (UNDP)
        max(dp.value) FILTER (
            WHERE i.code = 'UNDP_HDI')
            AS hdi_score,
        max(dp.value) FILTER (
            WHERE i.code = 'UNDP_GDI')
            AS gender_dev_index,
        max(dp.value) FILTER (
            WHERE i.code = 'UNDP_GII')
            AS gender_ineq_index,
        -- Libertad económica (Heritage)
        max(dp.value) FILTER (
            WHERE i.code = 'HF_ECON_FREEDOM')
            AS econ_freedom_score,
        max(dp.value) FILTER (
            WHERE i.code = 'HF_TRADE_FREEDOM')
            AS trade_freedom_score,
        -- Vulnerabilidad climática (ND-GAIN)
        max(dp.value) FILTER (
            WHERE i.code = 'NDGAIN_OVERALL')
            AS ndgain_score,
        max(dp.value) FILTER (
            WHERE i.code = 'NDGAIN_VULNERABILITY')
            AS ndgain_vulnerability,
        max(dp.value) FILTER (
            WHERE i.code = 'NDGAIN_READINESS')
            AS ndgain_readiness,
        -- Fragilidad estatal (FSI)
        max(dp.value) FILTER (
            WHERE i.code = 'FSI_TOTAL')
            AS fragile_state_index,
        -- Democracia detallada (V-Dem, 0-1)
        max(dp.value) FILTER (
            WHERE i.code = 'VDEM_POLYARCHY')
            AS vdem_polyarchy,
        max(dp.value) FILTER (
            WHERE i.code = 'VDEM_LIBERAL')
            AS vdem_liberal,
        max(dp.value) FILTER (
            WHERE i.code = 'VDEM_CORRUPTION')
            AS vdem_corruption,
        max(dp.value) FILTER (
            WHERE i.code = 'VDEM_MEDIA_FREEDOM')
            AS vdem_media_freedom,
        max(dp.value) FILTER (
            WHERE i.code = 'VDEM_JUDICIAL_INDEP')
            AS vdem_judicial_indep,
        -- Demografía detallada (UN DESA)
        max(dp.value) FILTER (
            WHERE i.code = 'UNDESA_POP_TOTAL')
            AS undesa_pop_total,
        max(dp.value) FILTER (
            WHERE i.code = 'UNDESA_MEDIAN_AGE')
            AS median_age,
        max(dp.value) FILTER (
            WHERE i.code = 'UNDESA_DEPEND_OLD')
            AS old_depend_ratio,
        max(dp.value) FILTER (
            WHERE i.code = 'UNDESA_DEPEND_YOUNG')
            AS young_depend_ratio,
        max(dp.value) FILTER (
            WHERE i.code = 'UNDESA_FERTILITY')
            AS undesa_fertility,
        -- Innovación (WIPO)
        max(dp.value) FILTER (
            WHERE i.code = 'WIPO_PATENT_APPS')
            AS patent_applications,
        max(dp.value) FILTER (
            WHERE i.code = 'WIPO_PATENT_GRANTS')
            AS patent_grants,
        -- Educación detallada (UNESCO UIS)
        max(dp.value) FILTER (
            WHERE i.code = 'UNESCO_LITERACY')
            AS literacy_rate_pct,
        max(dp.value) FILTER (
            WHERE i.code = 'UNESCO_MEAN_SCHOOL_YEARS')
            AS mean_school_years,
        max(dp.value) FILTER (
            WHERE i.code = 'UNESCO_PUPIL_TEACHER')
            AS pupil_teacher_ratio,
        -- Finanzas públicas detalladas (IMF GFS, % PIB)
        max(dp.value) FILTER (
            WHERE i.code = 'IMF_GFS_TAX_TOTAL')
            AS gfs_tax_total_pct,
        max(dp.value) FILTER (
            WHERE i.code = 'IMF_GFS_TAX_INCOME')
            AS gfs_tax_income_pct,
        max(dp.value) FILTER (
            WHERE i.code = 'IMF_GFS_SPEND_DEFENSE')
            AS gfs_spend_defense_pct,
        max(dp.value) FILTER (
            WHERE i.code = 'IMF_GFS_SPEND_HEALTH')
            AS gfs_spend_health_pct,
        max(dp.value) FILTER (
            WHERE i.code = 'IMF_GFS_SPEND_EDUCATION')
            AS gfs_spend_education_pct,
        max(dp.value) FILTER (
            WHERE i.code = 'IMF_GFS_SPEND_SOCIAL')
            AS gfs_spend_social_pct,
        -- Emisiones sectoriales (EDGAR JRC, Mt)
        max(dp.value) FILTER (
            WHERE i.code = 'EDGAR_CO2_ENERGY')
            AS edgar_co2_energy_mt,
        max(dp.value) FILTER (
            WHERE i.code = 'EDGAR_CO2_INDUSTRY')
            AS edgar_co2_industry_mt,
        max(dp.value) FILTER (
            WHERE i.code = 'EDGAR_CH4')
            AS edgar_ch4_mt,
        max(dp.value) FILTER (
            WHERE i.code = 'EDGAR_N2O')
            AS edgar_n2o_mt
    FROM macro.data_point dp
    JOIN macro.series s ON s.id = dp.series_id
    JOIN macro.indicator i ON i.id = s.indicator_id
    WHERE s.country_code IS NOT NULL
    GROUP BY s.country_code, extract(year FROM dp.date)
),
energy_p AS (
    SELECT country_code, period AS year,
        max(value) FILTER (
            WHERE product_code = 'primary_energy' AND flow = 'consumption'
        ) AS primary_energy_twh,
        max(value) FILTER (
            WHERE product_code = 'total' AND flow = 'electricity'
        ) AS electricity_twh,
        max(value) FILTER (
            WHERE product_code = 'renewables' AND flow = 'electricity'
        ) AS renewables_elec_twh
    FROM energy.balance
    GROUP BY country_code, period
),
trade_p AS (
    SELECT reporter_code AS country_code, period AS year,
        max(value_usd_k) FILTER (WHERE flow = 'X') / 1e6 AS exports_usd_bn,
        max(value_usd_k) FILTER (WHERE flow = 'M') / 1e6 AS imports_usd_bn
    FROM trade.flow
    WHERE partner_code = 'WLD' AND product_code = 'Total'
    GROUP BY reporter_code, period
)
SELECT m.*,
    e.primary_energy_twh, e.electricity_twh, e.renewables_elec_twh,
    -- % de electricidad renovable (calculado)
    round((e.renewables_elec_twh / NULLIF(e.electricity_twh, 0) * 100)::numeric,
          2) AS renewables_share_elec_pct,
    t.exports_usd_bn, t.imports_usd_bn,
    -- Balance comercial de bienes (calculado)
    (t.exports_usd_bn - t.imports_usd_bn) AS trade_balance_usd_bn
FROM macro_p m
LEFT JOIN energy_p e
    ON e.country_code = m.country_code AND e.year = m.year
LEFT JOIN trade_p t
    ON t.country_code = m.country_code AND t.year = m.year
"""

_MV_COUNTRY_YEAR_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS ix_gold_country_year
ON gold.mart_country_year (country_code, year)
"""

# --- Matriz de comercio bilateral país×país (exports + imports) ---
_MV_TRADE = """
CREATE MATERIALIZED VIEW IF NOT EXISTS gold.mart_trade_matrix AS
SELECT x.reporter_code, x.partner_code, x.period AS year,
       x.value_usd_k AS exports_usd_k,
       m.value_usd_k AS imports_usd_k
FROM trade.flow x
LEFT JOIN trade.flow m
  ON m.reporter_code = x.reporter_code
 AND m.partner_code = x.partner_code
 AND m.period = x.period
 AND m.product_code = x.product_code
 AND m.flow = 'M'
WHERE x.flow = 'X' AND x.product_code = 'Total'
  AND x.partner_code IN (SELECT code FROM ref.country)
"""

_MV_TRADE_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS ix_gold_trade_matrix
ON gold.mart_trade_matrix (reporter_code, partner_code, year)
"""

# --- Empresa + macro de su país (cruce empresa↔economía) --------
_MV_COMPANY_MACRO = """
CREATE MATERIALIZED VIEW IF NOT EXISTS gold.mart_company_macro AS
SELECT
    dc.company_id, dc.ticker, dc.name AS company_name,
    dc.sector_name, dc.country_code, mcy.year,
    mcy.gdp_growth_pct, mcy.inflation_pct,
    mcy.unemployment_pct, mcy.policy_rate_pct,
    mcy.gov_debt_pct_gdp, mcy.current_account_pct_gdp,
    mcy.life_expectancy_yrs, mcy.income_gini,
    mcy.exports_usd_bn, mcy.imports_usd_bn,
    mcy.fdi_inflows_usd_bn, mcy.reserves_total_usd_bn
FROM gold.dim_company dc
JOIN gold.mart_country_year mcy
  ON mcy.country_code = dc.country_code
WHERE dc.country_code IS NOT NULL
"""

_MV_COMPANY_MACRO_IX = """
CREATE UNIQUE INDEX IF NOT EXISTS ix_gold_company_macro
ON gold.mart_company_macro (company_id, year)
"""

# --- Riesgo soberano (rating + deuda + volatilidad macro) --------
_MV_SOVEREIGN_RISK = """
CREATE MATERIALIZED VIEW IF NOT EXISTS gold.mart_sovereign_risk AS
WITH latest_rating AS (
    SELECT bi.country_code, cr.agency, cr.rating,
           cr.outlook, cr.rating_date,
           ROW_NUMBER() OVER (
               PARTITION BY bi.country_code, cr.agency
               ORDER BY cr.rating_date DESC
           ) AS rn
    FROM fi.credit_rating cr
    JOIN fi.bond_issuer bi ON bi.id = cr.issuer_id
    WHERE bi.issuer_type = 'government'
)
SELECT
    mcy.country_code, mcy.year,
    mcy.gdp_growth_pct, mcy.inflation_pct,
    mcy.unemployment_pct,
    mcy.gov_debt_pct_gdp, mcy.gov_balance_pct_gdp,
    mcy.current_account_pct_gdp,
    mcy.reserves_total_usd_bn,
    mcy.reserves_months_imports,
    lr.agency AS rating_agency,
    lr.rating AS sovereign_rating,
    lr.outlook AS rating_outlook,
    stddev(mcy.gdp_growth_pct) OVER (
        PARTITION BY mcy.country_code
        ORDER BY mcy.year
        ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
    ) AS gdp_vol_5y
FROM gold.mart_country_year mcy
LEFT JOIN latest_rating lr
  ON lr.country_code = mcy.country_code AND lr.rn = 1
"""

_MV_SOVEREIGN_RISK_IX = """
CREATE UNIQUE INDEX IF NOT EXISTS ix_gold_sovereign_risk
ON gold.mart_sovereign_risk (country_code, year, rating_agency)
"""

# --- Dependencia comercial (top partners, concentración) ---------
_MV_TRADE_DEP = """
CREATE MATERIALIZED VIEW IF NOT EXISTS gold.mart_trade_dependency AS
WITH ranked AS (
    SELECT reporter_code, partner_code, year,
           coalesce(exports_usd_k, 0)
           + coalesce(imports_usd_k, 0) AS total_k,
           ROW_NUMBER() OVER (
               PARTITION BY reporter_code, year
               ORDER BY coalesce(exports_usd_k,0)
                      + coalesce(imports_usd_k,0) DESC
           ) AS rk
    FROM gold.mart_trade_matrix
)
SELECT reporter_code, year,
    max(partner_code) FILTER (WHERE rk = 1) AS top1_partner,
    max(total_k)      FILTER (WHERE rk = 1) AS top1_trade_k,
    max(partner_code) FILTER (WHERE rk = 2) AS top2_partner,
    max(partner_code) FILTER (WHERE rk = 3) AS top3_partner,
    round(
        sum(total_k) FILTER (WHERE rk <= 3)::numeric
        / NULLIF(sum(total_k), 0) * 100, 1
    ) AS top3_concentration_pct,
    count(DISTINCT partner_code) AS n_partners
FROM ranked
GROUP BY reporter_code, year
"""

_MV_TRADE_DEP_IX = """
CREATE UNIQUE INDEX IF NOT EXISTS ix_gold_trade_dep
ON gold.mart_trade_dependency (reporter_code, year)
"""

# --- Sorpresas de beneficios (estimado vs reportado) -------------
_MV_EARNINGS_SURPRISE = """
CREATE MATERIALIZED VIEW IF NOT EXISTS gold.mart_earnings_surprise AS
SELECT
    ed.company_id,
    dc.ticker,
    extract(year FROM ed.date)::smallint AS year,
    ed.date AS announcement_date,
    ed.eps_estimate,
    ed.reported_eps,
    ed.reported_eps - ed.eps_estimate AS surprise,
    ed.surprise_pct
FROM equity.earnings_date ed
JOIN gold.dim_company dc ON dc.company_id = ed.company_id
WHERE ed.eps_estimate IS NOT NULL
  AND ed.reported_eps IS NOT NULL
"""

_MV_EARNINGS_SURPRISE_IX = """
CREATE UNIQUE INDEX IF NOT EXISTS ix_gold_earnings_surprise
ON gold.mart_earnings_surprise (company_id, announcement_date)
"""

# --- Sector × país (exposición sectorial geográfica) -------------
_MV_SECTOR_COUNTRY = """
CREATE MATERIALIZED VIEW IF NOT EXISTS gold.mart_sector_country AS
SELECT
    dc.sector_name,
    dc.country_code,
    dco.name AS country_name,
    dco.region,
    count(*) AS n_companies,
    sum(CASE WHEN dc.is_active THEN 1 ELSE 0 END) AS n_active,
    round(avg(c.market_cap_usd)::numeric, 0) AS avg_market_cap
FROM gold.dim_company dc
JOIN equity.company c ON c.id = dc.company_id
LEFT JOIN gold.dim_country dco
  ON dco.country_code = dc.country_code
WHERE dc.sector_name IS NOT NULL
  AND dc.country_code IS NOT NULL
GROUP BY dc.sector_name, dc.country_code, dco.name, dco.region
"""

_MV_SECTOR_COUNTRY_IX = """
CREATE UNIQUE INDEX IF NOT EXISTS ix_gold_sector_country
ON gold.mart_sector_country (sector_name, country_code)
"""

# --- Panel gobernanza multidimensional (WGI + TI + FH + Heritage + FSI + V-Dem)
_MV_GOVERNANCE = """
CREATE MATERIALIZED VIEW IF NOT EXISTS
    gold.mart_country_governance AS
SELECT
    s.country_code,
    extract(year FROM dp.date)::smallint AS year,
    -- World Bank WGI (score 0-100)
    max(dp.value) FILTER (
        WHERE i.code = 'WB_GOV_WGI_CC_SC')
        AS wgi_corruption_control,
    max(dp.value) FILTER (
        WHERE i.code = 'WB_GOV_WGI_GE_SC')
        AS wgi_gov_effectiveness,
    max(dp.value) FILTER (
        WHERE i.code = 'WB_GOV_WGI_PV_SC')
        AS wgi_political_stability,
    max(dp.value) FILTER (
        WHERE i.code = 'WB_GOV_WGI_RL_SC')
        AS wgi_rule_of_law,
    max(dp.value) FILTER (
        WHERE i.code = 'WB_GOV_WGI_RQ_SC')
        AS wgi_regulatory_quality,
    max(dp.value) FILTER (
        WHERE i.code = 'WB_GOV_WGI_VA_SC')
        AS wgi_voice_accountability,
    -- Transparency International (0-100)
    max(dp.value) FILTER (
        WHERE i.code = 'TI_CPI')
        AS ti_cpi_score,
    -- Freedom House
    max(dp.value) FILTER (
        WHERE i.code = 'FH_TOTAL')
        AS fh_freedom_score,
    max(dp.value) FILTER (
        WHERE i.code = 'FH_PR')
        AS fh_political_rights,
    max(dp.value) FILTER (
        WHERE i.code = 'FH_CL')
        AS fh_civil_liberties,
    -- Heritage Foundation (0-100)
    max(dp.value) FILTER (
        WHERE i.code = 'HF_ECON_FREEDOM')
        AS hf_econ_freedom,
    max(dp.value) FILTER (
        WHERE i.code = 'HF_TRADE_FREEDOM')
        AS hf_trade_freedom,
    max(dp.value) FILTER (
        WHERE i.code = 'HF_FISCAL')
        AS hf_fiscal_health,
    -- Fragile States Index (0-120)
    max(dp.value) FILTER (
        WHERE i.code = 'FSI_TOTAL')
        AS fsi_total,
    max(dp.value) FILTER (
        WHERE i.code = 'FSI_COHESION')
        AS fsi_cohesion,
    max(dp.value) FILTER (
        WHERE i.code = 'FSI_ECONOMIC')
        AS fsi_economic,
    -- V-Dem (0-1)
    max(dp.value) FILTER (
        WHERE i.code = 'VDEM_POLYARCHY')
        AS vdem_polyarchy,
    max(dp.value) FILTER (
        WHERE i.code = 'VDEM_LIBERAL')
        AS vdem_liberal,
    max(dp.value) FILTER (
        WHERE i.code = 'VDEM_CORRUPTION')
        AS vdem_corruption,
    max(dp.value) FILTER (
        WHERE i.code = 'VDEM_MEDIA_FREEDOM')
        AS vdem_media_freedom,
    max(dp.value) FILTER (
        WHERE i.code = 'VDEM_JUDICIAL_INDEP')
        AS vdem_judicial_indep
FROM macro.data_point dp
JOIN macro.series s ON s.id = dp.series_id
JOIN macro.indicator i ON i.id = s.indicator_id
WHERE s.country_code IS NOT NULL
  AND i.category = 'governance'
GROUP BY s.country_code, extract(year FROM dp.date)
"""

_MV_GOVERNANCE_IX = """
CREATE UNIQUE INDEX IF NOT EXISTS ix_gold_governance
ON gold.mart_country_governance (country_code, year)
"""

# --- Panel riesgo climático (ND-GAIN + emisiones + renovables) ---
_MV_CLIMATE_RISK = """
CREATE MATERIALIZED VIEW IF NOT EXISTS
    gold.mart_climate_risk AS
SELECT
    s.country_code,
    extract(year FROM dp.date)::smallint AS year,
    -- ND-GAIN
    max(dp.value) FILTER (
        WHERE i.code = 'NDGAIN_OVERALL')
        AS ndgain_score,
    max(dp.value) FILTER (
        WHERE i.code = 'NDGAIN_VULNERABILITY')
        AS ndgain_vulnerability,
    max(dp.value) FILTER (
        WHERE i.code = 'NDGAIN_READINESS')
        AS ndgain_readiness,
    -- Emisiones (OWID)
    max(dp.value) FILTER (
        WHERE i.code = 'OWID_CO2')
        AS co2_mt,
    max(dp.value) FILTER (
        WHERE i.code = 'OWID_CO2_PC')
        AS co2_per_capita_t,
    max(dp.value) FILTER (
        WHERE i.code = 'OWID_CO2_SHARE')
        AS co2_share_global_pct,
    max(dp.value) FILTER (
        WHERE i.code = 'OWID_GHG')
        AS ghg_mt,
    -- Energía renovable (WB)
    max(dp.value) FILTER (
        WHERE i.code = 'RENEWABLE_ENERGY_PCT')
        AS renewable_energy_pct,
    -- Emisiones sectoriales (EDGAR JRC, Mt)
    max(dp.value) FILTER (
        WHERE i.code = 'EDGAR_CO2_ENERGY')
        AS edgar_co2_energy_mt,
    max(dp.value) FILTER (
        WHERE i.code = 'EDGAR_CO2_INDUSTRY')
        AS edgar_co2_industry_mt,
    max(dp.value) FILTER (
        WHERE i.code = 'EDGAR_CH4')
        AS edgar_ch4_mt,
    max(dp.value) FILTER (
        WHERE i.code = 'EDGAR_N2O')
        AS edgar_n2o_mt
FROM macro.data_point dp
JOIN macro.series s ON s.id = dp.series_id
JOIN macro.indicator i ON i.id = s.indicator_id
WHERE s.country_code IS NOT NULL
GROUP BY s.country_code, extract(year FROM dp.date)
"""

_MV_CLIMATE_RISK_IX = """
CREATE UNIQUE INDEX IF NOT EXISTS ix_gold_climate_risk
ON gold.mart_climate_risk (country_code, year)
"""

# --- Catálogo autodocumentado de indicadores macro ---
_VIEW_INDICATOR = """
CREATE OR REPLACE VIEW gold.dim_indicator AS
SELECT
    i.code, i.name, i.category, i.unit, i.frequency,
    string_agg(DISTINCT ds.name, ', ') AS sources,
    count(DISTINCT s.country_code) AS n_countries,
    min(dp.date) AS first_date,
    max(dp.date) AS last_date,
    count(dp.id) AS n_points
FROM macro.indicator i
LEFT JOIN macro.indicator_source isr ON isr.indicator_id = i.id
LEFT JOIN meta.data_source ds ON ds.id = isr.source_id
LEFT JOIN macro.series s ON s.indicator_id = i.id
LEFT JOIN macro.data_point dp ON dp.series_id = s.id
GROUP BY i.id, i.code, i.name, i.category, i.unit, i.frequency
"""


# --- Regímenes de volatilidad (VIX + variantes) --------
_MV_VOLATILITY_REGIME = """
CREATE MATERIALIZED VIEW IF NOT EXISTS
    gold.mart_volatility_regime AS
SELECT
    vi.code,
    vi.name AS index_name,
    vd.date,
    vd.close AS value,
    avg(vd.close) OVER w20 AS sma_20,
    avg(vd.close) OVER w60 AS sma_60,
    stddev(vd.close) OVER w60 AS std_60d,
    CASE
        WHEN vi.code = 'VIX' THEN
            CASE
                WHEN vd.close < 15 THEN 'low'
                WHEN vd.close < 25 THEN 'normal'
                WHEN vd.close < 35 THEN 'elevated'
                ELSE 'extreme'
            END
        ELSE NULL
    END AS regime
FROM deriv.volatility_daily vd
JOIN deriv.volatility_index vi
    ON vi.id = vd.index_id
WINDOW
    w20 AS (PARTITION BY vi.id
            ORDER BY vd.date
            ROWS BETWEEN 19 PRECEDING
            AND CURRENT ROW),
    w60 AS (PARTITION BY vi.id
            ORDER BY vd.date
            ROWS BETWEEN 59 PRECEDING
            AND CURRENT ROW)
"""

_MV_VOLATILITY_REGIME_IX = """
CREATE UNIQUE INDEX IF NOT EXISTS
    ix_gold_vol_regime
ON gold.mart_volatility_regime
    (code, date)
"""

# --- Panorama crypto: top coins con retornos --------
_MV_CRYPTO_OVERVIEW = """
CREATE MATERIALIZED VIEW IF NOT EXISTS
    gold.mart_crypto_overview AS
WITH latest AS (
    SELECT coin_id,
           close AS last_price,
           volume_usd AS last_volume,
           market_cap_usd AS last_mcap,
           date AS last_date
    FROM crypto.price_daily
    WHERE date = (
        SELECT max(date) FROM crypto.price_daily
    )
),
prev_30 AS (
    SELECT coin_id, close AS price_30d
    FROM crypto.price_daily
    WHERE date = (
        SELECT max(date) - 30
        FROM crypto.price_daily
    )
),
prev_365 AS (
    SELECT coin_id, close AS price_1y
    FROM crypto.price_daily
    WHERE date = (
        SELECT max(date) - 365
        FROM crypto.price_daily
    )
)
SELECT
    c.symbol, c.name, c.category,
    c.market_cap_rank,
    l.last_date, l.last_price,
    l.last_volume, l.last_mcap,
    round(
        (l.last_price / NULLIF(p30.price_30d, 0)
         - 1) * 100, 2
    ) AS return_30d_pct,
    round(
        (l.last_price / NULLIF(p1y.price_1y, 0)
         - 1) * 100, 2
    ) AS return_1y_pct
FROM crypto.coin c
JOIN latest l ON l.coin_id = c.id
LEFT JOIN prev_30 p30 ON p30.coin_id = c.id
LEFT JOIN prev_365 p1y ON p1y.coin_id = c.id
"""

_MV_CRYPTO_OVERVIEW_IX = """
CREATE UNIQUE INDEX IF NOT EXISTS
    ix_gold_crypto_overview
ON gold.mart_crypto_overview (symbol)
"""

# --- Rendimiento ETF por categoría --------
_MV_ETF_CATEGORY = """
CREATE MATERIALIZED VIEW IF NOT EXISTS
    gold.mart_etf_category AS
WITH latest_nav AS (
    SELECT fund_id, close, date AS last_date
    FROM fund.nav_daily
    WHERE date = (
        SELECT max(date) FROM fund.nav_daily
    )
),
nav_1y AS (
    SELECT fund_id, close AS nav_1y
    FROM fund.nav_daily
    WHERE date = (
        SELECT max(date) - 365
        FROM fund.nav_daily
    )
)
SELECT
    f.asset_class,
    f.geography,
    f.strategy,
    count(DISTINCT f.id) AS n_funds,
    round(avg(ln.close)::numeric, 2)
        AS avg_nav,
    round(avg(
        (ln.close / NULLIF(n1.nav_1y, 0)
         - 1) * 100
    )::numeric, 2) AS avg_return_1y_pct,
    sum(
        (SELECT count(*)
         FROM fund.nav_daily nd
         WHERE nd.fund_id = f.id)
    ) AS total_nav_points
FROM fund.fund f
JOIN latest_nav ln ON ln.fund_id = f.id
LEFT JOIN nav_1y n1 ON n1.fund_id = f.id
WHERE f.asset_class IS NOT NULL
GROUP BY f.asset_class, f.geography,
    f.strategy
"""

_MV_ETF_CATEGORY_IX = """
CREATE UNIQUE INDEX IF NOT EXISTS
    ix_gold_etf_category
ON gold.mart_etf_category
    (asset_class, geography, strategy)
"""

# --- Curva de tipos actual vs hace 1 año --------
_MV_YIELD_CURVE = """
CREATE MATERIALIZED VIEW IF NOT EXISTS
    gold.mart_yield_curve AS
WITH latest AS (
    SELECT date, yield_3m, yield_2y,
           yield_5y, yield_10y, yield_30y,
           spread_10y_2y, spread_10y_3m
    FROM fi.yield_curve
    WHERE date = (
        SELECT max(date) FROM fi.yield_curve
    )
),
year_ago AS (
    SELECT date, yield_3m, yield_2y,
           yield_5y, yield_10y, yield_30y
    FROM fi.yield_curve
    WHERE date = (
        SELECT max(date) - 365
        FROM fi.yield_curve
    )
)
SELECT
    'current' AS period,
    l.date,
    l.yield_3m, l.yield_2y,
    l.yield_5y, l.yield_10y,
    l.yield_30y,
    l.spread_10y_2y,
    l.spread_10y_3m
FROM latest l
UNION ALL
SELECT
    '1y_ago' AS period,
    y.date,
    y.yield_3m, y.yield_2y,
    y.yield_5y, y.yield_10y,
    y.yield_30y,
    y.yield_10y - y.yield_2y,
    y.yield_10y - y.yield_3m
FROM year_ago y
"""

_MV_YIELD_CURVE_IX = """
CREATE UNIQUE INDEX IF NOT EXISTS
    ix_gold_yield_curve
ON gold.mart_yield_curve (period)
"""


_VIEW_DATA_SOURCE = """
CREATE OR REPLACE VIEW gold.dim_data_source AS
SELECT
    ds.name,
    ds.display_name,
    ds.base_url,
    ds.is_enabled,
    count(fr.id) AS total_runs,
    count(fr.id) FILTER (
        WHERE fr.status = 'success'
    ) AS successful_runs,
    max(fr.finished_at) AS last_run,
    sum(fr.records_inserted) AS total_records
FROM meta.data_source ds
LEFT JOIN meta.fetch_run fr ON fr.source_id = ds.id
GROUP BY ds.id, ds.name, ds.display_name,
    ds.base_url, ds.is_enabled
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
            conn.execute(text(_DIM_COUNTRY))
            conn.execute(text(_VIEW_POOL))
            conn.execute(text(_MV_BENCHMARK))
            conn.execute(text(_MV_INDEX))
            # Recrear el mart país×año para incorporar columnas nuevas.
            conn.execute(
                text(
                    "DROP MATERIALIZED VIEW IF EXISTS "
                    "gold.mart_country_year CASCADE"
                )
            )
            conn.execute(text(_MV_COUNTRY_YEAR))
            conn.execute(text(_MV_COUNTRY_YEAR_INDEX))
            conn.execute(text(_MV_TRADE))
            conn.execute(text(_MV_TRADE_INDEX))
            # Marts cruzados (empresa↔macro, riesgo, trade, earnings, sector)
            for mv_sql, ix_sql in [
                (_MV_COMPANY_MACRO, _MV_COMPANY_MACRO_IX),
                (_MV_SOVEREIGN_RISK, _MV_SOVEREIGN_RISK_IX),
                (_MV_TRADE_DEP, _MV_TRADE_DEP_IX),
                (_MV_EARNINGS_SURPRISE, _MV_EARNINGS_SURPRISE_IX),
                (_MV_SECTOR_COUNTRY, _MV_SECTOR_COUNTRY_IX),
                (_MV_GOVERNANCE, _MV_GOVERNANCE_IX),
                (_MV_CLIMATE_RISK, _MV_CLIMATE_RISK_IX),
                (_MV_VOLATILITY_REGIME, _MV_VOLATILITY_REGIME_IX),
                (_MV_CRYPTO_OVERVIEW, _MV_CRYPTO_OVERVIEW_IX),
                (_MV_ETF_CATEGORY, _MV_ETF_CATEGORY_IX),
                (_MV_YIELD_CURVE, _MV_YIELD_CURVE_IX),
            ]:
                conn.execute(text(mv_sql))
                conn.execute(text(ix_sql))
            conn.execute(text(_VIEW_INDICATOR))
            conn.execute(text(_VIEW_DATA_SOURCE))
        # Refrescar las materializadas fuera de la transacción DDL
        with engine.connect() as conn:
            conn.execute(
                text("REFRESH MATERIALIZED VIEW gold.mart_benchmark_returns")
            )
            conn.execute(
                text("REFRESH MATERIALIZED VIEW gold.mart_country_year")
            )
            conn.execute(
                text("REFRESH MATERIALIZED VIEW gold.mart_trade_matrix")
            )
            for mv in (
                "gold.mart_company_macro",
                "gold.mart_sovereign_risk",
                "gold.mart_trade_dependency",
                "gold.mart_country_governance",
                "gold.mart_climate_risk",
                "gold.mart_earnings_surprise",
                "gold.mart_sector_country",
                "gold.mart_volatility_regime",
                "gold.mart_crypto_overview",
                "gold.mart_etf_category",
                "gold.mart_yield_curve",
            ):
                conn.execute(text(f"REFRESH MATERIALIZED VIEW {mv}"))
            conn.execute(text("REFRESH MATERIALIZED VIEW equity.ratios_mv"))
            conn.commit()
        # Checks de calidad completos (informativo, no bloquea).
        try:
            from stonks.quality import run_all_checks

            run_all_checks()
        except Exception as e:  # noqa: BLE001
            logger.warning("Checks de calidad fallaron: %s", e)
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
