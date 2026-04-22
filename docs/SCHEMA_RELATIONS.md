# stonks_db — Esquema de Relaciones

> 40 tablas · 11 esquemas · 20 foreign keys · ~3.5M filas totales
> Generado: 2026-04-22

## Resumen por esquema

| Esquema | Tablas | Filas totales | Tamaño | Descripción |
|---------|--------|--------------|--------|-------------|
| **ref** | 4 | 498 | ~224 KB | Datos de referencia (países, monedas, bolsas, sectores) |
| **meta** | 3 | 6.530 | ~1.3 MB | Auditoría, fuentes de datos, calidad |
| **macro** | 4 | 88.418 | ~12.8 MB | Indicadores macroeconómicos y series temporales |
| **equity** | 9 | 3.145.594 | ~507 MB | Acciones, precios, fundamentales, dividendos |
| **fi** | 4 | 32.921 | ~4.7 MB | Renta fija: bonos, ratings, curvas de yield |
| **commodity** | 2 | 21.422 | ~3.3 MB | Materias primas y precios |
| **forex** | 2 | 183.265 | ~27 MB | Pares de divisas y tipos de cambio |
| **crypto** | 3 | 7.890 | ~1.3 MB | Criptomonedas y dominancia |
| **fund** | 2 | 31.475 | ~3.3 MB | ETFs/fondos y NAV |
| **country** | 3 | 1.080 | ~656 KB | Perfiles de país, demografía, impuestos |
| **alt** | 4 | 5.651 | ~688 KB | Datos alternativos: sentimiento, vivienda |

---

## Diagrama de relaciones (Mermaid)

```mermaid
erDiagram

    %% ═══════════════════════════════════════
    %% ESQUEMA: ref (Datos de referencia)
    %% ═══════════════════════════════════════

    ref_country {
        varchar code PK "ISO 3166-1 alpha-2"
        varchar name
        varchar region
        varchar subregion
        varchar capital
        numeric latitude
        numeric longitude
    }

    ref_currency {
        varchar code PK "ISO 4217"
        varchar name
        int decimal_places
    }

    ref_exchange {
        int id PK
        varchar mic "Market Identifier Code"
        varchar name
        varchar country_code FK
        varchar currency_code FK
        varchar timezone
        time open_time
        time close_time
    }

    ref_sector {
        int id PK
        varchar code
        varchar name
        varchar level "sector/industry_group/industry/sub_industry"
        int parent_id FK
    }

    ref_country ||--o{ ref_exchange : "country_code"
    ref_currency ||--o{ ref_exchange : "currency_code"
    ref_sector ||--o{ ref_sector : "parent_id (jerarquia GICS)"

    %% ═══════════════════════════════════════
    %% ESQUEMA: meta (Auditoría)
    %% ═══════════════════════════════════════

    meta_data_source {
        int id PK
        varchar name
        varchar base_url
        numeric rate_limit_rps
        varchar api_key_env
        boolean enabled
    }

    meta_fetch_run {
        int id PK
        varchar source
        varchar domain
        timestamp started_at
        timestamp finished_at
        varchar status
        int rows_fetched
        int errors
        text error_detail
    }

    meta_data_quality {
        int id PK
        varchar schema_name
        varchar table_name
        numeric completeness
        timestamp last_check
    }

    %% ═══════════════════════════════════════
    %% ESQUEMA: macro (Macroeconómico)
    %% ═══════════════════════════════════════

    macro_indicator {
        int id PK
        varchar code
        varchar name
        varchar category
        varchar unit
        varchar frequency
    }

    macro_indicator_source {
        int id PK
        int indicator_id FK
        varchar source_name
        varchar source_code
    }

    macro_series {
        int id PK
        int indicator_id FK
        varchar country_code "ref a ref.country (logica)"
        varchar region
    }

    macro_data_point {
        int id PK
        int series_id FK
        date date
        numeric value
    }

    macro_indicator ||--o{ macro_indicator_source : "indicator_id"
    macro_indicator ||--o{ macro_series : "indicator_id"
    macro_series ||--o{ macro_data_point : "series_id"

    %% ═══════════════════════════════════════
    %% ESQUEMA: equity (Renta variable)
    %% ═══════════════════════════════════════

    equity_company {
        int id PK
        varchar ticker
        varchar isin
        varchar name
        varchar country_code "ref a ref.country (logica)"
        varchar exchange_mic "ref a ref.exchange (logica)"
        varchar sector_code "ref a ref.sector (logica)"
        numeric market_cap
        varchar currency
    }

    equity_price_daily {
        int id PK
        int company_id FK
        date date
        numeric open
        numeric high
        numeric low
        numeric close
        bigint volume
        numeric adj_close
    }

    equity_income_statement {
        int id PK
        int company_id FK
        date period_end
        varchar period_type
        numeric revenue
        numeric gross_profit
        numeric operating_income
        numeric net_income
        numeric eps
        numeric ebitda
    }

    equity_balance_sheet {
        int id PK
        int company_id FK
        date period_end
        varchar period_type
        numeric total_assets
        numeric total_liabilities
        numeric total_equity
        numeric cash
        numeric total_debt
    }

    equity_cash_flow {
        int id PK
        int company_id FK
        date period_end
        varchar period_type
        numeric operating_cf
        numeric investing_cf
        numeric financing_cf
        numeric free_cf
        numeric capex
    }

    equity_dividend {
        int id PK
        int company_id FK
        date ex_date
        date pay_date
        numeric amount
    }

    equity_split {
        int id PK
        int company_id FK
        date date
        numeric ratio_from
        numeric ratio_to
    }

    equity_market_index {
        int id PK
        varchar symbol
        varchar name
        varchar country_code "ref a ref.country (logica)"
    }

    equity_index_price {
        int id PK
        int index_id FK
        date date
        numeric open
        numeric high
        numeric low
        numeric close
        bigint volume
    }

    equity_company ||--o{ equity_price_daily : "company_id"
    equity_company ||--o{ equity_income_statement : "company_id"
    equity_company ||--o{ equity_balance_sheet : "company_id"
    equity_company ||--o{ equity_cash_flow : "company_id"
    equity_company ||--o{ equity_dividend : "company_id"
    equity_company ||--o{ equity_split : "company_id"
    equity_market_index ||--o{ equity_index_price : "index_id"

    %% ═══════════════════════════════════════
    %% ESQUEMA: fi (Renta fija)
    %% ═══════════════════════════════════════

    fi_bond_issuer {
        int id PK
        varchar name
        varchar issuer_type "government/corporate"
        varchar country_code "ref a ref.country (logica)"
    }

    fi_bond {
        int id PK
        int issuer_id FK
        varchar isin
        numeric coupon
        date maturity_date
        varchar currency
    }

    fi_credit_rating {
        int id PK
        int issuer_id FK
        varchar agency "SP/Moodys/Fitch"
        varchar rating
        date date
    }

    fi_yield_curve {
        int id PK
        varchar country_code "ref a ref.country (logica)"
        date date
        varchar maturity
        numeric yield_pct
    }

    fi_bond_issuer ||--o{ fi_bond : "issuer_id"
    fi_bond_issuer ||--o{ fi_credit_rating : "issuer_id"

    %% ═══════════════════════════════════════
    %% ESQUEMA: commodity (Materias primas)
    %% ═══════════════════════════════════════

    commodity_commodity {
        int id PK
        varchar code
        varchar name
        varchar category "energy/metals/agriculture"
        varchar unit
    }

    commodity_price_daily {
        int id PK
        int commodity_id FK
        date date
        numeric open
        numeric high
        numeric low
        numeric close
        bigint volume
    }

    commodity_commodity ||--o{ commodity_price_daily : "commodity_id"

    %% ═══════════════════════════════════════
    %% ESQUEMA: forex (Divisas)
    %% ═══════════════════════════════════════

    forex_currency_pair {
        int id PK
        varchar base_currency "ref a ref.currency (logica)"
        varchar quote_currency "ref a ref.currency (logica)"
        varchar symbol
    }

    forex_rate_daily {
        int id PK
        int pair_id FK
        date date
        numeric open
        numeric high
        numeric low
        numeric close
    }

    forex_currency_pair ||--o{ forex_rate_daily : "pair_id"

    %% ═══════════════════════════════════════
    %% ESQUEMA: crypto (Criptomonedas)
    %% ═══════════════════════════════════════

    crypto_coin {
        int id PK
        varchar coingecko_id
        varchar symbol
        varchar name
    }

    crypto_price_daily {
        int id PK
        int coin_id FK "sin FK formal"
        date date
        numeric price_usd
        numeric volume_usd
        numeric market_cap
    }

    crypto_market_dominance {
        int id PK
        date date
        numeric btc_pct
        numeric eth_pct
    }

    %% ═══════════════════════════════════════
    %% ESQUEMA: fund (Fondos/ETFs)
    %% ═══════════════════════════════════════

    fund_fund {
        int id PK
        varchar ticker
        varchar name
        varchar fund_type "ETF/mutual_fund"
        numeric aum
        numeric expense_ratio
        varchar currency
    }

    fund_nav_daily {
        int id PK
        int fund_id FK
        date date
        numeric nav
        numeric total_return
    }

    fund_fund ||--o{ fund_nav_daily : "fund_id"

    %% ═══════════════════════════════════════
    %% ESQUEMA: country (Perfiles de país)
    %% ═══════════════════════════════════════

    country_profile {
        int id PK
        varchar country_code "ref a ref.country (logica)"
        numeric gdp_usd
        numeric gdp_per_capita
        numeric hdi
        numeric gini
        int ease_of_business_rank
    }

    country_demographics {
        int id PK
        varchar country_code "ref a ref.country (logica)"
        int year
        bigint population
        numeric median_age
        numeric urbanization_pct
        numeric fertility_rate
    }

    country_tax_rate {
        int id PK
        varchar country_code "ref a ref.country (logica)"
        int year
        numeric corporate_tax
        numeric income_tax_max
        numeric vat
        numeric capital_gains_tax
    }

    %% ═══════════════════════════════════════
    %% ESQUEMA: alt (Datos alternativos)
    %% ═══════════════════════════════════════

    alt_sentiment_indicator {
        int id PK
        varchar code
        varchar name
        text description
    }

    alt_sentiment_value {
        int id PK
        int indicator_id FK
        date date
        numeric value
    }

    alt_housing_index {
        int id PK
        varchar code
        varchar name
        varchar country_code "ref a ref.country (logica)"
        varchar index_type
    }

    alt_housing_index_value {
        int id PK
        int index_id FK
        date date
        numeric value
        numeric yoy_change_pct
    }

    alt_sentiment_indicator ||--o{ alt_sentiment_value : "indicator_id"
    alt_housing_index ||--o{ alt_housing_index_value : "index_id"

    %% ═══════════════════════════════════════
    %% RELACIONES LÓGICAS CROSS-SCHEMA
    %% (sin FK formal en la BD)
    %% ═══════════════════════════════════════

    ref_country ||..o{ macro_series : "country_code (logica)"
    ref_country ||..o{ equity_company : "country_code (logica)"
    ref_country ||..o{ fi_bond_issuer : "country_code (logica)"
    ref_country ||..o{ fi_yield_curve : "country_code (logica)"
    ref_country ||..o{ country_profile : "country_code (logica)"
    ref_country ||..o{ country_demographics : "country_code (logica)"
    ref_country ||..o{ country_tax_rate : "country_code (logica)"
    ref_country ||..o{ equity_market_index : "country_code (logica)"
    ref_country ||..o{ alt_housing_index : "country_code (logica)"
```

---

## Relaciones formales (Foreign Keys)

| # | Tabla origen | Columna FK | → Tabla destino | Columna destino |
|---|-------------|-----------|----------------|----------------|
| 1 | `ref.exchange` | `country_code` | → `ref.country` | `code` |
| 2 | `ref.exchange` | `currency_code` | → `ref.currency` | `code` |
| 3 | `ref.sector` | `parent_id` | → `ref.sector` | `id` |
| 4 | `macro.indicator_source` | `indicator_id` | → `macro.indicator` | `id` |
| 5 | `macro.series` | `indicator_id` | → `macro.indicator` | `id` |
| 6 | `macro.data_point` | `series_id` | → `macro.series` | `id` |
| 7 | `equity.price_daily` | `company_id` | → `equity.company` | `id` |
| 8 | `equity.income_statement` | `company_id` | → `equity.company` | `id` |
| 9 | `equity.balance_sheet` | `company_id` | → `equity.company` | `id` |
| 10 | `equity.cash_flow` | `company_id` | → `equity.company` | `id` |
| 11 | `equity.dividend` | `company_id` | → `equity.company` | `id` |
| 12 | `equity.split` | `company_id` | → `equity.company` | `id` |
| 13 | `equity.index_price` | `index_id` | → `equity.market_index` | `id` |
| 14 | `fi.bond` | `issuer_id` | → `fi.bond_issuer` | `id` |
| 15 | `fi.credit_rating` | `issuer_id` | → `fi.bond_issuer` | `id` |
| 16 | `commodity.price_daily` | `commodity_id` | → `commodity.commodity` | `id` |
| 17 | `forex.rate_daily` | `pair_id` | → `forex.currency_pair` | `id` |
| 18 | `fund.nav_daily` | `fund_id` | → `fund.fund` | `id` |
| 19 | `alt.sentiment_value` | `indicator_id` | → `alt.sentiment_indicator` | `id` |
| 20 | `alt.housing_index_value` | `index_id` | → `alt.housing_index` | `id` |

---

## Relaciones lógicas (sin FK formal, por `country_code`)

Muchas tablas usan `country_code` (ISO 3166-1 alpha-2) para vincular con `ref.country`, pero **no tienen FK formal** en la BD. Esto permite flexibilidad pero requiere cuidado al hacer JOINs:

- `macro.series.country_code` → `ref.country.code`
- `equity.company.country_code` → `ref.country.code`
- `equity.market_index.country_code` → `ref.country.code`
- `fi.bond_issuer.country_code` → `ref.country.code`
- `fi.yield_curve.country_code` → `ref.country.code`
- `country.profile.country_code` → `ref.country.code`
- `country.demographics.country_code` → `ref.country.code`
- `country.tax_rate.country_code` → `ref.country.code`
- `alt.housing_index.country_code` → `ref.country.code`
- `forex.currency_pair.base/quote_currency` → `ref.currency.code`
- `equity.company.exchange_mic` → `ref.exchange.mic`
- `equity.company.sector_code` → `ref.sector.code`

---

## Tablas más grandes (datos reales)

| Tabla | Filas | Tamaño |
|-------|-------|--------|
| `equity.price_daily` | 2.934.320 | 476 MB |
| `forex.rate_daily` | 183.235 | 27 MB |
| `equity.dividend` | 135.327 | 15 MB |
| `macro.data_point` | 87.726 | 11 MB |
| `fi.yield_curve` | 32.921 | 4.6 MB |
| `fund.nav_daily` | 31.450 | 3.3 MB |
| `equity.index_price` | 25.089 | 3.7 MB |
| `commodity.price_daily` | 21.405 | 3.3 MB |

---

## Tablas vacías (pendientes de poblar)

- `fi.bond`, `fi.bond_issuer`, `fi.credit_rating` — Renta fija (excepto yield curves)
- `crypto.market_dominance` — Dominancia BTC/ETH
- `country.tax_rate` — Tasas impositivas
- `alt.housing_index`, `alt.housing_index_value` — Índices de vivienda
- `meta.data_quality` — Scores de calidad de datos

---

## Queries de ejemplo para análisis

### Precio de acción + fundamentales de una empresa
```sql
SELECT c.ticker, c.name, p.date, p.close, p.volume,
       i.revenue, i.net_income, i.eps
FROM equity.company c
JOIN equity.price_daily p ON p.company_id = c.id
LEFT JOIN equity.income_statement i ON i.company_id = c.id
WHERE c.ticker = 'AAPL'
ORDER BY p.date DESC LIMIT 10;
```

### PIB per capita + indicadores macro por país
```sql
SELECT rc.name AS pais, mi.name AS indicador,
       dp.date, dp.value
FROM macro.data_point dp
JOIN macro.series s ON s.id = dp.series_id
JOIN macro.indicator mi ON mi.id = s.indicator_id
JOIN ref.country rc ON rc.code = s.country_code
WHERE rc.code = 'ES' AND mi.category = 'gdp'
ORDER BY dp.date DESC;
```

### Correlación: oro vs S&P500
```sql
SELECT g.date, g.close AS gold, sp.close AS sp500
FROM commodity.price_daily g
JOIN commodity.commodity gc ON gc.id = g.commodity_id
CROSS JOIN (
    SELECT ip.date, ip.close
    FROM equity.index_price ip
    JOIN equity.market_index mi ON mi.id = ip.index_id
    WHERE mi.symbol = 'SPX'
) sp ON sp.date = g.date
WHERE gc.code = 'GC'
ORDER BY g.date;
```

### Vista cross-schema: país completo
```sql
SELECT rc.name, rc.region,
       cp.gdp_usd, cp.hdi, cp.gini,
       cd.population, cd.median_age,
       ct.corporate_tax, ct.vat
FROM ref.country rc
LEFT JOIN country.profile cp ON cp.country_code = rc.code
LEFT JOIN country.demographics cd ON cd.country_code = rc.code
LEFT JOIN country.tax_rate ct ON ct.country_code = rc.code
WHERE rc.code = 'ES';
```
