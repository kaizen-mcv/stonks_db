# Tutoriales stonks_db

Guías paso a paso para los tres casos de uso más comunes.

---

## 1. Backtests point-in-time (sin sesgo de revisión)

### Concepto
Los datos macro y de beneficios se **revisan**: el PIB publicado hoy
para el Q1 cambiará 3 veces en los próximos 2 años. Si usas la cifra
final, tu backtest hace trampa (miras el futuro).

`gold.fact_fundamentals_pit` guarda cada dato con su `filed_date`:
la fecha en que la empresa lo publicó ante la SEC. Así puedes
reconstruir lo que se sabía en cualquier momento.

### Query canónico: último valor conocido a una fecha

```sql
-- Beneficio neto de cada empresa conocido a 30-jun-2023
SELECT DISTINCT ON (company_id)
    company_id, fiscal_year, fiscal_quarter,
    value, filed_date
FROM gold.fact_fundamentals_pit
WHERE metric = 'NetIncomeLoss'
  AND filed_date <= '2023-06-30'
ORDER BY company_id, filed_date DESC;
```

### Universo sin sesgo de supervivencia

Para evitar analizar solo las que sobrevivieron, usa
`gold.index_membership` (composición del S&P 500 en cada momento):

```sql
-- Empresas del S&P 500 a 30-jun-2023
SELECT company_id
FROM gold.index_membership
WHERE start_date <= '2023-06-30'
  AND (end_date IS NULL OR end_date > '2023-06-30');
```

### P/E ratio point-in-time

```sql
WITH pit_eps AS (
    SELECT DISTINCT ON (company_id)
        company_id, value AS eps, filed_date
    FROM gold.fact_fundamentals_pit
    WHERE metric = 'EarningsPerShareBasic'
      AND filed_date <= '2023-06-30'
    ORDER BY company_id, filed_date DESC
),
pit_price AS (
    SELECT DISTINCT ON (company_id)
        company_id, close
    FROM equity.price_daily
    WHERE date <= '2023-06-30'
    ORDER BY company_id, date DESC
)
SELECT p.company_id, dc.ticker,
       p.close / NULLIF(e.eps, 0) AS pe_ratio
FROM pit_price p
JOIN pit_eps e ON e.company_id = p.company_id
JOIN gold.dim_company dc ON dc.company_id = p.company_id
WHERE e.eps > 0
ORDER BY pe_ratio;
```

### Vintages macro (FRED/ALFRED)

`macro.data_point_vintage` guarda las revisiones de las macro US clave:

```sql
-- Cómo evolucionó el PIB US del Q3-2008 (primera estimación → final)
SELECT vintage_date, value
FROM macro.data_point_vintage v
JOIN macro.series s ON s.id = v.series_id
JOIN macro.indicator i ON i.id = s.indicator_id
WHERE i.code = 'US_GDP_QUARTERLY'
  AND v.obs_date = '2008-07-01'
ORDER BY vintage_date;
```

---

## 2. Análisis de la economía mundial

### Panel país × año

`gold.mart_country_year` tiene **~120 métricas** por país y año:
PIB, inflación, paro, deuda, comercio, energía, CO2, salud,
desigualdad, educación, infraestructura, I+D, pobreza, governance,
democracia, militar, clima, innovación, fiscal detallado, demografía.

```sql
-- Top 10 países por PIB per capita 2022
SELECT country_code, gdp_per_capita_usd,
       life_expectancy_yrs, income_gini,
       internet_users_pct
FROM gold.mart_country_year
WHERE year = 2022 AND gdp_per_capita_usd IS NOT NULL
ORDER BY gdp_per_capita_usd DESC
LIMIT 10;
```

### Riesgo soberano

`gold.mart_sovereign_risk` combina rating + deuda + volatilidad:

```sql
-- Países con deuda > 80% PIB y perspectiva negativa
SELECT country_code, year, sovereign_rating,
       rating_outlook, gov_debt_pct_gdp, gdp_vol_5y
FROM gold.mart_sovereign_risk
WHERE year = 2023
  AND gov_debt_pct_gdp > 80
  AND rating_outlook = 'negative'
ORDER BY gov_debt_pct_gdp DESC;
```

### Dependencia comercial

```sql
-- Países más concentrados en pocos socios (2022)
SELECT reporter_code, top1_partner,
       top3_concentration_pct, n_partners
FROM gold.mart_trade_dependency
WHERE year = 2022
ORDER BY top3_concentration_pct DESC
LIMIT 15;
```

### Tipos de interés globales (IMF IFS + ECB SDW)

Series mensuales para 190+ países (IMF IFS) y la eurozona (ECB SDW):

```sql
-- Comparar lending rates de 5 economías
SELECT s.country_code, dp.date, dp.value
FROM macro.data_point dp
JOIN macro.series s ON s.id = dp.series_id
JOIN macro.indicator i ON i.id = s.indicator_id
WHERE i.code = 'IMF_LENDING_RATE'
  AND s.country_code IN ('USA','ESP','BRA','JPN','IND')
  AND dp.date >= '2020-01-01'
ORDER BY dp.date, s.country_code;
```

Indicadores disponibles: `IMF_POLICY_RATE`, `IMF_LENDING_RATE`,
`IMF_DEPOSIT_RATE`, `IMF_DISCOUNT_RATE`, `IMF_MONEY_MARKET_RATE`,
`IMF_CPI_YOY`, `IMF_BROAD_MONEY`. Eurozona: `ECB_EURIBOR_3M`,
`ECB_MRR`, `ECB_DFR`, `ECB_M1`/`M2`/`M3`.

---

## 3. Factores de inversión personalizados

### Factor pre-construido

`gold.fact_factor_scores` tiene Value, Quality y Momentum
normalizados por sector (z-score):

```sql
-- Top 10 empresas "Value" del S&P 500 hoy
SELECT fs.company_id, dc.ticker, fs.value AS zscore
FROM gold.fact_factor_scores fs
JOIN gold.dim_company dc ON dc.company_id = fs.company_id
WHERE fs.factor = 'value'
  AND fs.universe = 'sp500'
ORDER BY fs.value DESC
LIMIT 10;
```

### Construir un factor personalizado

Patrón: calcular una métrica por empresa, z-score por sector:

```sql
WITH base AS (
    -- Último ROE por empresa (PIT)
    SELECT DISTINCT ON (company_id)
        company_id, value AS roe
    FROM gold.fact_fundamentals_pit
    WHERE metric = 'ReturnOnEquity'
    ORDER BY company_id, filed_date DESC
),
sector AS (
    SELECT b.company_id, b.roe,
           dc.sector_name,
           avg(b.roe) OVER w AS avg_sector,
           stddev(b.roe) OVER w AS std_sector
    FROM base b
    JOIN gold.dim_company dc ON dc.company_id = b.company_id
    WINDOW w AS (PARTITION BY dc.sector_name)
)
SELECT company_id, sector_name, roe,
       (roe - avg_sector) / NULLIF(std_sector, 0) AS zscore
FROM sector
ORDER BY zscore DESC;
```

---

## 4. Turismo, migración y FDI por país

`gold.mart_country_year` incluye turismo (arrivals, receipts,
expenditure), migración (net, stock, refugees), FDI (inflows,
outflows, net), BOP componentes y reservas.

```sql
-- Top 10 destinos turísticos vs PIB
SELECT country_code, year,
       tourism_arrivals, tourism_receipts_usd_bn,
       gdp_usd_bn,
       round((tourism_receipts_usd_bn
              / NULLIF(gdp_usd_bn, 0) * 100)::numeric, 2)
           AS tourism_pct_gdp
FROM gold.mart_country_year
WHERE year = 2019  -- pre-pandemia
  AND tourism_arrivals IS NOT NULL
ORDER BY tourism_arrivals DESC
LIMIT 10;
```

```sql
-- Países con más refugiados hospedados
SELECT country_code, year, refugees_hosted,
       migrant_stock, migrant_stock_pct
FROM gold.mart_country_year
WHERE year = 2022 AND refugees_hosted IS NOT NULL
ORDER BY refugees_hosted DESC LIMIT 10;
```

---

## 5. Gobernanza avanzada (6 fuentes, mart dedicado)

Seis fuentes complementarias: WGI (institucional), TI CPI
(percepción de corrupción), Freedom House (libertad política),
Heritage (libertad económica), FSI (fragilidad estatal)
y V-Dem (democracia granular).

### Mart dedicado

`gold.mart_country_governance` consolida las 6 fuentes en 21
columnas para análisis institucional profundo:

```sql
SELECT country_code, year,
       wgi_corruption_control, ti_cpi_score,
       fh_freedom_score, hf_econ_freedom,
       fsi_total, vdem_polyarchy, vdem_liberal,
       vdem_media_freedom, vdem_judicial_indep
FROM gold.mart_country_governance
WHERE year = 2023
ORDER BY vdem_polyarchy DESC NULLS LAST;
```

### Correlación democracia × desarrollo

```sql
SELECT g.country_code,
       g.vdem_polyarchy, g.ti_cpi_score,
       m.gdp_per_capita_usd, m.hdi_score
FROM gold.mart_country_governance g
JOIN gold.mart_country_year m
  ON m.country_code = g.country_code
  AND m.year = g.year
WHERE g.year = 2023
  AND g.vdem_polyarchy IS NOT NULL
  AND m.gdp_per_capita_usd IS NOT NULL
ORDER BY g.vdem_polyarchy DESC;
```

### Desde el mart general (vista rápida)

```sql
SELECT country_code, year,
       corruption_control_score AS wgi_corruption,
       ti_cpi_score, fh_freedom_score,
       econ_freedom_score, fragile_state_index,
       vdem_polyarchy, vdem_liberal
FROM gold.mart_country_year
WHERE year = 2023
  AND ti_cpi_score IS NOT NULL
ORDER BY ti_cpi_score DESC;
```

Escalas: `TI_CPI` (0-100, mayor = menos corrupto),
`FH_TOTAL` (0-100, mayor = más libre), `FH_PR`/`FH_CL`
(1-7, menor = más libre), WGI scores (-2.5 a +2.5),
Heritage (0-100), FSI (0-120, mayor = más frágil),
V-Dem (0-1, mayor = más democrático).

---

## 6. Riesgo climático y emisiones

Panel de riesgo climático para análisis ESG e inversión sostenible.

### Mart dedicado

`gold.mart_climate_risk` consolida ND-GAIN (vulnerabilidad),
OWID (emisiones CO2/GHG), EDGAR (emisiones sectoriales) y
energía renovable del WDI:

```sql
SELECT country_code, year,
       ndgain_score, ndgain_vulnerability,
       ndgain_readiness,
       co2_mt, co2_per_capita_t,
       edgar_co2_energy_mt, edgar_co2_industry_mt,
       edgar_ch4_mt, edgar_n2o_mt,
       renewable_energy_pct
FROM gold.mart_climate_risk
WHERE year = 2022
ORDER BY ndgain_vulnerability DESC NULLS LAST;
```

### Intensidad carbónica por PIB

```sql
SELECT cr.country_code, cr.year,
       cr.co2_mt, m.gdp_usd_bn,
       round((cr.co2_mt
              / NULLIF(m.gdp_usd_bn, 0))::numeric, 2)
           AS co2_per_gdp_bn,
       cr.ndgain_readiness
FROM gold.mart_climate_risk cr
JOIN gold.mart_country_year m
  ON m.country_code = cr.country_code
  AND m.year = cr.year
WHERE cr.year = 2022 AND m.gdp_usd_bn IS NOT NULL
ORDER BY co2_per_gdp_bn DESC NULLS LAST
LIMIT 20;
```

### Emisiones sectoriales (EDGAR)

```sql
SELECT country_code, year,
       edgar_co2_energy_mt,
       edgar_co2_industry_mt,
       edgar_ch4_mt, edgar_n2o_mt
FROM gold.mart_country_year
WHERE country_code IN ('CHN', 'USA', 'IND', 'RUS', 'JPN')
  AND year BETWEEN 2015 AND 2022
ORDER BY country_code, year;
```

Escalas: ND-GAIN (0-100, mayor = mejor preparado),
emisiones en Mt (megatoneladas). La combinación de alta
vulnerabilidad + baja readiness señala riesgo climático agudo.

---

## 7. Balanza de pagos trimestral (IMF BOP)

Series trimestrales para análisis de sector externo.

```sql
-- Evolución cuenta corriente y goods/services
SELECT s.country_code, dp.date,
       i.code, dp.value AS bn_usd
FROM macro.data_point dp
JOIN macro.series s ON s.id = dp.series_id
JOIN macro.indicator i ON i.id = s.indicator_id
WHERE i.code IN (
    'IMF_BOP_CAB_Q', 'IMF_BOP_GOODS_X_Q',
    'IMF_BOP_GOODS_M_Q', 'IMF_BOP_SVCS_X_Q',
    'IMF_BOP_SVCS_M_Q'
)
AND s.country_code = 'DEU'
AND dp.date >= '2020-01-01'
ORDER BY dp.date, i.code;
```

Indicadores BOP trimestrales: `IMF_BOP_CAB_Q` (current
account), `IMF_BOP_GOODS_X_Q`/`_M_Q` (goods exports/imports),
`IMF_BOP_SVCS_X_Q`/`_M_Q` (services), `IMF_BOP_INCOME1_Q`
(primary income), `IMF_BOP_INCOME2_Q` (secondary income),
`IMF_BOP_FDI_Q` (direct investment), `IMF_BOP_FA_Q`
(financial account). Valores en miles de millones USD.
