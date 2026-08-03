# Patrones de JOIN comunes

Los 15 cruces más útiles entre esquemas. Cada uno incluye contexto,
SQL y notas de rendimiento.

---

## 1. Empresa + precios + fundamentales

Combina la ficha de empresa con su precio actual y último beneficio.

```sql
SELECT c.ticker, c.name,
       p.date, p.close, p.volume,
       bs.total_assets, ic.net_income
FROM equity.company c
JOIN equity.price_daily p ON p.company_id = c.id
LEFT JOIN equity.income_statement ic ON ic.company_id = c.id
LEFT JOIN equity.balance_sheet bs ON bs.company_id = c.id
WHERE c.ticker = 'AAPL'
  AND p.date = (SELECT max(date) FROM equity.price_daily
                WHERE company_id = c.id)
  AND ic.period_end = (SELECT max(period_end)
                       FROM equity.income_statement
                       WHERE company_id = c.id);
```

**Rendimiento**: filtra por `company_id` + `date` (índice cubierto).

---

## 2. Empresa + macro de su país

`gold.mart_company_macro` ya lo tiene precalculado:

```sql
SELECT ticker, company_name, year,
       gdp_growth_pct, inflation_pct, unemployment_pct
FROM gold.mart_company_macro
WHERE ticker = 'AAPL' AND year >= 2020
ORDER BY year;
```

Manual (si no existe el mart):

```sql
SELECT c.ticker, mcy.*
FROM equity.company c
JOIN gold.mart_country_year mcy
  ON mcy.country_code = c.country_code
WHERE c.ticker = 'AAPL';
```

---

## 3. Fundamentales PIT a una fecha concreta

El patrón `DISTINCT ON + filed_date <=` devuelve el último valor
conocido de cada métrica para cada empresa a la fecha elegida.

```sql
SELECT DISTINCT ON (company_id, metric)
    company_id, metric, value, filed_date
FROM gold.fact_fundamentals_pit
WHERE filed_date <= '2023-12-31'
ORDER BY company_id, metric, filed_date DESC;
```

**Rendimiento**: ~31M filas, índice `ix_gold_pit_co_metric`
(`company_id, metric`). Siempre filtrar por `company_id` si es
posible, o añadir `metric =` para reducir el escaneo.

---

## 4. Composición del S&P 500 + precios

Para un backtest del S&P 500 sin sesgo de supervivencia:

```sql
SELECT im.company_id, dc.ticker, p.date, p.close
FROM gold.index_membership im
JOIN gold.dim_company dc ON dc.company_id = im.company_id
JOIN equity.price_daily p ON p.company_id = im.company_id
WHERE im.start_date <= '2023-01-01'
  AND (im.end_date IS NULL OR im.end_date > '2023-01-01')
  AND p.date BETWEEN '2023-01-01' AND '2023-12-31';
```

---

## 5. País: macro + comercio + energía

`gold.mart_country_year` combina las tres fuentes:

```sql
SELECT country_code, year,
       gdp_per_capita_usd, inflation_pct,
       exports_usd_bn, imports_usd_bn,
       primary_energy_twh, renewables_share_elec_pct,
       co2_per_capita_t
FROM gold.mart_country_year
WHERE country_code = 'ESP' AND year >= 2015
ORDER BY year;
```

---

## 6. Riesgo soberano: rating + macro

`gold.mart_sovereign_risk` cruza rating Fitch con macro:

```sql
SELECT country_code, year, sovereign_rating,
       gov_debt_pct_gdp, gdp_vol_5y,
       current_account_pct_gdp
FROM gold.mart_sovereign_risk
WHERE year = 2023
ORDER BY gdp_vol_5y DESC NULLS LAST;
```

---

## 7. Commodities + macro (via fecha)

Cruce temporal: precio de commodity en la misma fecha que un dato macro.

```sql
SELECT cp.date, cp.close AS wti_price,
       dp.value AS us_cpi
FROM commodity.price_daily cp
JOIN commodity.commodity c ON c.id = cp.commodity_id
JOIN macro.series s ON s.country_code = 'USA'
JOIN macro.indicator i ON i.id = s.indicator_id
JOIN macro.data_point dp ON dp.series_id = s.id
WHERE c.symbol = 'CL=F'
  AND i.code = 'US_CPI_MOM'
  AND dp.date = date_trunc('month', cp.date)
  AND cp.date >= '2020-01-01'
ORDER BY cp.date;
```

---

## 8. Factores + precios (backtest de señal)

```sql
SELECT fs.company_id, dc.ticker, fs.value AS value_zscore,
       p2.close / p1.close - 1 AS return_1m
FROM gold.fact_factor_scores fs
JOIN gold.dim_company dc ON dc.company_id = fs.company_id
JOIN equity.price_daily p1 ON p1.company_id = fs.company_id
  AND p1.date = fs.as_of_date
JOIN equity.price_daily p2 ON p2.company_id = fs.company_id
  AND p2.date = fs.as_of_date + interval '30 days'
WHERE fs.factor = 'value' AND fs.universe = 'sp500';
```

---

## 9. Sorpresas de beneficios

`gold.mart_earnings_surprise` (precalculado):

```sql
SELECT ticker, year, announcement_date,
       eps_estimate, reported_eps, surprise_pct
FROM gold.mart_earnings_surprise
WHERE ticker = 'AAPL'
ORDER BY announcement_date DESC;
```

---

## 10. Comercio bilateral (drill-down)

De la matriz bilateral al detalle por producto HS:

```sql
-- Bilateral total
SELECT reporter_code, partner_code, year,
       exports_usd_k, imports_usd_k
FROM gold.mart_trade_matrix
WHERE reporter_code = 'ESP' AND partner_code = 'DEU'
ORDER BY year DESC LIMIT 5;

-- Detalle por producto HS2
SELECT f.product_code, p.description,
       round(f.value_usd_k / 1e6, 1) AS millon_usd
FROM trade.flow f
JOIN ref.hs_product p ON p.code = f.product_code
WHERE f.reporter_code = 'ESP' AND f.partner_code = 'WLD'
  AND f.flow = 'X' AND f.period = 2022
ORDER BY f.value_usd_k DESC LIMIT 10;
```

---

## 11. Tipos de interés globales (IMF IFS)

Comparar lending/deposit rates entre países:

```sql
SELECT s.country_code, dp.date, dp.value AS lending_rate
FROM macro.data_point dp
JOIN macro.series s ON s.id = dp.series_id
JOIN macro.indicator i ON i.id = s.indicator_id
WHERE i.code = 'IMF_LENDING_RATE'
  AND s.country_code IN ('USA', 'ESP', 'BRA', 'JPN')
  AND dp.date >= '2020-01-01'
ORDER BY dp.date, s.country_code;
```

Combinar con ECB EURIBOR para la eurozona:

```sql
SELECT dp.date, dp.value AS euribor_3m
FROM macro.data_point dp
JOIN macro.series s ON s.id = dp.series_id
JOIN macro.indicator i ON i.id = s.indicator_id
WHERE i.code = 'ECB_EURIBOR_3M'
ORDER BY dp.date DESC LIMIT 12;
```

---

## 12. Dependencia comercial + riesgo

`gold.mart_trade_dependency` muestra concentración:

```sql
SELECT td.reporter_code, c.name,
       td.top1_partner, td.top3_concentration_pct,
       td.n_partners,
       sr.sovereign_rating, sr.gov_debt_pct_gdp
FROM gold.mart_trade_dependency td
JOIN ref.country c ON c.code = td.reporter_code
LEFT JOIN gold.mart_sovereign_risk sr
  ON sr.country_code = td.reporter_code
  AND sr.year = td.year
WHERE td.year = 2022
ORDER BY td.top3_concentration_pct DESC NULLS LAST
LIMIT 20;
```

---

## 13. Turismo + FDI + desarrollo

Panel turismo, inversión extranjera y desarrollo por país.

```sql
SELECT country_code, year,
       tourism_arrivals, tourism_receipts_usd_bn,
       fdi_inflows_usd_bn, fdi_outflows_usd_bn,
       gdp_usd_bn, gdp_per_capita_usd
FROM gold.mart_country_year
WHERE country_code IN ('ESP', 'FRA', 'THA', 'MEX')
  AND year BETWEEN 2015 AND 2023
ORDER BY country_code, year;
```

---

## 14. Gobernanza multidimensional (6 fuentes)

`gold.mart_country_governance` consolida WGI, TI, FH, Heritage,
FSI y V-Dem en un panel ancho:

```sql
SELECT country_code, year,
       wgi_corruption_control, ti_cpi_score,
       fh_freedom_score, hf_econ_freedom,
       fsi_total, vdem_polyarchy, vdem_liberal
FROM gold.mart_country_governance
WHERE year = 2023
ORDER BY ti_cpi_score DESC NULLS LAST;
```

Para análisis rápido desde el mart general:

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

---

## 15. BOP trimestral (IMF) — evolución cuenta corriente

Series trimestrales de balanza de pagos por país.

```sql
SELECT s.country_code, dp.date, dp.value AS cab_bn_usd
FROM macro.data_point dp
JOIN macro.series s ON s.id = dp.series_id
JOIN macro.indicator i ON i.id = s.indicator_id
WHERE i.code = 'IMF_BOP_CAB_Q'
  AND s.country_code = 'ESP'
ORDER BY dp.date;
```

---

## 16. Riesgo climático (ND-GAIN + emisiones + renovables)

`gold.mart_climate_risk` consolida vulnerabilidad y emisiones:

```sql
SELECT country_code, year,
       ndgain_score, ndgain_vulnerability,
       ndgain_readiness,
       co2_mt, co2_per_capita_t,
       edgar_co2_energy_mt, edgar_ch4_mt,
       renewable_energy_pct
FROM gold.mart_climate_risk
WHERE year = 2022
ORDER BY ndgain_vulnerability DESC NULLS LAST;
```

Cruce con GDP para intensidad carbónica:

```sql
SELECT cr.country_code, cr.year,
       cr.co2_mt, mcy.gdp_usd_bn,
       round((cr.co2_mt / NULLIF(mcy.gdp_usd_bn, 0))::numeric,
             2) AS co2_per_gdp_bn
FROM gold.mart_climate_risk cr
JOIN gold.mart_country_year mcy
  ON mcy.country_code = cr.country_code
  AND mcy.year = cr.year
WHERE cr.year = 2022
ORDER BY co2_per_gdp_bn DESC NULLS LAST
LIMIT 20;
```

---

## 17. Innovación y capital humano

Patentes WIPO + educación UNESCO + I+D:

```sql
SELECT country_code, year,
       patent_applications, patent_grants,
       literacy_rate_pct, mean_school_years,
       rd_exp_pct_gdp, tertiary_enrollment_pct,
       gdp_per_capita_usd
FROM gold.mart_country_year
WHERE year = 2022
  AND patent_applications IS NOT NULL
ORDER BY patent_applications DESC
LIMIT 20;
```

---

## 18. Fiscal detallado (IMF GFS + WDI)

Composición del gasto público por función y estructura impositiva:

```sql
SELECT country_code, year,
       gfs_tax_total_pct, gfs_tax_income_pct,
       tax_revenue_pct_gdp AS wb_tax_pct,
       gfs_spend_defense_pct, gfs_spend_health_pct,
       gfs_spend_education_pct, gfs_spend_social_pct,
       gov_debt_pct_gdp, gov_balance_pct_gdp
FROM gold.mart_country_year
WHERE year = 2022
  AND gfs_tax_total_pct IS NOT NULL
ORDER BY gfs_spend_social_pct DESC NULLS LAST;
```
