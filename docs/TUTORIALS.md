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

`gold.mart_country_year` tiene **~30 métricas** por país y año:
PIB, inflación, paro, deuda, comercio, energía, CO2, salud,
desigualdad, educación, infraestructura, I+D, pobreza.

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
