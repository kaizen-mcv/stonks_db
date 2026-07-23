# Patrones de JOIN comunes

Los 10 cruces más útiles entre esquemas. Cada uno incluye contexto,
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
