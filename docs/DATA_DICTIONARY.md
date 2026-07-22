# Diccionario de datos — stonks_db

> Generado automáticamente desde el esquema real (`python scripts/gen_data_dictionary.py`).
> No editar a mano. Para el diseño ver [ARCHITECTURE.md](ARCHITECTURE.md) y [SCHEMA_RELATIONS.md](SCHEMA_RELATIONS.md).

## Referencia y metadatos

### Esquema `ref`
_Datos de referencia: países, divisas, bolsas, sectores GICS._

#### `ref.country` · tabla · ~249 filas
País (ISO 3166-1).

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `code` | character varying(3) | no | PK |
| `code_alpha2` | character varying(2) | sí |  |
| `name` | character varying(200) | no |  |
| `region` | character varying(100) | sí |  |
| `sub_region` | character varying(100) | sí |  |
| `income_group` | character varying(50) | sí |  |
| `currency_code` | character varying(3) | sí |  |
| `capital` | character varying(100) | sí |  |
| `latitude` | numeric(9,6) | sí |  |
| `longitude` | numeric(9,6) | sí |  |

#### `ref.currency` · tabla · ~178 filas
Divisa (ISO 4217).

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `code` | character varying(3) | no | PK |
| `name` | character varying(100) | sí |  |
| `symbol` | character varying(10) | sí |  |
| `is_major` | boolean | no |  |
| `decimal_places` | smallint | no |  |

#### `ref.exchange` · tabla · ~0 filas
Bolsa de valores.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `mic` | character varying(10) | sí |  |
| `name` | character varying(200) | no |  |
| `short_name` | character varying(50) | sí |  |
| `country_code` | character varying(3) | sí | FK → ref.country.code |
| `city` | character varying(100) | sí |  |
| `timezone` | character varying(50) | sí |  |
| `currency_code` | character varying(3) | sí | FK → ref.currency.code |
| `open_time` | time without time zone | sí |  |
| `close_time` | time without time zone | sí |  |
| `website` | character varying(300) | sí |  |

#### `ref.sector` · tabla · ~0 filas
Clasificación GICS (sectores/industrias).

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `gics_code` | character varying(10) | sí |  |
| `name` | character varying(200) | no |  |
| `parent_id` | integer | sí | FK → ref.sector.id |
| `level` | smallint | sí |  |

### Esquema `meta`
_Metadatos y auditoría: fuentes, ejecuciones, calidad._

#### `meta.data_quality` · tabla · ~4 filas
Puntuación de calidad por entidad/dominio.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `domain` | character varying(50) | no |  |
| `entity_type` | character varying(100) | no |  |
| `entity_id` | character varying(200) | no |  |
| `completeness_score` | numeric(5,2) | sí |  |
| `freshness_days` | integer | sí |  |
| `source_count` | integer | sí |  |
| `last_assessed` | timestamp without time zone | no |  |

#### `meta.data_source` · tabla · ~0 filas
Registro de fuentes de datos (APIs).

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `name` | character varying(100) | no |  |
| `display_name` | character varying(200) | sí |  |
| `base_url` | character varying(500) | sí |  |
| `api_key_env_var` | character varying(100) | sí |  |
| `rate_limit_per_second` | numeric(6,3) | sí |  |
| `daily_request_limit` | integer | sí |  |
| `is_enabled` | boolean | no |  |
| `notes` | text | sí |  |

#### `meta.fetch_run` · tabla · ~71,134 filas
Auditoría de cada ejecución de descarga.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `source_id` | integer | sí |  |
| `domain` | character varying(50) | no |  |
| `started_at` | timestamp without time zone | no |  |
| `finished_at` | timestamp without time zone | sí |  |
| `status` | character varying(20) | no |  |
| `records_fetched` | integer | no |  |
| `records_inserted` | integer | no |  |
| `records_updated` | integer | no |  |
| `errors` | integer | no |  |
| `params` | jsonb | sí |  |
| `error_log` | jsonb | sí |  |

#### `meta.transform_run` · tabla · ~84 filas
Auditoría de cada transformación (bronze→silver, →gold).

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `domain` | character varying(50) | no |  |
| `target_layer` | character varying(20) | no |  |
| `started_at` | timestamp without time zone | no |  |
| `finished_at` | timestamp without time zone | sí |  |
| `status` | character varying(20) | no |  |
| `records_read` | integer | no |  |
| `records_written` | integer | no |  |
| `records_invalid` | integer | no |  |
| `params` | jsonb | sí |  |
| `error_log` | jsonb | sí |  |

## Renta variable y mercados financieros

### Esquema `equity`
_Renta variable: empresas, precios, fundamentales y 360°._

#### `equity.analyst_estimate` · tabla · ~0 filas
Estimación de consenso de analistas (foto por día).

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `company_id` | integer | no | FK → equity.company.id |
| `snapshot_date` | date | no |  |
| `horizon` | character varying(10) | no |  |
| `period_label` | character varying(20) | sí |  |
| `eps_avg` | numeric(12,4) | sí |  |
| `eps_low` | numeric(12,4) | sí |  |
| `eps_high` | numeric(12,4) | sí |  |
| `revenue_avg` | numeric(20,2) | sí |  |
| `num_analysts` | smallint | sí |  |
| `source_id` | integer | sí | FK → meta.data_source.id |

#### `equity.balance_sheet` · tabla · ~11,119 filas
Balance de situación.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `company_id` | integer | no | FK → equity.company.id |
| `fiscal_year` | smallint | no |  |
| `fiscal_quarter` | smallint | sí |  |
| `period_end_date` | date | sí |  |
| `currency_code` | character varying(3) | sí |  |
| `cash_and_equivalents` | numeric(18,2) | sí |  |
| `short_term_investments` | numeric(18,2) | sí |  |
| `total_current_assets` | numeric(18,2) | sí |  |
| `property_plant_equipment` | numeric(18,2) | sí |  |
| `goodwill` | numeric(18,2) | sí |  |
| `intangible_assets` | numeric(18,2) | sí |  |
| `total_assets` | numeric(18,2) | sí |  |
| `accounts_payable` | numeric(18,2) | sí |  |
| `short_term_debt` | numeric(18,2) | sí |  |
| `total_current_liabilities` | numeric(18,2) | sí |  |
| `long_term_debt` | numeric(18,2) | sí |  |
| `total_liabilities` | numeric(18,2) | sí |  |
| `total_stockholders_equity` | numeric(18,2) | sí |  |
| `retained_earnings` | numeric(18,2) | sí |  |
| `total_equity` | numeric(18,2) | sí |  |
| `source_id` | integer | sí | FK → meta.data_source.id |
| `fetched_at` | timestamp without time zone | no |  |

#### `equity.cash_flow` · tabla · ~11,214 filas
Estado de flujos de efectivo.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `company_id` | integer | no | FK → equity.company.id |
| `fiscal_year` | smallint | no |  |
| `fiscal_quarter` | smallint | sí |  |
| `period_end_date` | date | sí |  |
| `currency_code` | character varying(3) | sí |  |
| `operating_cash_flow` | numeric(18,2) | sí |  |
| `capital_expenditure` | numeric(18,2) | sí |  |
| `free_cash_flow` | numeric(18,2) | sí |  |
| `dividends_paid` | numeric(18,2) | sí |  |
| `share_buyback` | numeric(18,2) | sí |  |
| `debt_issued` | numeric(18,2) | sí |  |
| `debt_repaid` | numeric(18,2) | sí |  |
| `investing_cash_flow` | numeric(18,2) | sí |  |
| `financing_cash_flow` | numeric(18,2) | sí |  |
| `net_change_cash` | numeric(18,2) | sí |  |
| `source_id` | integer | sí | FK → meta.data_source.id |
| `fetched_at` | timestamp without time zone | no |  |

#### `equity.company` · tabla · ~2,446 filas
Empresa cotizada.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `name` | character varying(500) | no |  |
| `ticker` | character varying(20) | no |  |
| `isin` | character varying(12) | sí |  |
| `exchange_id` | integer | sí | FK → ref.exchange.id |
| `sector_id` | integer | sí | FK → ref.sector.id |
| `country_code` | character varying(3) | sí | FK → ref.country.code |
| `currency_code` | character varying(3) | sí | FK → ref.currency.code |
| `market_cap_usd` | numeric(18,2) | sí |  |
| `shares_outstanding` | bigint | sí |  |
| `ipo_date` | date | sí |  |
| `delisted_date` | date | sí |  |
| `is_active` | boolean | no |  |
| `website` | character varying(300) | sí |  |
| `description` | text | sí |  |
| `employees` | integer | sí |  |
| `last_updated` | timestamp without time zone | no |  |

#### `equity.dividend` · tabla · ~134,600 filas
Dividendos.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `company_id` | integer | no | FK → equity.company.id |
| `ex_date` | date | no |  |
| `pay_date` | date | sí |  |
| `record_date` | date | sí |  |
| `amount` | numeric(12,6) | no |  |
| `currency_code` | character varying(3) | sí |  |
| `dividend_type` | character varying(20) | sí |  |

#### `equity.earnings_date` · tabla · ~100,804 filas
Fecha de resultados: estimado vs reportado.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `company_id` | integer | no | FK → equity.company.id |
| `date` | date | no |  |
| `eps_estimate` | numeric(12,4) | sí |  |
| `reported_eps` | numeric(12,4) | sí |  |
| `surprise_pct` | numeric(10,4) | sí |  |

#### `equity.earnings_revision` · tabla · ~0 filas
Revisiones de estimaciones de EPS (foto por día).

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `company_id` | integer | no | FK → equity.company.id |
| `snapshot_date` | date | no |  |
| `horizon` | character varying(10) | no |  |
| `eps_current` | numeric(12,4) | sí |  |
| `eps_7d_ago` | numeric(12,4) | sí |  |
| `eps_30d_ago` | numeric(12,4) | sí |  |
| `up_last_30d` | smallint | sí |  |
| `down_last_30d` | smallint | sí |  |
| `source_id` | integer | sí | FK → meta.data_source.id |

#### `equity.holder` · tabla · ~34,656 filas
Accionista institucional o fondo (foto por captura).

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | bigint | no | PK |
| `company_id` | integer | no | FK → equity.company.id |
| `holder_type` | character varying(20) | no |  |
| `holder_name` | character varying(200) | no |  |
| `snapshot_date` | date | no |  |
| `date_reported` | date | sí |  |
| `pct_held` | numeric(9,6) | sí |  |
| `shares` | bigint | sí |  |
| `value_usd` | numeric(20,2) | sí |  |

#### `equity.income_statement` · tabla · ~11,053 filas
Cuenta de resultados.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `company_id` | integer | no | FK → equity.company.id |
| `fiscal_year` | smallint | no |  |
| `fiscal_quarter` | smallint | sí |  |
| `period_end_date` | date | sí |  |
| `currency_code` | character varying(3) | sí |  |
| `revenue` | numeric(18,2) | sí |  |
| `cost_of_revenue` | numeric(18,2) | sí |  |
| `gross_profit` | numeric(18,2) | sí |  |
| `operating_expenses` | numeric(18,2) | sí |  |
| `operating_income` | numeric(18,2) | sí |  |
| `interest_expense` | numeric(18,2) | sí |  |
| `pretax_income` | numeric(18,2) | sí |  |
| `income_tax` | numeric(18,2) | sí |  |
| `net_income` | numeric(18,2) | sí |  |
| `eps_basic` | numeric(10,4) | sí |  |
| `eps_diluted` | numeric(10,4) | sí |  |
| `shares_basic` | bigint | sí |  |
| `shares_diluted` | bigint | sí |  |
| `ebitda` | numeric(18,2) | sí |  |
| `source_id` | integer | sí | FK → meta.data_source.id |
| `fetched_at` | timestamp without time zone | no |  |

#### `equity.index_constituent_current` · tabla · ~503 filas
Constituyentes ACTUALES de un índice (snapshot sin historial).

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `index_id` | integer | no | FK → equity.market_index.id |
| `company_id` | integer | no | FK → equity.company.id |
| `weight` | numeric(8,5) | sí |  |
| `as_of_date` | date | no |  |
| `source_id` | integer | sí | FK → meta.data_source.id |

#### `equity.index_price` · tabla · ~189,345 filas
Precio diario de un índice.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `index_id` | integer | no | FK → equity.market_index.id |
| `date` | date | no |  |
| `open` | numeric(14,4) | sí |  |
| `high` | numeric(14,4) | sí |  |
| `low` | numeric(14,4) | sí |  |
| `close` | numeric(14,4) | no |  |
| `volume` | bigint | sí |  |

#### `equity.insider_transaction` · tabla · ~121,912 filas
Operación de un insider (compra/venta).

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | bigint | no | PK |
| `company_id` | integer | no | FK → equity.company.id |
| `insider` | character varying(200) | no |  |
| `position` | character varying(200) | sí |  |
| `transaction` | character varying(100) | sí |  |
| `start_date` | date | sí |  |
| `shares` | bigint | sí |  |
| `value_usd` | numeric(20,2) | sí |  |

#### `equity.market_index` · tabla · ~0 filas
Índice de mercado.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `code` | character varying(50) | no |  |
| `name` | character varying(200) | no |  |
| `country_code` | character varying(3) | sí | FK → ref.country.code |
| `exchange_id` | integer | sí | FK → ref.exchange.id |
| `currency_code` | character varying(3) | sí |  |
| `description` | text | sí |  |

#### `equity.price_daily` · tabla · ~9,332,877 filas
Precio diario OHLCV.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `company_id` | integer | no | FK → equity.company.id |
| `date` | date | no |  |
| `open` | numeric(14,4) | sí |  |
| `high` | numeric(14,4) | sí |  |
| `low` | numeric(14,4) | sí |  |
| `close` | numeric(14,4) | no |  |
| `adj_close` | numeric(14,4) | sí |  |
| `volume` | bigint | sí |  |
| `source_id` | integer | sí | FK → meta.data_source.id |

#### `equity.ratios_mv` · materializada · ~2,412 filas
| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `company_id` | integer | sí |  |
| `ticker` | character varying(20) | sí |  |
| `sector_id` | integer | sí |  |
| `country_code` | character varying(3) | sí |  |
| `currency_code` | character varying(3) | sí |  |
| `market_cap_usd` | numeric(18,2) | sí |  |
| `shares_outstanding` | bigint | sí |  |
| `price_date` | date | sí |  |
| `income_period` | date | sí |  |
| `balance_period` | date | sí |  |
| `cashflow_period` | date | sí |  |
| `last_close` | numeric(14,4) | sí |  |
| `pe_ratio` | numeric | sí |  |
| `pb_ratio` | numeric | sí |  |
| `ps_ratio` | numeric | sí |  |
| `roe` | numeric | sí |  |
| `roa` | numeric | sí |  |
| `roic` | numeric | sí |  |
| `gross_margin` | numeric | sí |  |
| `operating_margin` | numeric | sí |  |
| `net_margin` | numeric | sí |  |
| `debt_equity` | numeric | sí |  |
| `debt_assets` | numeric | sí |  |
| `fcf_yield` | numeric | sí |  |
| `revenue` | numeric(18,2) | sí |  |
| `net_income` | numeric(18,2) | sí |  |
| `ebitda` | numeric(18,2) | sí |  |
| `eps_diluted` | numeric(10,4) | sí |  |
| `total_equity` | numeric(18,2) | sí |  |
| `total_assets` | numeric(18,2) | sí |  |
| `free_cash_flow` | numeric(18,2) | sí |  |
| `operating_cash_flow` | numeric(18,2) | sí |  |

#### `equity.recommendation_trend` · tabla · ~8,073 filas
Resumen de recomendaciones (nº de analistas por categoría).

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `company_id` | integer | no | FK → equity.company.id |
| `snapshot_date` | date | no |  |
| `period` | character varying(10) | no |  |
| `strong_buy` | smallint | sí |  |
| `buy` | smallint | sí |  |
| `hold` | smallint | sí |  |
| `sell` | smallint | sí |  |
| `strong_sell` | smallint | sí |  |

#### `equity.shares_history` · tabla · ~1,287,132 filas
Acciones en circulación a lo largo del tiempo.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | bigint | no | PK |
| `company_id` | integer | no | FK → equity.company.id |
| `date` | date | no |  |
| `shares` | bigint | sí |  |

#### `equity.split` · tabla · ~4,564 filas
Stock splits.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `company_id` | integer | no | FK → equity.company.id |
| `date` | date | no |  |
| `ratio_from` | numeric(10,4) | sí |  |
| `ratio_to` | numeric(10,4) | sí |  |

#### `equity.upgrade_downgrade` · tabla · ~289,296 filas
Cambio de recomendación/precio objetivo de una firma.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | bigint | no | PK |
| `company_id` | integer | no | FK → equity.company.id |
| `date` | date | no |  |
| `firm` | character varying(200) | no |  |
| `to_grade` | character varying(100) | sí |  |
| `from_grade` | character varying(100) | sí |  |
| `action` | character varying(50) | sí |  |
| `price_target` | numeric(14,4) | sí |  |

### Esquema `fi`
_Renta fija: bonos, ratings, curvas de tipos._

#### `fi.bond` · tabla · ~5,015 filas
Bono individual.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `issuer_id` | integer | sí | FK → fi.bond_issuer.id |
| `isin` | character varying(12) | sí |  |
| `name` | character varying(300) | sí |  |
| `coupon_rate` | numeric(8,4) | sí |  |
| `coupon_frequency` | smallint | sí |  |
| `maturity_date` | date | sí |  |
| `issue_date` | date | sí |  |
| `face_value` | numeric(14,2) | sí |  |
| `currency_code` | character varying(3) | sí |  |
| `bond_type` | character varying(30) | sí |  |
| `is_callable` | boolean | no |  |

#### `fi.bond_issuer` · tabla · ~53 filas
Emisor de bonos.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `name` | character varying(300) | sí |  |
| `issuer_type` | character varying(20) | no |  |
| `country_code` | character varying(3) | sí | FK → ref.country.code |

#### `fi.credit_rating` · tabla · ~10,563 filas
Rating crediticio.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `issuer_id` | integer | no | FK → fi.bond_issuer.id |
| `agency` | character varying(20) | no |  |
| `rating` | character varying(10) | no |  |
| `outlook` | character varying(20) | sí |  |
| `rating_date` | date | no |  |
| `previous_rating` | character varying(10) | sí |  |

#### `fi.yield_curve` · tabla · ~68,072 filas
Punto de curva de tipos por país y fecha.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `country_code` | character varying(3) | no | FK → ref.country.code |
| `date` | date | no |  |
| `maturity_months` | smallint | no |  |
| `yield_pct` | numeric(8,4) | no |  |
| `source_id` | integer | sí | FK → meta.data_source.id |

### Esquema `commodity`
_Materias primas y sus precios._

#### `commodity.commodity` · tabla · ~0 filas
Materia prima.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `code` | character varying(20) | no |  |
| `name` | character varying(200) | no |  |
| `category` | character varying(50) | sí |  |
| `subcategory` | character varying(50) | sí |  |
| `unit` | character varying(50) | sí |  |
| `currency_code` | character varying(3) | sí |  |
| `exchange` | character varying(50) | sí |  |
| `yfinance_ticker` | character varying(20) | sí |  |

#### `commodity.price_daily` · tabla · ~104,882 filas
Precio diario de materia prima.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `commodity_id` | integer | no | FK → commodity.commodity.id |
| `date` | date | no |  |
| `open` | numeric(14,4) | sí |  |
| `high` | numeric(14,4) | sí |  |
| `low` | numeric(14,4) | sí |  |
| `close` | numeric(14,4) | no |  |
| `volume` | bigint | sí |  |
| `source_id` | integer | sí | FK → meta.data_source.id |

### Esquema `forex`
_Divisas y tipos de cambio._

#### `forex.currency_pair` · tabla · ~0 filas
Par de divisas.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `base_currency` | character varying(3) | no | FK → ref.currency.code |
| `quote_currency` | character varying(3) | no | FK → ref.currency.code |
| `pair_code` | character varying(7) | no |  |
| `category` | character varying(20) | sí |  |

#### `forex.rate_daily` · tabla · ~183,177 filas
Tipo de cambio diario.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `pair_id` | integer | no | FK → forex.currency_pair.id |
| `date` | date | no |  |
| `open` | numeric(14,8) | sí |  |
| `high` | numeric(14,8) | sí |  |
| `low` | numeric(14,8) | sí |  |
| `close` | numeric(14,8) | no |  |
| `source_id` | integer | sí | FK → meta.data_source.id |

### Esquema `crypto`
_Criptomonedas._

#### `crypto.coin` · tabla · ~0 filas
Criptomoneda.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `coingecko_id` | character varying(100) | no |  |
| `symbol` | character varying(20) | no |  |
| `name` | character varying(200) | no |  |
| `category` | character varying(50) | sí |  |
| `market_cap_rank` | smallint | sí |  |

#### `crypto.market_dominance` · tabla · ~0 filas
Snapshot diario del mercado crypto.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `date` | date | no |  |
| `total_market_cap_usd` | numeric(18,2) | sí |  |
| `btc_dominance_pct` | numeric(6,3) | sí |  |
| `eth_dominance_pct` | numeric(6,3) | sí |  |

#### `crypto.price_daily` · tabla · ~13,482 filas
Precio diario de criptomoneda.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `coin_id` | integer | no |  |
| `date` | date | no |  |
| `open` | numeric(18,8) | sí |  |
| `high` | numeric(18,8) | sí |  |
| `low` | numeric(18,8) | sí |  |
| `close` | numeric(18,8) | no |  |
| `volume_usd` | numeric(18,2) | sí |  |
| `market_cap_usd` | numeric(18,2) | sí |  |

### Esquema `fund`
_ETFs y fondos._

#### `fund.fund` · tabla · ~25 filas
Fondo / ETF.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `ticker` | character varying(20) | sí |  |
| `name` | character varying(500) | no |  |
| `fund_type` | character varying(20) | no |  |
| `asset_class` | character varying(50) | sí |  |
| `geography` | character varying(100) | sí |  |
| `strategy` | character varying(100) | sí |  |
| `provider` | character varying(100) | sí |  |
| `expense_ratio` | numeric(6,4) | sí |  |
| `aum_usd` | numeric(18,2) | sí |  |
| `inception_date` | date | sí |  |
| `currency_code` | character varying(3) | sí |  |
| `exchange_id` | integer | sí | FK → ref.exchange.id |
| `is_active` | boolean | no |  |

#### `fund.nav_daily` · tabla · ~132,304 filas
NAV diario del fondo.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `fund_id` | integer | no | FK → fund.fund.id |
| `date` | date | no |  |
| `nav` | numeric(14,6) | no |  |
| `volume` | integer | sí |  |

### Esquema `alt`
_Datos alternativos: sentimiento, vivienda._

#### `alt.housing_index` · tabla · ~0 filas
Índice inmobiliario.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `code` | character varying(50) | no |  |
| `name` | character varying(200) | sí |  |
| `country_code` | character varying(3) | sí | FK → ref.country.code |
| `index_type` | character varying(50) | sí |  |

#### `alt.housing_index_value` · tabla · ~0 filas
Valor de índice inmobiliario.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `index_id` | integer | no | FK → alt.housing_index.id |
| `date` | date | no |  |
| `value` | numeric(12,4) | no |  |
| `yoy_change_pct` | numeric(8,4) | sí |  |

#### `alt.sentiment_indicator` · tabla · ~0 filas
Definición de indicador de sentimiento.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `code` | character varying(50) | no |  |
| `name` | character varying(200) | sí |  |
| `description` | text | sí |  |

#### `alt.sentiment_value` · tabla · ~6,254 filas
Valor diario de indicador de sentimiento.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `indicator_id` | integer | no | FK → alt.sentiment_indicator.id |
| `date` | date | no |  |
| `value` | numeric(12,4) | no |  |

## Economía mundial

### Esquema `macro`
_Economía mundial como series país × indicador × fecha._

#### `macro.data_point` · tabla · ~2,870,193 filas
Punto de datos de una serie temporal.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `series_id` | integer | no | FK → macro.series.id |
| `date` | date | no |  |
| `value` | numeric(20,6) | no |  |
| `source_id` | integer | sí | FK → meta.data_source.id |
| `fetched_at` | timestamp without time zone | no |  |

#### `macro.indicator` · tabla · ~1,669 filas
Definición de un indicador macroeconómico.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `code` | character varying(100) | no |  |
| `name` | character varying(300) | no |  |
| `category` | character varying(100) | sí |  |
| `subcategory` | character varying(100) | sí |  |
| `unit` | character varying(50) | sí |  |
| `frequency` | character varying(20) | sí |  |
| `seasonal_adjustment` | character varying(20) | sí |  |
| `description` | text | sí |  |

#### `macro.indicator_source` · tabla · ~1,636 filas
Mapeo indicador → código en fuente externa.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `indicator_id` | integer | no | FK → macro.indicator.id |
| `source_id` | integer | no | FK → meta.data_source.id |
| `external_code` | character varying(200) | no |  |
| `external_name` | character varying(500) | sí |  |
| `priority` | smallint | no |  |

#### `macro.series` · tabla · ~87,854 filas
Serie temporal: indicador + país.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `indicator_id` | integer | no | FK → macro.indicator.id |
| `country_code` | character varying(3) | sí | FK → ref.country.code |
| `region_code` | character varying(20) | sí |  |
| `last_value` | numeric(20,6) | sí |  |
| `last_date` | date | sí |  |
| `point_count` | integer | no |  |

### Esquema `trade`
_Comercio internacional bilateral (país × socio)._

#### `trade.flow` · tabla · ~973,418 filas
Flujo comercial bilateral (exportación/importación).

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | bigint | no | PK |
| `reporter_code` | character varying(3) | no | FK → ref.country.code |
| `partner_code` | character varying(3) | no |  |
| `product_code` | character varying(20) | no |  |
| `flow` | character varying(1) | no |  |
| `period` | smallint | no |  |
| `value_usd_k` | numeric(20,3) | sí |  |
| `source_id` | integer | sí | FK → meta.data_source.id |
| `fetched_at` | timestamp without time zone | no |  |

### Esquema `energy`
_Balance energético por país, fuente y flujo._

#### `energy.balance` · tabla · ~185,679 filas
Balance energético por país, fuente y flujo.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | bigint | no | PK |
| `country_code` | character varying(3) | no | FK → ref.country.code |
| `product_code` | character varying(30) | no |  |
| `flow` | character varying(20) | no |  |
| `period` | smallint | no |  |
| `value` | numeric(18,4) | sí |  |
| `unit` | character varying(20) | sí |  |
| `source_id` | integer | sí | FK → meta.data_source.id |
| `fetched_at` | timestamp without time zone | no |  |

### Esquema `agri`
_Producción agrícola por país, cultivo/ganado y elemento._

#### `agri.production` · tabla · ~2,929,268 filas
Producción agrícola por país, item y elemento.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | bigint | no | PK |
| `country_code` | character varying(3) | no | FK → ref.country.code |
| `item_code` | character varying(20) | no |  |
| `item_name` | character varying(200) | sí |  |
| `element` | character varying(60) | no |  |
| `period` | smallint | no |  |
| `value` | numeric(24,3) | sí |  |
| `unit` | character varying(40) | sí |  |
| `source_id` | integer | sí | FK → meta.data_source.id |
| `fetched_at` | timestamp without time zone | no |  |

### Esquema `country`
_Perfiles de país: demografía, impuestos._

#### `country.demographics` · tabla · ~1,040 filas
Datos demográficos por país y año.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `country_code` | character varying(3) | no | FK → ref.country.code |
| `year` | smallint | no |  |
| `total_population` | bigint | sí |  |
| `median_age` | numeric(5,2) | sí |  |
| `urban_population_pct` | numeric(6,3) | sí |  |
| `life_expectancy` | numeric(5,2) | sí |  |
| `fertility_rate` | numeric(4,2) | sí |  |
| `labor_force` | bigint | sí |  |

#### `country.profile` · tabla · ~40 filas
Perfil económico de un país.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `country_code` | character varying(3) | no | PK |
| `population` | bigint | sí |  |
| `population_year` | smallint | sí |  |
| `gdp_usd` | numeric(18,2) | sí |  |
| `gdp_per_capita_usd` | numeric(12,2) | sí |  |
| `hdi` | numeric(5,4) | sí |  |
| `gini_index` | numeric(5,2) | sí |  |
| `ease_of_business_rank` | smallint | sí |  |
| `political_stability_index` | numeric(6,4) | sí |  |
| `last_updated` | timestamp without time zone | sí |  |

#### `country.tax_rate` · tabla · ~0 filas
Tipos impositivos por país y año.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `country_code` | character varying(3) | no | FK → ref.country.code |
| `year` | smallint | no |  |
| `corporate_tax_rate` | numeric(6,3) | sí |  |
| `top_income_tax_rate` | numeric(6,3) | sí |  |
| `vat_rate` | numeric(6,3) | sí |  |
| `capital_gains_tax_rate` | numeric(6,3) | sí |  |

## Derivados

### Esquema `deriv`
_Derivados: snapshots de cadenas de opciones._

#### `deriv.option_snapshot` · tabla · ~2,113 filas
Foto de un contrato de opción (call/put).

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | bigint | no | PK |
| `company_id` | integer | no | FK → equity.company.id |
| `snapshot_date` | date | no |  |
| `expiry` | date | no |  |
| `option_type` | character varying(1) | no |  |
| `strike` | numeric(14,4) | no |  |
| `last_price` | numeric(14,4) | sí |  |
| `bid` | numeric(14,4) | sí |  |
| `ask` | numeric(14,4) | sí |  |
| `volume` | integer | sí |  |
| `open_interest` | integer | sí |  |
| `implied_vol` | numeric(10,6) | sí |  |
| `fetched_at` | timestamp without time zone | no |  |

## Medallion — aterrizaje y analítica

### Esquema `bronze`
_Aterrizaje crudo (JSONB) de las fuentes nuevas._

#### `bronze.analyst_snapshot` · tabla · ~0 filas
Foto diaria de datos de analistas de yfinance (por ticker).

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | bigint | no | PK |
| `fetch_run_id` | integer | sí |  |
| `ingested_at` | timestamp without time zone | no |  |
| `ticker` | character varying(20) | no |  |
| `snapshot_date` | date | no |  |
| `payload` | jsonb | no |  |

#### `bronze.api_response` · tabla · ~316 filas
Respuesta cruda de una API macro (genérica, append-only).

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | bigint | no | PK |
| `fetch_run_id` | integer | sí |  |
| `ingested_at` | timestamp without time zone | no |  |
| `source_name` | character varying(50) | no |  |
| `dataset` | character varying(120) | no |  |
| `params` | jsonb | sí |  |
| `payload` | jsonb | no |  |

#### `bronze.constituents_snapshot` · tabla · ~0 filas
Foto cruda de constituyentes de un índice (Wikipedia/GitHub).

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | bigint | no | PK |
| `fetch_run_id` | integer | sí |  |
| `ingested_at` | timestamp without time zone | no |  |
| `index_code` | character varying(50) | no |  |
| `source_kind` | character varying(30) | no |  |
| `payload` | jsonb | no |  |

#### `bronze.sec_companyfacts` · tabla · ~1,420 filas
JSON crudo de la API companyfacts de SEC EDGAR (por empresa).

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | bigint | no | PK |
| `fetch_run_id` | integer | sí |  |
| `ingested_at` | timestamp without time zone | no |  |
| `cik` | character varying(10) | no |  |
| `ticker` | character varying(20) | sí |  |
| `payload` | jsonb | no |  |

#### `bronze.yf_profile` · tabla · ~2,170 filas
Volcado completo del `.info` de yfinance por empresa (foto).

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | bigint | no | PK |
| `fetch_run_id` | integer | sí |  |
| `ingested_at` | timestamp without time zone | no |  |
| `ticker` | character varying(20) | no |  |
| `snapshot_date` | date | no |  |
| `payload` | jsonb | no |  |

### Esquema `gold`
_Capa analítica point-in-time: hechos, dimensiones y marts._

#### `gold.dim_company` · tabla · ~3,014 filas
Dimensión de empresa (SCD-1; sector desnormalizado).

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `company_key` | integer | no | PK |
| `company_id` | integer | no | FK → equity.company.id |
| `ticker` | character varying(20) | no |  |
| `name` | character varying(500) | sí |  |
| `sector_id` | integer | sí |  |
| `sector_name` | character varying(200) | sí |  |
| `industry_id` | integer | sí |  |
| `country_code` | character varying(3) | sí |  |
| `currency_code` | character varying(3) | sí |  |
| `is_active` | boolean | no |  |
| `delisted_date` | date | sí |  |

#### `gold.dim_country` · tabla · ~249 filas
Dimensión de país (economía mundial).

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `country_code` | character varying(3) | no | PK |
| `name` | character varying(200) | no |  |
| `region` | character varying(100) | sí |  |
| `sub_region` | character varying(100) | sí |  |
| `income_group` | character varying(50) | sí |  |

#### `gold.dim_date` · tabla · ~23,552 filas
Dimensión de fecha (1 fila por día calendario).

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `date_key` | date | no | PK |
| `year` | smallint | no |  |
| `quarter` | smallint | no |  |
| `month` | smallint | no |  |
| `day_of_week` | smallint | no |  |
| `is_month_end` | boolean | no |  |
| `is_trading_day` | boolean | sí |  |

#### `gold.dim_indicator` · vista · ~0 filas
Catálogo autodocumentado de indicadores macro (código, fuente, cobertura, rango).

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `code` | character varying(100) | sí |  |
| `name` | character varying(300) | sí |  |
| `category` | character varying(100) | sí |  |
| `unit` | character varying(50) | sí |  |
| `frequency` | character varying(20) | sí |  |
| `sources` | text | sí |  |
| `n_countries` | bigint | sí |  |
| `first_date` | date | sí |  |
| `last_date` | date | sí |  |
| `n_points` | bigint | sí |  |

#### `gold.fact_factor_scores` · tabla · ~170,960 filas
Scores de factores cross-section, neutralizados por sector.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | bigint | no | PK |
| `company_id` | integer | no | FK → equity.company.id |
| `as_of_date` | date | no |  |
| `factor` | character varying(30) | no |  |
| `universe` | character varying(30) | no |  |
| `raw_value` | numeric(18,6) | sí |  |
| `z_score` | numeric(10,6) | sí |  |
| `z_sector_neutral` | numeric(10,6) | sí |  |
| `percentile` | numeric(6,4) | sí |  |
| `source_id` | integer | sí |  |

#### `gold.fact_fundamentals_pit` · tabla · ~12,826,841 filas
Hecho fundamental point-in-time (formato long, una métrica/fila).

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | bigint | no | PK |
| `company_id` | integer | no | FK → equity.company.id |
| `statement_type` | character varying(10) | no |  |
| `fiscal_year` | smallint | no |  |
| `fiscal_quarter` | smallint | sí |  |
| `period_end_date` | date | no |  |
| `filed_date` | date | no |  |
| `publish_date` | date | sí |  |
| `metric` | character varying(150) | no |  |
| `value` | numeric(28,6) | sí |  |
| `currency_code` | character varying(3) | sí |  |
| `form` | character varying(10) | sí |  |
| `source_id` | integer | sí |  |

#### `gold.index_membership` · tabla · ~1,255 filas
Pertenencia point-in-time de una empresa a un índice.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | integer | no | PK |
| `index_id` | integer | no | FK → equity.market_index.id |
| `company_id` | integer | no | FK → equity.company.id |
| `ticker` | character varying(20) | no |  |
| `start_date` | date | no |  |
| `end_date` | date | sí |  |
| `source_id` | integer | sí |  |

#### `gold.mart_benchmark_returns` · materializada · ~32,440 filas
Retorno diario del pool S&P 500 equiponderado (survivorship-free) vs SPY.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `date` | date | sí |  |
| `method` | character varying(20) | sí |  |
| `ret` | numeric | sí |  |

#### `gold.mart_country_year` · materializada · ~38,444 filas
Panel ancho país × año: macro + energía + comercio + emisiones (tabla analítica principal).

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `country_code` | character varying(3) | sí |  |
| `year` | smallint | sí |  |
| `gdp_usd_bn` | numeric | sí |  |
| `gdp_per_capita_usd` | numeric | sí |  |
| `gdp_growth_pct` | numeric | sí |  |
| `gdp_ppp_bn` | numeric | sí |  |
| `inflation_pct` | numeric | sí |  |
| `unemployment_pct` | numeric | sí |  |
| `population_mn` | numeric | sí |  |
| `gov_debt_pct_gdp` | numeric | sí |  |
| `gov_balance_pct_gdp` | numeric | sí |  |
| `current_account_pct_gdp` | numeric | sí |  |
| `gdp_ppp_per_capita` | numeric | sí |  |
| `share_world_gdp_ppp_pct` | numeric | sí |  |
| `savings_pct_gdp` | numeric | sí |  |
| `investment_pct_gdp` | numeric | sí |  |
| `gov_revenue_pct_gdp` | numeric | sí |  |
| `gov_expenditure_pct_gdp` | numeric | sí |  |
| `co2_mt` | numeric | sí |  |
| `co2_per_capita_t` | numeric | sí |  |
| `co2_share_global_pct` | numeric | sí |  |
| `ghg_mt` | numeric | sí |  |
| `primary_energy_twh` | numeric | sí |  |
| `electricity_twh` | numeric | sí |  |
| `renewables_elec_twh` | numeric | sí |  |
| `renewables_share_elec_pct` | numeric | sí |  |
| `exports_usd_bn` | numeric | sí |  |
| `imports_usd_bn` | numeric | sí |  |
| `trade_balance_usd_bn` | numeric | sí |  |

#### `gold.mart_pool_membership` · vista · ~0 filas
Universo S&P 500 point-in-time expandido a días de cotización.

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `index_id` | integer | sí |  |
| `company_id` | integer | sí |  |
| `date` | date | sí |  |

#### `gold.mart_trade_matrix` · materializada · ~442,027 filas
Matriz de comercio bilateral reporter × partner × año (exportaciones e importaciones).

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `reporter_code` | character varying(3) | sí |  |
| `partner_code` | character varying(3) | sí |  |
| `year` | smallint | sí |  |
| `exports_usd_k` | numeric(20,3) | sí |  |
| `imports_usd_k` | numeric(20,3) | sí |  |
