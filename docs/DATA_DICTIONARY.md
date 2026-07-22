# Diccionario de datos — stonks_db

> Generado automáticamente desde el esquema real (`python scripts/gen_data_dictionary.py`).
> No editar a mano. Para el diseño ver [ARCHITECTURE.md](ARCHITECTURE.md) y [SCHEMA_RELATIONS.md](SCHEMA_RELATIONS.md).

Este documento explica **en lenguaje llano qué es cada tabla y cada columna** de la base de datos. Está agrupado por temas.

Cómo leer cada tabla:
- **Columna**: el nombre técnico del campo.
- **Qué es**: explicación sencilla de lo que guarda.
- **Tipo**: formato del dato (número, texto, fecha...).
- **Nulo**: si puede estar vacío.
- **Clave**: `PK` = identifica la fila; `FK →` = enlaza con otra tabla.

## Referencia y metadatos

### Esquema `ref`
_Datos de referencia: países, divisas, bolsas, sectores GICS._

#### `ref.country` · tabla · ~249 filas
Lista de países del mundo, con su código ISO.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `code` | Código identificador. | character varying(3) | no | PK |
| `code_alpha2` |  | character varying(2) | sí |  |
| `name` | Nombre. | character varying(200) | no |  |
| `region` |  | character varying(100) | sí |  |
| `sub_region` |  | character varying(100) | sí |  |
| `income_group` |  | character varying(50) | sí |  |
| `currency_code` | Moneda del importe. | character varying(3) | sí |  |
| `capital` |  | character varying(100) | sí |  |
| `latitude` |  | numeric(9,6) | sí |  |
| `longitude` |  | numeric(9,6) | sí |  |

#### `ref.currency` · tabla · ~178 filas
Lista de monedas (euro, dólar...).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `code` | Código identificador. | character varying(3) | no | PK |
| `name` | Nombre. | character varying(100) | sí |  |
| `symbol` |  | character varying(10) | sí |  |
| `is_major` |  | boolean | no |  |
| `decimal_places` |  | smallint | no |  |

#### `ref.exchange` · tabla · ~0 filas
Bolsas de valores (Nasdaq, NYSE...).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `mic` |  | character varying(10) | sí |  |
| `name` | Nombre. | character varying(200) | no |  |
| `short_name` |  | character varying(50) | sí |  |
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | sí | FK → ref.country.code |
| `city` |  | character varying(100) | sí |  |
| `timezone` |  | character varying(50) | sí |  |
| `currency_code` | Moneda del importe. | character varying(3) | sí | FK → ref.currency.code |
| `open_time` |  | time without time zone | sí |  |
| `close_time` |  | time without time zone | sí |  |
| `website` | Web de la empresa. | character varying(300) | sí |  |

#### `ref.sector` · tabla · ~0 filas
Sectores económicos GICS (Tecnología, Salud...).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `gics_code` |  | character varying(10) | sí |  |
| `name` | Nombre. | character varying(200) | no |  |
| `parent_id` |  | integer | sí | FK → ref.sector.id |
| `level` |  | smallint | sí |  |

### Esquema `meta`
_Metadatos y auditoría: fuentes, ejecuciones, calidad._

#### `meta.data_quality` · tabla · ~4 filas
Nota de calidad por dominio: cuántos países cubrimos y cómo de reciente es el dato.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `domain` |  | character varying(50) | no |  |
| `entity_type` |  | character varying(100) | no |  |
| `entity_id` |  | character varying(200) | no |  |
| `completeness_score` |  | numeric(5,2) | sí |  |
| `freshness_days` |  | integer | sí |  |
| `source_count` |  | integer | sí |  |
| `last_assessed` |  | timestamp without time zone | no |  |

#### `meta.data_source` · tabla · ~0 filas
Las fuentes de donde sacamos los datos (IMF, yfinance, SEC...).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `name` | Nombre. | character varying(100) | no |  |
| `display_name` |  | character varying(200) | sí |  |
| `base_url` |  | character varying(500) | sí |  |
| `api_key_env_var` |  | character varying(100) | sí |  |
| `rate_limit_per_second` |  | numeric(6,3) | sí |  |
| `daily_request_limit` |  | integer | sí |  |
| `is_enabled` |  | boolean | no |  |
| `notes` |  | text | sí |  |

#### `meta.fetch_run` · tabla · ~71,134 filas
Un registro por cada descarga hecha: cuándo, qué fuente, cuántos datos y si hubo errores. Es el 'diario' de descargas.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `domain` |  | character varying(50) | no |  |
| `started_at` |  | timestamp without time zone | no |  |
| `finished_at` |  | timestamp without time zone | sí |  |
| `status` | Estado (running / success / failed). | character varying(20) | no |  |
| `records_fetched` |  | integer | no |  |
| `records_inserted` |  | integer | no |  |
| `records_updated` |  | integer | no |  |
| `errors` |  | integer | no |  |
| `params` |  | jsonb | sí |  |
| `error_log` |  | jsonb | sí |  |

#### `meta.transform_run` · tabla · ~84 filas
Un registro por cada vez que transformamos datos crudos en datos limpios. El 'diario' de transformaciones.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `domain` |  | character varying(50) | no |  |
| `target_layer` |  | character varying(20) | no |  |
| `started_at` |  | timestamp without time zone | no |  |
| `finished_at` |  | timestamp without time zone | sí |  |
| `status` | Estado (running / success / failed). | character varying(20) | no |  |
| `records_read` |  | integer | no |  |
| `records_written` |  | integer | no |  |
| `records_invalid` |  | integer | no |  |
| `params` |  | jsonb | sí |  |
| `error_log` |  | jsonb | sí |  |

## Renta variable y mercados financieros

### Esquema `equity`
_Renta variable: empresas, precios, fundamentales y 360°._

#### `equity.analyst_estimate` · tabla · ~0 filas
Previsiones de los analistas sobre beneficios e ingresos futuros.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `snapshot_date` | Día de la foto (los datos se acumulan por día). | date | no |  |
| `horizon` |  | character varying(10) | no |  |
| `period_label` |  | character varying(20) | sí |  |
| `eps_avg` |  | numeric(12,4) | sí |  |
| `eps_low` |  | numeric(12,4) | sí |  |
| `eps_high` |  | numeric(12,4) | sí |  |
| `revenue_avg` |  | numeric(20,2) | sí |  |
| `num_analysts` |  | smallint | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |

#### `equity.balance_sheet` · tabla · ~11,119 filas
Balance anual (activos, deudas, patrimonio) de cada empresa.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `fiscal_year` | Año fiscal del periodo. | smallint | no |  |
| `fiscal_quarter` | Trimestre fiscal (vacío = dato anual). | smallint | sí |  |
| `period_end_date` | Fecha de cierre del periodo contable. | date | sí |  |
| `currency_code` | Moneda del importe. | character varying(3) | sí |  |
| `cash_and_equivalents` | Efectivo y equivalentes. | numeric(18,2) | sí |  |
| `short_term_investments` | Inversiones a corto plazo. | numeric(18,2) | sí |  |
| `total_current_assets` | Activo corriente total. | numeric(18,2) | sí |  |
| `property_plant_equipment` | Inmovilizado material (fábricas, equipos...). | numeric(18,2) | sí |  |
| `goodwill` | Fondo de comercio. | numeric(18,2) | sí |  |
| `intangible_assets` | Activos intangibles. | numeric(18,2) | sí |  |
| `total_assets` | Activos totales. | numeric(18,2) | sí |  |
| `accounts_payable` | Cuentas a pagar (a proveedores). | numeric(18,2) | sí |  |
| `short_term_debt` | Deuda a corto plazo. | numeric(18,2) | sí |  |
| `total_current_liabilities` | Pasivo corriente total. | numeric(18,2) | sí |  |
| `long_term_debt` | Deuda a largo plazo. | numeric(18,2) | sí |  |
| `total_liabilities` | Pasivos totales (todo lo que debe). | numeric(18,2) | sí |  |
| `total_stockholders_equity` | Patrimonio de los accionistas. | numeric(18,2) | sí |  |
| `retained_earnings` | Beneficios retenidos (no repartidos). | numeric(18,2) | sí |  |
| `total_equity` | Patrimonio neto total. | numeric(18,2) | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |
| `fetched_at` | Cuándo se descargó. | timestamp without time zone | no |  |

#### `equity.cash_flow` · tabla · ~11,214 filas
Flujos de caja anuales de cada empresa.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `fiscal_year` | Año fiscal del periodo. | smallint | no |  |
| `fiscal_quarter` | Trimestre fiscal (vacío = dato anual). | smallint | sí |  |
| `period_end_date` | Fecha de cierre del periodo contable. | date | sí |  |
| `currency_code` | Moneda del importe. | character varying(3) | sí |  |
| `operating_cash_flow` | Flujo de caja de las operaciones. | numeric(18,2) | sí |  |
| `capital_expenditure` | Inversión en activos (capex). | numeric(18,2) | sí |  |
| `free_cash_flow` | Flujo de caja libre. | numeric(18,2) | sí |  |
| `dividends_paid` | Dividendos pagados. | numeric(18,2) | sí |  |
| `share_buyback` | Recompra de acciones propias. | numeric(18,2) | sí |  |
| `debt_issued` | Deuda emitida. | numeric(18,2) | sí |  |
| `debt_repaid` | Deuda devuelta. | numeric(18,2) | sí |  |
| `investing_cash_flow` | Flujo de caja de inversión. | numeric(18,2) | sí |  |
| `financing_cash_flow` | Flujo de caja de financiación. | numeric(18,2) | sí |  |
| `net_change_cash` | Variación neta de efectivo. | numeric(18,2) | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |
| `fetched_at` | Cuándo se descargó. | timestamp without time zone | no |  |

#### `equity.company` · tabla · ~2,446 filas
Cada empresa cotizada que seguimos.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `name` | Nombre. | character varying(500) | no |  |
| `ticker` | Símbolo bursátil (p.ej. AAPL). | character varying(20) | no |  |
| `isin` | Código ISIN (identificador internacional del valor). | character varying(12) | sí |  |
| `exchange_id` | Bolsa de valores. | integer | sí | FK → ref.exchange.id |
| `sector_id` | Sector GICS. | integer | sí | FK → ref.sector.id |
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | sí | FK → ref.country.code |
| `currency_code` | Moneda del importe. | character varying(3) | sí | FK → ref.currency.code |
| `market_cap_usd` | Capitalización bursátil en dólares. | numeric(18,2) | sí |  |
| `shares_outstanding` | Acciones en circulación. | bigint | sí |  |
| `ipo_date` | Fecha de salida a bolsa. | date | sí |  |
| `delisted_date` | Fecha en que dejó de cotizar. | date | sí |  |
| `is_active` | Si la empresa sigue cotizando (no deslistada). | boolean | no |  |
| `website` | Web de la empresa. | character varying(300) | sí |  |
| `description` | Descripción libre. | text | sí |  |
| `employees` | Número de empleados. | integer | sí |  |
| `last_updated` | Última actualización. | timestamp without time zone | no |  |

#### `equity.dividend` · tabla · ~134,600 filas
Dividendos pagados por cada acción.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `ex_date` |  | date | no |  |
| `pay_date` |  | date | sí |  |
| `record_date` |  | date | sí |  |
| `amount` |  | numeric(12,6) | no |  |
| `currency_code` | Moneda del importe. | character varying(3) | sí |  |
| `dividend_type` |  | character varying(20) | sí |  |

#### `equity.earnings_date` · tabla · ~100,804 filas
Fechas de presentación de resultados, con lo esperado vs lo reportado.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `date` | Fecha del dato. | date | no |  |
| `eps_estimate` | Beneficio por acción esperado. | numeric(12,4) | sí |  |
| `reported_eps` | Beneficio por acción real. | numeric(12,4) | sí |  |
| `surprise_pct` |  | numeric(10,4) | sí |  |

#### `equity.earnings_revision` · tabla · ~0 filas
Cómo van cambiando esas previsiones (si los analistas revisan al alza o a la baja).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `snapshot_date` | Día de la foto (los datos se acumulan por día). | date | no |  |
| `horizon` |  | character varying(10) | no |  |
| `eps_current` |  | numeric(12,4) | sí |  |
| `eps_7d_ago` |  | numeric(12,4) | sí |  |
| `eps_30d_ago` |  | numeric(12,4) | sí |  |
| `up_last_30d` |  | smallint | sí |  |
| `down_last_30d` |  | smallint | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |

#### `equity.holder` · tabla · ~34,656 filas
Quién posee cada empresa: grandes fondos e instituciones, con su porcentaje.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `holder_type` | Tipo: institutional o mutualfund. | character varying(20) | no |  |
| `holder_name` |  | character varying(200) | no |  |
| `snapshot_date` | Día de la foto (los datos se acumulan por día). | date | no |  |
| `date_reported` |  | date | sí |  |
| `pct_held` | % de la empresa que posee. | numeric(9,6) | sí |  |
| `shares` | Nº de acciones que posee. | bigint | sí |  |
| `value_usd` |  | numeric(20,2) | sí |  |

#### `equity.income_statement` · tabla · ~11,053 filas
Cuenta de resultados anual (ingresos, beneficio...) de cada empresa.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `fiscal_year` | Año fiscal del periodo. | smallint | no |  |
| `fiscal_quarter` | Trimestre fiscal (vacío = dato anual). | smallint | sí |  |
| `period_end_date` | Fecha de cierre del periodo contable. | date | sí |  |
| `currency_code` | Moneda del importe. | character varying(3) | sí |  |
| `revenue` | Ingresos totales (ventas). | numeric(18,2) | sí |  |
| `cost_of_revenue` | Coste de las ventas. | numeric(18,2) | sí |  |
| `gross_profit` | Beneficio bruto. | numeric(18,2) | sí |  |
| `operating_expenses` | Gastos operativos. | numeric(18,2) | sí |  |
| `operating_income` | Beneficio operativo. | numeric(18,2) | sí |  |
| `interest_expense` | Gastos financieros (intereses). | numeric(18,2) | sí |  |
| `pretax_income` | Beneficio antes de impuestos. | numeric(18,2) | sí |  |
| `income_tax` | Impuestos sobre beneficios. | numeric(18,2) | sí |  |
| `net_income` | Beneficio neto (lo que gana al final). | numeric(18,2) | sí |  |
| `eps_basic` | Beneficio por acción (básico). | numeric(10,4) | sí |  |
| `eps_diluted` | Beneficio por acción (diluido). | numeric(10,4) | sí |  |
| `shares_basic` | Nº de acciones (básico). | bigint | sí |  |
| `shares_diluted` | Nº de acciones (diluido). | bigint | sí |  |
| `ebitda` | EBITDA (beneficio antes de intereses, impuestos y amortizaciones). | numeric(18,2) | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |
| `fetched_at` | Cuándo se descargó. | timestamp without time zone | no |  |

#### `equity.index_constituent_current` · tabla · ~503 filas
Qué empresas componen hoy cada índice.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `index_id` | Índice de mercado. | integer | no | FK → equity.market_index.id |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `weight` |  | numeric(8,5) | sí |  |
| `as_of_date` | Fecha de referencia del cálculo. | date | no |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |

#### `equity.index_price` · tabla · ~189,345 filas
Valor de cierre diario de cada índice.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `index_id` | Índice de mercado. | integer | no | FK → equity.market_index.id |
| `date` | Fecha del dato. | date | no |  |
| `open` | Precio de apertura. | numeric(14,4) | sí |  |
| `high` | Precio máximo del día. | numeric(14,4) | sí |  |
| `low` | Precio mínimo del día. | numeric(14,4) | sí |  |
| `close` | Precio de cierre. | numeric(14,4) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.insider_transaction` · tabla · ~121,912 filas
Compras y ventas de acciones por parte de directivos e insiders de la empresa.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `insider` | Nombre del directivo/insider. | character varying(200) | no |  |
| `position` |  | character varying(200) | sí |  |
| `transaction` | Compra o venta. | character varying(100) | sí |  |
| `start_date` |  | date | sí |  |
| `shares` |  | bigint | sí |  |
| `value_usd` |  | numeric(20,2) | sí |  |

#### `equity.market_index` · tabla · ~0 filas
Índices bursátiles (S&P 500, DAX...).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `code` | Código identificador. | character varying(50) | no |  |
| `name` | Nombre. | character varying(200) | no |  |
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | sí | FK → ref.country.code |
| `exchange_id` | Bolsa de valores. | integer | sí | FK → ref.exchange.id |
| `currency_code` | Moneda del importe. | character varying(3) | sí |  |
| `description` | Descripción libre. | text | sí |  |

#### `equity.price_daily` · tabla · ~9,332,877 filas
El precio de cierre diario de cada acción (y máximo, mínimo, volumen...).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `date` | Fecha del dato. | date | no |  |
| `open` | Precio de apertura. | numeric(14,4) | sí |  |
| `high` | Precio máximo del día. | numeric(14,4) | sí |  |
| `low` | Precio mínimo del día. | numeric(14,4) | sí |  |
| `close` | Precio de cierre. | numeric(14,4) | no |  |
| `adj_close` | Precio de cierre ajustado (dividendos/splits). | numeric(14,4) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |

#### `equity.ratios_mv` · materializada · ~2,412 filas
Ratios de valoración calculados (PER, ROE...) — foto actual.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | sí |  |
| `ticker` | Símbolo bursátil (p.ej. AAPL). | character varying(20) | sí |  |
| `sector_id` | Sector GICS. | integer | sí |  |
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | sí |  |
| `currency_code` | Moneda del importe. | character varying(3) | sí |  |
| `market_cap_usd` | Capitalización bursátil en dólares. | numeric(18,2) | sí |  |
| `shares_outstanding` | Acciones en circulación. | bigint | sí |  |
| `price_date` |  | date | sí |  |
| `income_period` |  | date | sí |  |
| `balance_period` |  | date | sí |  |
| `cashflow_period` |  | date | sí |  |
| `last_close` |  | numeric(14,4) | sí |  |
| `pe_ratio` |  | numeric | sí |  |
| `pb_ratio` |  | numeric | sí |  |
| `ps_ratio` |  | numeric | sí |  |
| `roe` |  | numeric | sí |  |
| `roa` |  | numeric | sí |  |
| `roic` |  | numeric | sí |  |
| `gross_margin` |  | numeric | sí |  |
| `operating_margin` |  | numeric | sí |  |
| `net_margin` |  | numeric | sí |  |
| `debt_equity` |  | numeric | sí |  |
| `debt_assets` |  | numeric | sí |  |
| `fcf_yield` |  | numeric | sí |  |
| `revenue` | Ingresos totales (ventas). | numeric(18,2) | sí |  |
| `net_income` | Beneficio neto (lo que gana al final). | numeric(18,2) | sí |  |
| `ebitda` | EBITDA (beneficio antes de intereses, impuestos y amortizaciones). | numeric(18,2) | sí |  |
| `eps_diluted` | Beneficio por acción (diluido). | numeric(10,4) | sí |  |
| `total_equity` | Patrimonio neto total. | numeric(18,2) | sí |  |
| `total_assets` | Activos totales. | numeric(18,2) | sí |  |
| `free_cash_flow` | Flujo de caja libre. | numeric(18,2) | sí |  |
| `operating_cash_flow` | Flujo de caja de las operaciones. | numeric(18,2) | sí |  |

#### `equity.recommendation_trend` · tabla · ~8,073 filas
Resumen de cuántos analistas recomiendan comprar, mantener o vender.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `snapshot_date` | Día de la foto (los datos se acumulan por día). | date | no |  |
| `period` | Año del dato. | character varying(10) | no |  |
| `strong_buy` |  | smallint | sí |  |
| `buy` |  | smallint | sí |  |
| `hold` |  | smallint | sí |  |
| `sell` |  | smallint | sí |  |
| `strong_sell` |  | smallint | sí |  |

#### `equity.shares_history` · tabla · ~1,287,132 filas
Número de acciones en circulación de la empresa a lo largo del tiempo.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `date` | Fecha del dato. | date | no |  |
| `shares` |  | bigint | sí |  |

#### `equity.split` · tabla · ~4,564 filas
Splits (desdoblamientos) de acciones.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `date` | Fecha del dato. | date | no |  |
| `ratio_from` |  | numeric(10,4) | sí |  |
| `ratio_to` |  | numeric(10,4) | sí |  |

#### `equity.upgrade_downgrade` · tabla · ~289,296 filas
Cambios de recomendación y precio objetivo que hacen los analistas (comprar/vender).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `date` | Fecha del dato. | date | no |  |
| `firm` | Casa de análisis (Goldman...). | character varying(200) | no |  |
| `to_grade` | Nueva recomendación. | character varying(100) | sí |  |
| `from_grade` |  | character varying(100) | sí |  |
| `action` |  | character varying(50) | sí |  |
| `price_target` | Precio objetivo fijado. | numeric(14,4) | sí |  |

### Esquema `fi`
_Renta fija: bonos, ratings, curvas de tipos._

#### `fi.bond` · tabla · ~5,015 filas
Bonos (sobre todo deuda pública de EE.UU.).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `issuer_id` |  | integer | sí | FK → fi.bond_issuer.id |
| `isin` | Código ISIN (identificador internacional del valor). | character varying(12) | sí |  |
| `name` | Nombre. | character varying(300) | sí |  |
| `coupon_rate` |  | numeric(8,4) | sí |  |
| `coupon_frequency` |  | smallint | sí |  |
| `maturity_date` |  | date | sí |  |
| `issue_date` |  | date | sí |  |
| `face_value` |  | numeric(14,2) | sí |  |
| `currency_code` | Moneda del importe. | character varying(3) | sí |  |
| `bond_type` |  | character varying(30) | sí |  |
| `is_callable` |  | boolean | no |  |

#### `fi.bond_issuer` · tabla · ~53 filas
Emisores de bonos (países).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `name` | Nombre. | character varying(300) | sí |  |
| `issuer_type` |  | character varying(20) | no |  |
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | sí | FK → ref.country.code |

#### `fi.credit_rating` · tabla · ~10,563 filas
Ratings de crédito (calificaciones de solvencia).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `issuer_id` |  | integer | no | FK → fi.bond_issuer.id |
| `agency` |  | character varying(20) | no |  |
| `rating` |  | character varying(10) | no |  |
| `outlook` |  | character varying(20) | sí |  |
| `rating_date` |  | date | no |  |
| `previous_rating` |  | character varying(10) | sí |  |

#### `fi.yield_curve` · tabla · ~68,072 filas
Curvas de tipos de interés (rendimiento de la deuda por plazo).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | no | FK → ref.country.code |
| `date` | Fecha del dato. | date | no |  |
| `maturity_months` |  | smallint | no |  |
| `yield_pct` |  | numeric(8,4) | no |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |

### Esquema `commodity`
_Materias primas y sus precios._

#### `commodity.commodity` · tabla · ~0 filas
Materias primas (oro, petróleo...).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `code` | Código identificador. | character varying(20) | no |  |
| `name` | Nombre. | character varying(200) | no |  |
| `category` | Categoría o dominio. | character varying(50) | sí |  |
| `subcategory` | Subcategoría. | character varying(50) | sí |  |
| `unit` | Unidad de medida. | character varying(50) | sí |  |
| `currency_code` | Moneda del importe. | character varying(3) | sí |  |
| `exchange` |  | character varying(50) | sí |  |
| `yfinance_ticker` |  | character varying(20) | sí |  |

#### `commodity.price_daily` · tabla · ~104,882 filas
Precio diario de cada materia prima.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `commodity_id` |  | integer | no | FK → commodity.commodity.id |
| `date` | Fecha del dato. | date | no |  |
| `open` | Precio de apertura. | numeric(14,4) | sí |  |
| `high` | Precio máximo del día. | numeric(14,4) | sí |  |
| `low` | Precio mínimo del día. | numeric(14,4) | sí |  |
| `close` | Precio de cierre. | numeric(14,4) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |

### Esquema `forex`
_Divisas y tipos de cambio._

#### `forex.currency_pair` · tabla · ~0 filas
Pares de divisas (EUR/USD...).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `base_currency` |  | character varying(3) | no | FK → ref.currency.code |
| `quote_currency` |  | character varying(3) | no | FK → ref.currency.code |
| `pair_code` |  | character varying(7) | no |  |
| `category` | Categoría o dominio. | character varying(20) | sí |  |

#### `forex.rate_daily` · tabla · ~183,177 filas
Tipo de cambio diario de cada par.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `pair_id` |  | integer | no | FK → forex.currency_pair.id |
| `date` | Fecha del dato. | date | no |  |
| `open` | Precio de apertura. | numeric(14,8) | sí |  |
| `high` | Precio máximo del día. | numeric(14,8) | sí |  |
| `low` | Precio mínimo del día. | numeric(14,8) | sí |  |
| `close` | Precio de cierre. | numeric(14,8) | no |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |

### Esquema `crypto`
_Criptomonedas._

#### `crypto.coin` · tabla · ~0 filas
Criptomonedas (Bitcoin, Ethereum...).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `coingecko_id` |  | character varying(100) | no |  |
| `symbol` |  | character varying(20) | no |  |
| `name` | Nombre. | character varying(200) | no |  |
| `category` | Categoría o dominio. | character varying(50) | sí |  |
| `market_cap_rank` |  | smallint | sí |  |

#### `crypto.market_dominance` · tabla · ~0 filas
Snapshot diario del mercado crypto.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `date` | Fecha del dato. | date | no |  |
| `total_market_cap_usd` |  | numeric(18,2) | sí |  |
| `btc_dominance_pct` |  | numeric(6,3) | sí |  |
| `eth_dominance_pct` |  | numeric(6,3) | sí |  |

#### `crypto.price_daily` · tabla · ~13,482 filas
Precio diario de cada cripto.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `coin_id` |  | integer | no |  |
| `date` | Fecha del dato. | date | no |  |
| `open` | Precio de apertura. | numeric(18,8) | sí |  |
| `high` | Precio máximo del día. | numeric(18,8) | sí |  |
| `low` | Precio mínimo del día. | numeric(18,8) | sí |  |
| `close` | Precio de cierre. | numeric(18,8) | no |  |
| `volume_usd` |  | numeric(18,2) | sí |  |
| `market_cap_usd` | Capitalización bursátil en dólares. | numeric(18,2) | sí |  |

### Esquema `fund`
_ETFs y fondos._

#### `fund.fund` · tabla · ~25 filas
ETFs y fondos de inversión.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `ticker` | Símbolo bursátil (p.ej. AAPL). | character varying(20) | sí |  |
| `name` | Nombre. | character varying(500) | no |  |
| `fund_type` |  | character varying(20) | no |  |
| `asset_class` |  | character varying(50) | sí |  |
| `geography` |  | character varying(100) | sí |  |
| `strategy` |  | character varying(100) | sí |  |
| `provider` |  | character varying(100) | sí |  |
| `expense_ratio` |  | numeric(6,4) | sí |  |
| `aum_usd` |  | numeric(18,2) | sí |  |
| `inception_date` |  | date | sí |  |
| `currency_code` | Moneda del importe. | character varying(3) | sí |  |
| `exchange_id` | Bolsa de valores. | integer | sí | FK → ref.exchange.id |
| `is_active` | Si sigue cotizando (no deslistada). | boolean | no |  |

#### `fund.nav_daily` · tabla · ~132,304 filas
Valor liquidativo (NAV) diario de cada fondo.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `fund_id` |  | integer | no | FK → fund.fund.id |
| `date` | Fecha del dato. | date | no |  |
| `nav` |  | numeric(14,6) | no |  |
| `volume` | Volumen negociado. | integer | sí |  |

### Esquema `alt`
_Datos alternativos: sentimiento, vivienda._

#### `alt.housing_index` · tabla · ~0 filas
Índice inmobiliario.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `code` | Código identificador. | character varying(50) | no |  |
| `name` | Nombre. | character varying(200) | sí |  |
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | sí | FK → ref.country.code |
| `index_type` |  | character varying(50) | sí |  |

#### `alt.housing_index_value` · tabla · ~0 filas
Valor de índice inmobiliario.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `index_id` | Índice de mercado. | integer | no | FK → alt.housing_index.id |
| `date` | Fecha del dato. | date | no |  |
| `value` | Valor del dato. | numeric(12,4) | no |  |
| `yoy_change_pct` |  | numeric(8,4) | sí |  |

#### `alt.sentiment_indicator` · tabla · ~0 filas
Definición de indicador de sentimiento.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `code` | Código identificador. | character varying(50) | no |  |
| `name` | Nombre. | character varying(200) | sí |  |
| `description` | Descripción libre. | text | sí |  |

#### `alt.sentiment_value` · tabla · ~6,254 filas
Valor diario de indicador de sentimiento.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `indicator_id` | Indicador al que pertenece. | integer | no | FK → alt.sentiment_indicator.id |
| `date` | Fecha del dato. | date | no |  |
| `value` | Valor del dato. | numeric(12,4) | no |  |

## Economía mundial

### Esquema `macro`
_Economía mundial como series país × indicador × fecha._

#### `macro.data_point` · tabla · ~2,870,193 filas
El dato en sí: el valor de una serie en una fecha (p.ej. inflación de España en 2022 = 8,3%).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `series_id` | Serie temporal a la que pertenece. | integer | no | FK → macro.series.id |
| `date` | Fecha del dato. | date | no |  |
| `value` | El valor del indicador en esa fecha. | numeric(20,6) | no |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |
| `fetched_at` | Cuándo se descargó. | timestamp without time zone | no |  |

#### `macro.indicator` · tabla · ~1,669 filas
El catálogo de indicadores económicos que seguimos (PIB, inflación, paro...). Cada fila es un indicador.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `code` | Código identificador. | character varying(100) | no |  |
| `name` | Nombre. | character varying(300) | no |  |
| `category` | Categoría o dominio. | character varying(100) | sí |  |
| `subcategory` | Subcategoría. | character varying(100) | sí |  |
| `unit` | En qué se mide (%, USD, personas...). | character varying(50) | sí |  |
| `frequency` | Frecuencia (anual, mensual, diario...). | character varying(20) | sí |  |
| `seasonal_adjustment` |  | character varying(20) | sí |  |
| `description` | Descripción libre. | text | sí |  |

#### `macro.indicator_source` · tabla · ~1,636 filas
Cómo se llama cada indicador en cada fuente (el mismo 'PIB' tiene códigos distintos en IMF y World Bank).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `indicator_id` | Indicador al que pertenece. | integer | no | FK → macro.indicator.id |
| `source_id` | Fuente de la que procede el dato. | integer | no | FK → meta.data_source.id |
| `external_code` |  | character varying(200) | no |  |
| `external_name` |  | character varying(500) | sí |  |
| `priority` |  | smallint | no |  |

#### `macro.series` · tabla · ~87,854 filas
Una serie = un indicador para un país concreto (p.ej. 'inflación de España'). Agrupa sus valores en el tiempo.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `indicator_id` | Indicador al que pertenece. | integer | no | FK → macro.indicator.id |
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | sí | FK → ref.country.code |
| `region_code` |  | character varying(20) | sí |  |
| `last_value` | Último valor conocido de la serie. | numeric(20,6) | sí |  |
| `last_date` |  | date | sí |  |
| `point_count` | Cuántos datos tiene la serie. | integer | no |  |

### Esquema `trade`
_Comercio internacional bilateral (país × socio)._

#### `trade.flow` · tabla · ~973,418 filas
Comercio entre dos países: cuánto exporta/importa un país a otro cada año.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `reporter_code` | País que declara (exporta/importa). | character varying(3) | no | FK → ref.country.code |
| `partner_code` | País socio comercial. | character varying(3) | no |  |
| `product_code` | Producto (Total = todos los productos). | character varying(20) | no |  |
| `flow` | Sentido: X = exportación, M = importación. | character varying(1) | no |  |
| `period` | Año del dato. | smallint | no |  |
| `value_usd_k` | Valor comerciado en miles de dólares. | numeric(20,3) | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |
| `fetched_at` | Cuándo se descargó. | timestamp without time zone | no |  |

### Esquema `energy`
_Balance energético por país, fuente y flujo._

#### `energy.balance` · tabla · ~185,679 filas
Energía por país y fuente (carbón, gas, solar...): cuánto se produce y consume.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | no | FK → ref.country.code |
| `product_code` | Fuente de energía (coal, gas, solar...). | character varying(30) | no |  |
| `flow` | consumption / production / electricity. | character varying(20) | no |  |
| `period` | Año del dato. | smallint | no |  |
| `value` | Valor del dato. | numeric(18,4) | sí |  |
| `unit` | Unidad de medida. | character varying(20) | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |
| `fetched_at` | Cuándo se descargó. | timestamp without time zone | no |  |

### Esquema `agri`
_Producción agrícola por país, cultivo/ganado y elemento._

#### `agri.production` · tabla · ~2,929,268 filas
Producción agrícola: cuánto trigo, maíz, carne... produce cada país cada año.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | no | FK → ref.country.code |
| `item_code` | Código del cultivo o ganado. | character varying(20) | no |  |
| `item_name` | Nombre del cultivo/ganado (Wheat...). | character varying(200) | sí |  |
| `element` | Qué se mide (producción, rendimiento...). | character varying(60) | no |  |
| `period` | Año del dato. | smallint | no |  |
| `value` | Valor del dato. | numeric(24,3) | sí |  |
| `unit` | Unidad de medida. | character varying(40) | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |
| `fetched_at` | Cuándo se descargó. | timestamp without time zone | no |  |

### Esquema `country`
_Perfiles de país: demografía, impuestos._

#### `country.demographics` · tabla · ~1,040 filas
Datos demográficos por país.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | no | FK → ref.country.code |
| `year` | Año. | smallint | no |  |
| `total_population` |  | bigint | sí |  |
| `median_age` |  | numeric(5,2) | sí |  |
| `urban_population_pct` |  | numeric(6,3) | sí |  |
| `life_expectancy` |  | numeric(5,2) | sí |  |
| `fertility_rate` |  | numeric(4,2) | sí |  |
| `labor_force` |  | bigint | sí |  |

#### `country.profile` · tabla · ~40 filas
Perfil de cada país (datos generales).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | no | PK |
| `population` |  | bigint | sí |  |
| `population_year` |  | smallint | sí |  |
| `gdp_usd` |  | numeric(18,2) | sí |  |
| `gdp_per_capita_usd` |  | numeric(12,2) | sí |  |
| `hdi` |  | numeric(5,4) | sí |  |
| `gini_index` |  | numeric(5,2) | sí |  |
| `ease_of_business_rank` |  | smallint | sí |  |
| `political_stability_index` |  | numeric(6,4) | sí |  |
| `last_updated` | Última actualización. | timestamp without time zone | sí |  |

#### `country.tax_rate` · tabla · ~0 filas
Tipos impositivos por país y año.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | no | FK → ref.country.code |
| `year` | Año. | smallint | no |  |
| `corporate_tax_rate` |  | numeric(6,3) | sí |  |
| `top_income_tax_rate` |  | numeric(6,3) | sí |  |
| `vat_rate` |  | numeric(6,3) | sí |  |
| `capital_gains_tax_rate` |  | numeric(6,3) | sí |  |

## Derivados

### Esquema `deriv`
_Derivados: snapshots de cadenas de opciones._

#### `deriv.option_snapshot` · tabla · ~2,113 filas
Foto diaria de las opciones (contratos de compra/venta) de las empresas más líquidas.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `snapshot_date` | Día de la foto (los datos se acumulan por día). | date | no |  |
| `expiry` | Fecha de vencimiento del contrato. | date | no |  |
| `option_type` | C = call (compra), P = put (venta). | character varying(1) | no |  |
| `strike` | Precio de ejercicio del contrato. | numeric(14,4) | no |  |
| `last_price` |  | numeric(14,4) | sí |  |
| `bid` |  | numeric(14,4) | sí |  |
| `ask` |  | numeric(14,4) | sí |  |
| `volume` | Volumen negociado. | integer | sí |  |
| `open_interest` | Contratos abiertos vivos. | integer | sí |  |
| `implied_vol` | Volatilidad implícita. | numeric(10,6) | sí |  |
| `fetched_at` | Cuándo se descargó. | timestamp without time zone | no |  |

## Medallion — aterrizaje y analítica

### Esquema `bronze`
_Aterrizaje crudo (JSONB) de las fuentes nuevas._

#### `bronze.analyst_snapshot` · tabla · ~0 filas
Foto diaria de datos de analistas de yfinance (por ticker).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |
| `ingested_at` | Cuándo se guardó el dato crudo. | timestamp without time zone | no |  |
| `ticker` | Símbolo bursátil (p.ej. AAPL). | character varying(20) | no |  |
| `snapshot_date` | Día de la foto (los datos se acumulan por día). | date | no |  |
| `payload` | Respuesta cruda de la API (JSON), tal cual llegó. | jsonb | no |  |

#### `bronze.api_response` · tabla · ~316 filas
La respuesta cruda de una API macro, guardada tal cual por si hay que reprocesarla.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |
| `ingested_at` | Cuándo se guardó el dato crudo. | timestamp without time zone | no |  |
| `source_name` |  | character varying(50) | no |  |
| `dataset` |  | character varying(120) | no |  |
| `params` |  | jsonb | sí |  |
| `payload` | Respuesta cruda de la API (JSON), tal cual llegó. | jsonb | no |  |

#### `bronze.constituents_snapshot` · tabla · ~0 filas
Foto cruda de constituyentes de un índice (Wikipedia/GitHub).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |
| `ingested_at` | Cuándo se guardó el dato crudo. | timestamp without time zone | no |  |
| `index_code` |  | character varying(50) | no |  |
| `source_kind` |  | character varying(30) | no |  |
| `payload` | Respuesta cruda de la API (JSON), tal cual llegó. | jsonb | no |  |

#### `bronze.sec_companyfacts` · tabla · ~1,420 filas
El JSON crudo con todos los datos financieros que publica la SEC de cada empresa.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |
| `ingested_at` | Cuándo se guardó el dato crudo. | timestamp without time zone | no |  |
| `cik` |  | character varying(10) | no |  |
| `ticker` | Símbolo bursátil (p.ej. AAPL). | character varying(20) | sí |  |
| `payload` | Respuesta cruda de la API (JSON), tal cual llegó. | jsonb | no |  |

#### `bronze.yf_profile` · tabla · ~2,170 filas
El perfil completo de una empresa tal cual lo devuelve yfinance.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |
| `ingested_at` | Cuándo se guardó el dato crudo. | timestamp without time zone | no |  |
| `ticker` | Símbolo bursátil (p.ej. AAPL). | character varying(20) | no |  |
| `snapshot_date` | Día de la foto (los datos se acumulan por día). | date | no |  |
| `payload` | Respuesta cruda de la API (JSON), tal cual llegó. | jsonb | no |  |

### Esquema `gold`
_Capa analítica point-in-time: hechos, dimensiones y marts._

#### `gold.dim_company` · tabla · ~3,014 filas
Ficha resumida de cada empresa para análisis (con su sector ya incorporado).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_key` |  | integer | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `ticker` | Símbolo bursátil (p.ej. AAPL). | character varying(20) | no |  |
| `name` | Nombre. | character varying(500) | sí |  |
| `sector_id` | Sector GICS. | integer | sí |  |
| `sector_name` |  | character varying(200) | sí |  |
| `industry_id` |  | integer | sí |  |
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | sí |  |
| `currency_code` | Moneda del importe. | character varying(3) | sí |  |
| `is_active` | Si sigue cotizando (no deslistada). | boolean | no |  |
| `delisted_date` | Fecha en que dejó de cotizar. | date | sí |  |

#### `gold.dim_country` · tabla · ~249 filas
Ficha de cada país (región, grupo de renta).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | no | PK |
| `name` | Nombre. | character varying(200) | no |  |
| `region` |  | character varying(100) | sí |  |
| `sub_region` |  | character varying(100) | sí |  |
| `income_group` |  | character varying(50) | sí |  |

#### `gold.dim_date` · tabla · ~23,552 filas
Calendario: una fila por día, con año, trimestre...

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `date_key` |  | date | no | PK |
| `year` | Año. | smallint | no |  |
| `quarter` |  | smallint | no |  |
| `month` |  | smallint | no |  |
| `day_of_week` |  | smallint | no |  |
| `is_month_end` |  | boolean | no |  |
| `is_trading_day` |  | boolean | sí |  |

#### `gold.dim_indicator` · vista · ~0 filas
Catálogo autodocumentado de indicadores macro (código, fuente, cobertura, rango).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `code` | Código identificador. | character varying(100) | sí |  |
| `name` | Nombre. | character varying(300) | sí |  |
| `category` | Categoría o dominio. | character varying(100) | sí |  |
| `unit` | Unidad de medida. | character varying(50) | sí |  |
| `frequency` | Frecuencia (anual, mensual, diario...). | character varying(20) | sí |  |
| `sources` |  | text | sí |  |
| `n_countries` |  | bigint | sí |  |
| `first_date` |  | date | sí |  |
| `last_date` |  | date | sí |  |
| `n_points` |  | bigint | sí |  |

#### `gold.fact_factor_scores` · tabla · ~170,960 filas
Puntuaciones de factores de inversión (Value/Quality/Momentum) de cada empresa, normalizadas por sector.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `as_of_date` | Fecha de referencia del cálculo. | date | no |  |
| `factor` | value, quality o momentum. | character varying(30) | no |  |
| `universe` |  | character varying(30) | no |  |
| `raw_value` |  | numeric(18,6) | sí |  |
| `z_score` |  | numeric(10,6) | sí |  |
| `z_sector_neutral` | Puntuación normalizada dentro de su sector (para comparar manzanas con manzanas). | numeric(10,6) | sí |  |
| `percentile` |  | numeric(6,4) | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |

#### `gold.fact_fundamentals_pit` · tabla · ~12,826,841 filas
Todos los datos financieros de las empresas US con la fecha en que se publicaron (para saber qué se sabía en cada momento). Es la tabla más grande.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `statement_type` |  | character varying(10) | no |  |
| `fiscal_year` | Año fiscal del periodo. | smallint | no |  |
| `fiscal_quarter` | Trimestre fiscal (vacío = dato anual). | smallint | sí |  |
| `period_end_date` | Fecha de cierre del periodo contable. | date | no |  |
| `filed_date` | Fecha en que se publicó/presentó el dato. | date | no |  |
| `publish_date` | Fecha de publicación. | date | sí |  |
| `metric` | Concepto financiero (revenue, net_income o el código XBRL completo). | character varying(150) | no |  |
| `value` | Importe del concepto. | numeric(28,6) | sí |  |
| `currency_code` | Moneda del importe. | character varying(3) | sí |  |
| `form` |  | character varying(10) | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |

#### `gold.index_membership` · tabla · ~1,255 filas
Qué empresas estaban en el S&P 500 en cada momento del pasado (para análisis sin 'trampa').

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `index_id` | Índice de mercado. | integer | no | FK → equity.market_index.id |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `ticker` | Símbolo bursátil (p.ej. AAPL). | character varying(20) | no |  |
| `start_date` | Cuándo entró en el índice. | date | no |  |
| `end_date` | Cuándo salió (vacío = sigue dentro). | date | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |

#### `gold.mart_benchmark_returns` · materializada · ~32,440 filas
Retorno diario del pool S&P 500 equiponderado (survivorship-free) vs SPY.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `date` | Fecha del dato. | date | sí |  |
| `method` |  | character varying(20) | sí |  |
| `ret` |  | numeric | sí |  |

#### `gold.mart_country_year` · materializada · ~38,444 filas
La tabla estrella: una fila por país y año con TODO junto (PIB, inflación, paro, CO2, energía, comercio...).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | sí |  |
| `year` | Año. | smallint | sí |  |
| `gdp_usd_bn` | PIB en miles de millones de USD. | numeric | sí |  |
| `gdp_per_capita_usd` | PIB por habitante (USD). | numeric | sí |  |
| `gdp_growth_pct` | Crecimiento del PIB (%). | numeric | sí |  |
| `gdp_ppp_bn` | PIB en paridad de poder adquisitivo (miles de millones). | numeric | sí |  |
| `inflation_pct` | Inflación anual (%). | numeric | sí |  |
| `unemployment_pct` | Tasa de paro (%). | numeric | sí |  |
| `population_mn` | Población (millones). | numeric | sí |  |
| `gov_debt_pct_gdp` | Deuda pública (% del PIB). | numeric | sí |  |
| `gov_balance_pct_gdp` | Saldo público: déficit o superávit (% del PIB). | numeric | sí |  |
| `current_account_pct_gdp` | Cuenta corriente (% del PIB): lo que el país presta o toma prestado al exterior. | numeric | sí |  |
| `gdp_ppp_per_capita` | PIB PPA por habitante. | numeric | sí |  |
| `share_world_gdp_ppp_pct` | % que representa del PIB mundial (PPA). | numeric | sí |  |
| `savings_pct_gdp` | Ahorro nacional (% del PIB). | numeric | sí |  |
| `investment_pct_gdp` | Inversión (% del PIB). | numeric | sí |  |
| `gov_revenue_pct_gdp` | Ingresos del Estado (% del PIB). | numeric | sí |  |
| `gov_expenditure_pct_gdp` | Gasto del Estado (% del PIB). | numeric | sí |  |
| `co2_mt` | Emisiones de CO2 (millones de toneladas). | numeric | sí |  |
| `co2_per_capita_t` | CO2 por habitante (toneladas). | numeric | sí |  |
| `co2_share_global_pct` | % del CO2 mundial. | numeric | sí |  |
| `ghg_mt` | Gases de efecto invernadero totales (Mt CO2 eq.). | numeric | sí |  |
| `primary_energy_twh` | Energía primaria consumida (TWh). | numeric | sí |  |
| `electricity_twh` | Electricidad generada (TWh). | numeric | sí |  |
| `renewables_elec_twh` | Electricidad renovable (TWh). | numeric | sí |  |
| `renewables_share_elec_pct` | % de la electricidad que es renovable. | numeric | sí |  |
| `exports_usd_bn` | Exportaciones de bienes (miles de millones USD). | numeric | sí |  |
| `imports_usd_bn` | Importaciones de bienes (miles de millones USD). | numeric | sí |  |
| `trade_balance_usd_bn` | Balanza comercial (exportaciones − importaciones). | numeric | sí |  |

#### `gold.mart_pool_membership` · vista · ~0 filas
Universo S&P 500 point-in-time expandido a días de cotización.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `index_id` | Índice de mercado. | integer | sí |  |
| `company_id` | Empresa a la que pertenece. | integer | sí |  |
| `date` | Fecha del dato. | date | sí |  |

#### `gold.mart_trade_matrix` · materializada · ~442,027 filas
Matriz de comercio: exportaciones e importaciones entre cada par de países.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `reporter_code` | País que declara (exporta/importa). | character varying(3) | sí |  |
| `partner_code` | País socio comercial. | character varying(3) | sí |  |
| `year` | Año. | smallint | sí |  |
| `exports_usd_k` | Exportaciones del reporter al socio (miles de USD). | numeric(20,3) | sí |  |
| `imports_usd_k` | Importaciones del reporter desde el socio (miles de USD). | numeric(20,3) | sí |  |
