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

#### `ref.area` · tabla · ~281 filas
Entidad geográfica: superset de `ref.country`.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `code` | Código identificador. | character varying(3) | no | PK |
| `name` | Nombre. | character varying(200) | no |  |
| `area_type` |  | character varying(20) | no |  |
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | sí | FK → ref.country.code |
| `notes` |  | character varying(300) | sí |  |

#### `ref.country` · tabla · ~250 filas
Lista de países del mundo, con su código ISO.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `code` | Código identificador. | character varying(3) | no | PK |
| `code_alpha2` | Código ISO-2 del país (ES, US...). | character varying(2) | sí |  |
| `name` | Nombre. | character varying(200) | no |  |
| `region` | Región del mundo. | character varying(100) | sí |  |
| `sub_region` | Subregión. | character varying(100) | sí |  |
| `income_group` | Grupo de renta (clasificación WB). | character varying(50) | sí |  |
| `currency_code` | Moneda del importe. | character varying(3) | sí |  |
| `capital` | Ciudad capital. | character varying(100) | sí |  |
| `latitude` | Latitud. | numeric(9,6) | sí |  |
| `longitude` | Longitud. | numeric(9,6) | sí |  |

#### `ref.currency` · tabla · ~178 filas
Lista de monedas (euro, dólar...).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `code` | Código identificador. | character varying(3) | no | PK |
| `name` | Nombre. | character varying(100) | sí |  |
| `symbol` | Símbolo de la moneda (€, $...). | character varying(10) | sí |  |
| `is_major` | Si es una divisa principal. | boolean | no |  |
| `decimal_places` | Nº de decimales de la moneda. | smallint | no |  |

#### `ref.exchange` · tabla · ~35 filas
Bolsas de valores (Nasdaq, NYSE...).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `mic` | Código MIC de la bolsa. | character varying(10) | sí |  |
| `name` | Nombre. | character varying(200) | no |  |
| `short_name` | Nombre corto de la bolsa. | character varying(50) | sí |  |
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | sí | FK → ref.country.code |
| `city` | Ciudad de la bolsa. | character varying(100) | sí |  |
| `timezone` | Zona horaria. | character varying(50) | sí |  |
| `currency_code` | Moneda del importe. | character varying(3) | sí | FK → ref.currency.code |
| `open_time` | Hora de apertura. | time without time zone | sí |  |
| `close_time` | Hora de cierre. | time without time zone | sí |  |
| `website` | Web de la empresa. | character varying(300) | sí |  |

#### `ref.hs_product` · tabla · ~97 filas
Catálogo de productos del Sistema Armonizado (HS): el código de cada tipo de mercancía (p.ej. '27' = combustibles) con su descripción. Da nombre a los productos del comercio.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `code` | Código HS del producto (2, 4 o 6 dígitos). | character varying(6) | no | PK |
| `description` | Nombre del producto. | character varying(500) | no |  |
| `level` | Nivel de detalle: 2, 4 o 6 dígitos. | smallint | no |  |
| `parent_code` | Producto padre (para la jerarquía HS). | character varying(6) | sí |  |

#### `ref.legal_entity` · tabla · ~355 filas
Entidad legal identificada por LEI (GLEIF).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `lei` |  | character varying(20) | no | PK |
| `legal_name` |  | character varying(500) | no |  |
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | sí | FK → ref.country.code |
| `legal_jurisdiction` |  | character varying(10) | sí |  |
| `entity_status` |  | character varying(20) | sí |  |
| `entity_category` |  | character varying(40) | sí |  |
| `parent_lei` |  | character varying(20) | sí |  |
| `registration_status` |  | character varying(30) | sí |  |
| `city` |  | character varying(120) | sí |  |

#### `ref.sector` · tabla · ~36 filas
Sectores económicos GICS (Tecnología, Salud...).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `gics_code` | Código GICS del sector. | character varying(10) | sí |  |
| `name` | Nombre. | character varying(200) | no |  |
| `parent_id` | Sector padre (jerarquía). | integer | sí | FK → ref.sector.id |
| `level` | Nivel: 1 = sector, 2 = industria. | smallint | sí |  |

### Esquema `meta`
_Metadatos y auditoría: fuentes, ejecuciones, calidad._

#### `meta.alembic_version` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `version_num` |  | character varying(32) | no | PK |

#### `meta.data_quality` · tabla · ~1,791 filas
Nota de calidad por dominio: cuántos países cubrimos y cómo de reciente es el dato.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `domain` | Dominio de datos afectado. | character varying(50) | no |  |
| `entity_type` | Tipo de entidad evaluada. | character varying(100) | no |  |
| `entity_id` | Entidad concreta evaluada. | character varying(200) | no |  |
| `completeness_score` | % de completitud (0-100). | numeric(5,2) | sí |  |
| `freshness_days` | Antigüedad del último dato. | integer | sí |  |
| `source_count` | Nº de fuentes que lo aportan. | integer | sí |  |
| `last_assessed` | Última evaluación. | timestamp with time zone | no |  |

#### `meta.data_source` · tabla · ~0 filas
Las fuentes de donde sacamos los datos (IMF, yfinance, SEC...).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `name` | Nombre. | character varying(100) | no |  |
| `display_name` | Nombre legible de la fuente. | character varying(200) | sí |  |
| `base_url` | URL base de la API. | character varying(500) | sí |  |
| `api_key_env_var` | Variable de entorno con la clave. | character varying(100) | sí |  |
| `rate_limit_per_second` | Límite de peticiones/segundo. | numeric(6,3) | sí |  |
| `daily_request_limit` | Límite diario de peticiones. | integer | sí |  |
| `is_enabled` | Si la fuente está activa. | boolean | no |  |
| `notes` | Notas. | text | sí |  |

#### `meta.fetch_run` · tabla · ~235,950 filas
Un registro por cada descarga hecha: cuándo, qué fuente, cuántos datos y si hubo errores. Es el 'diario' de descargas.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |
| `domain` | Dominio de datos afectado. | character varying(50) | no |  |
| `started_at` | Cuándo empezó la ejecución. | timestamp with time zone | no |  |
| `finished_at` | Cuándo terminó la ejecución. | timestamp with time zone | sí |  |
| `status` | Estado (running / success / failed). | character varying(20) | no |  |
| `records_fetched` | Registros descargados. | integer | no |  |
| `records_inserted` | Registros insertados. | integer | no |  |
| `records_updated` | Registros actualizados. | integer | no |  |
| `errors` | Número de errores. | integer | no |  |
| `params` | Parámetros usados en la ejecución. | jsonb | sí |  |
| `error_log` | Errores registrados, si los hubo. | jsonb | sí |  |

#### `meta.table_certification` · tabla · ~94 filas
Cómo se ha verificado cada tabla de datos.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `schema_name` |  | character varying(63) | no |  |
| `table_name` |  | character varying(63) | no |  |
| `estado` |  | character varying(40) | no |  |
| `metodo` |  | character varying(500) | sí |  |
| `motivo` |  | character varying(500) | sí |  |
| `filas` |  | bigint | sí |  |
| `referencias` |  | integer | sí |  |
| `certificado_por` |  | character varying(60) | sí |  |
| `certified_at` |  | timestamp with time zone | sí |  |

#### `meta.transform_run` · tabla · ~180 filas
Un registro por cada vez que transformamos datos crudos en datos limpios. El 'diario' de transformaciones.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `domain` | Dominio de datos afectado. | character varying(50) | no |  |
| `target_layer` | Capa destino (silver/gold). | character varying(20) | no |  |
| `started_at` | Cuándo empezó la ejecución. | timestamp with time zone | no |  |
| `finished_at` | Cuándo terminó la ejecución. | timestamp with time zone | sí |  |
| `status` | Estado (running / success / failed). | character varying(20) | no |  |
| `records_read` | Registros leídos. | integer | no |  |
| `records_written` | Registros escritos. | integer | no |  |
| `records_invalid` | Registros descartados por inválidos. | integer | no |  |
| `params` | Parámetros usados en la ejecución. | jsonb | sí |  |
| `error_log` | Errores registrados, si los hubo. | jsonb | sí |  |

## Renta variable y mercados financieros

### Esquema `equity`
_Renta variable: empresas, precios, fundamentales y 360°._

#### `equity.analyst_estimate` · tabla · ~228,204 filas
Previsiones de los analistas sobre beneficios e ingresos futuros.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `snapshot_date` | Día de la foto (los datos se acumulan por día). | date | no |  |
| `horizon` | Horizonte de la previsión (0q, +1q, 0y, +1y). | character varying(10) | no |  |
| `period_label` | Periodo estimado (p.ej. 2026Q2). | character varying(20) | sí |  |
| `eps_avg` | Beneficio por acción estimado (medio). | numeric(12,4) | sí |  |
| `eps_low` | BPA estimado mínimo. | numeric(12,4) | sí |  |
| `eps_high` | BPA estimado máximo. | numeric(12,4) | sí |  |
| `revenue_avg` | Ingresos estimados (medio). | numeric(20,2) | sí |  |
| `num_analysts` | Nº de analistas. | smallint | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `equity.balance_sheet` · tabla · ~22,342 filas
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
| `fetched_at` | Cuándo se descargó. | timestamp with time zone | no |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `equity.cash_flow` · tabla · ~22,026 filas
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
| `fetched_at` | Cuándo se descargó. | timestamp with time zone | no |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `equity.company` · tabla · ~11,012 filas
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
| `last_updated` | Última actualización. | timestamp with time zone | no |  |
| `lei` |  | character varying(20) | sí | FK → ref.legal_entity.lei |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `equity.dividend` · tabla · ~188,417 filas
Dividendos pagados por cada acción.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `ex_date` | Fecha ex-dividendo. | date | no |  |
| `pay_date` | Fecha de pago. | date | sí |  |
| `record_date` | Fecha de registro. | date | sí |  |
| `amount` | Importe del dividendo por acción. | numeric(12,6) | no |  |
| `currency_code` | Moneda del importe. | character varying(3) | sí |  |
| `dividend_type` | Tipo de dividendo. | character varying(20) | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `equity.earnings_date` · tabla · ~191,439 filas
Fechas de presentación de resultados, con lo esperado vs lo reportado.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `date` | Fecha del dato. | date | no |  |
| `eps_estimate` | Beneficio por acción esperado. | numeric(12,4) | sí |  |
| `reported_eps` | Beneficio por acción real. | numeric(12,4) | sí |  |
| `surprise_pct` | Sorpresa: desviación del real vs lo esperado (%). | numeric(10,4) | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `equity.earnings_revision` · tabla · ~228,204 filas
Cómo van cambiando esas previsiones (si los analistas revisan al alza o a la baja).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `snapshot_date` | Día de la foto (los datos se acumulan por día). | date | no |  |
| `horizon` | Horizonte de la previsión (0q, +1q, 0y, +1y). | character varying(10) | no |  |
| `eps_current` | BPA estimado ahora. | numeric(12,4) | sí |  |
| `eps_7d_ago` | BPA estimado hace 7 días. | numeric(12,4) | sí |  |
| `eps_30d_ago` | BPA estimado hace 30 días. | numeric(12,4) | sí |  |
| `up_last_30d` | Revisiones al alza (30 días). | smallint | sí |  |
| `down_last_30d` | Revisiones a la baja (30 días). | smallint | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `equity.factor_return` · tabla · ~18,702 filas
Rentabilidad de factores académicos (Fama-French).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `region` |  | character varying(20) | no |  |
| `frequency` | Frecuencia (anual, mensual, diario...). | character varying(10) | no |  |
| `factor` |  | character varying(10) | no |  |
| `date` | Fecha del dato. | date | no |  |
| `value_pct` |  | numeric(12,6) | no |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `equity.holder` · tabla · ~74,847 filas
Quién posee cada empresa: grandes fondos e instituciones, con su porcentaje.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `holder_type` | Tipo: institutional o mutualfund. | character varying(20) | no |  |
| `holder_name` | Nombre del accionista o fondo. | character varying(200) | no |  |
| `snapshot_date` | Día de la foto (los datos se acumulan por día). | date | no |  |
| `date_reported` | Fecha de la declaración. | date | sí |  |
| `pct_held` | % de la empresa que posee. | numeric(9,6) | sí |  |
| `shares` | Nº de acciones que posee. | bigint | sí |  |
| `value_usd` | Valor de la participación (USD). | numeric(20,2) | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `equity.income_statement` · tabla · ~21,743 filas
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
| `fetched_at` | Cuándo se descargó. | timestamp with time zone | no |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `equity.index_constituent_current` · tabla · ~1,362 filas
Qué empresas componen hoy cada índice.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `index_id` | Índice de mercado. | integer | no | FK → equity.market_index.id |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `weight` | Peso o ponderación en el índice. | numeric(8,5) | sí |  |
| `as_of_date` | Fecha de referencia del cálculo. | date | no |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `equity.index_price` · tabla · ~256,941 filas
Valor de cierre diario de cada índice.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `index_id` | Índice de mercado. | integer | no | FK → equity.market_index.id |
| `date` | Fecha del dato. | date | no |  |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `equity.insider_transaction` · tabla · ~210,101 filas
Compras y ventas de acciones por parte de directivos e insiders de la empresa.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `insider` | Nombre del directivo/insider. | character varying(200) | no |  |
| `position` | Cargo del insider. | character varying(200) | sí |  |
| `transaction` | Compra o venta. | character varying(100) | sí |  |
| `start_date` | Fecha de la operación. | date | sí |  |
| `shares` | Número de acciones. | bigint | sí |  |
| `value_usd` | Valor de la operación (USD). | numeric(20,2) | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `equity.market_index` · tabla · ~28 filas
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
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `equity.price_daily` · tabla · ~28,785,268 filas
El precio de cierre diario de cada acción (y máximo, mínimo, volumen...).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `date` | Fecha del dato. | date | no |  |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `adj_close` | Precio de cierre ajustado (dividendos/splits). | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `equity.price_intraday` · tabla · ~0 filas
Precio intraday OHLCV particionado por mes.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2023_08` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2023_09` · tabla · ~399 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2023_10` · tabla · ~462 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2023_11` · tabla · ~429 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2023_12` · tabla · ~420 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2024_01` · tabla · ~441 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2024_02` · tabla · ~420 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2024_03` · tabla · ~420 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2024_04` · tabla · ~462 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2024_05` · tabla · ~462 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2024_06` · tabla · ~399 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2024_07` · tabla · ~450 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2024_08` · tabla · ~462 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2024_09` · tabla · ~420 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2024_10` · tabla · ~483 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2024_11` · tabla · ~408 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2024_12` · tabla · ~429 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2025_01` · tabla · ~420 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2025_02` · tabla · ~399 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2025_03` · tabla · ~441 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2025_04` · tabla · ~441 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2025_05` · tabla · ~441 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2025_06` · tabla · ~420 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2025_07` · tabla · ~450 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2025_08` · tabla · ~441 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2025_09` · tabla · ~441 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2025_10` · tabla · ~483 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2025_11` · tabla · ~387 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2025_12` · tabla · ~450 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2026_01` · tabla · ~420 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2026_02` · tabla · ~399 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2026_03` · tabla · ~462 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2026_04` · tabla · ~441 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2026_05` · tabla · ~420 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2026_06` · tabla · ~441 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2026_07` · tabla · ~462 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2026_08` · tabla · ~3 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2026_09` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2026_10` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.price_intraday_2026_11` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `equity.ratios_mv` · materializada · ~10,449 filas
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
| `price_date` | Fecha del precio usado. | date | sí |  |
| `income_period` | Periodo de la cuenta de resultados. | date | sí |  |
| `balance_period` | Periodo del balance. | date | sí |  |
| `cashflow_period` | Periodo de los flujos de caja. | date | sí |  |
| `moneda_cuentas` |  | character varying(3) | sí |  |
| `moneda_coherente` |  | boolean | sí |  |
| `last_close` | Último precio de cierre. | numeric(24,10) | sí |  |
| `pe_ratio` | PER (precio / beneficio). | numeric | sí |  |
| `pb_ratio` | Precio / valor contable. | numeric | sí |  |
| `ps_ratio` | Precio / ventas. | numeric | sí |  |
| `roe` | Rentabilidad sobre patrimonio (ROE). | numeric | sí |  |
| `roa` | Rentabilidad sobre activos (ROA). | numeric | sí |  |
| `roic` | Rentabilidad sobre capital invertido. | numeric | sí |  |
| `gross_margin` | Margen bruto (%). | numeric | sí |  |
| `operating_margin` | Margen operativo (%). | numeric | sí |  |
| `net_margin` | Margen neto (%). | numeric | sí |  |
| `debt_equity` | Deuda / patrimonio. | numeric | sí |  |
| `debt_assets` | Deuda / activos. | numeric | sí |  |
| `fcf_yield` | Rentabilidad del flujo de caja libre. | numeric | sí |  |
| `revenue` | Ingresos totales (ventas). | numeric(18,2) | sí |  |
| `net_income` | Beneficio neto (lo que gana al final). | numeric(18,2) | sí |  |
| `ebitda` | EBITDA (beneficio antes de intereses, impuestos y amortizaciones). | numeric(18,2) | sí |  |
| `eps_diluted` | Beneficio por acción (diluido). | numeric(10,4) | sí |  |
| `total_equity` | Patrimonio neto total. | numeric(18,2) | sí |  |
| `total_assets` | Activos totales. | numeric(18,2) | sí |  |
| `free_cash_flow` | Flujo de caja libre. | numeric(18,2) | sí |  |
| `operating_cash_flow` | Flujo de caja de las operaciones. | numeric(18,2) | sí |  |

#### `equity.recommendation_trend` · tabla · ~12,630 filas
Resumen de cuántos analistas recomiendan comprar, mantener o vender.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `snapshot_date` | Día de la foto (los datos se acumulan por día). | date | no |  |
| `period` | Año del dato. | character varying(10) | no |  |
| `strong_buy` | Analistas: comprar fuerte. | smallint | sí |  |
| `buy` | Analistas: comprar. | smallint | sí |  |
| `hold` | Analistas: mantener. | smallint | sí |  |
| `sell` | Analistas: vender. | smallint | sí |  |
| `strong_sell` | Analistas: vender fuerte. | smallint | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `equity.shares_history` · tabla · ~3,377,997 filas
Número de acciones en circulación de la empresa a lo largo del tiempo.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `date` | Fecha del dato. | date | no |  |
| `shares` | Número de acciones. | bigint | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `equity.split` · tabla · ~6,755 filas
Splits (desdoblamientos) de acciones.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `date` | Fecha del dato. | date | no |  |
| `ratio_from` | Acciones antes del split. | numeric(10,4) | sí |  |
| `ratio_to` | Acciones después del split. | numeric(10,4) | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `equity.upgrade_downgrade` · tabla · ~331,351 filas
Cambios de recomendación y precio objetivo que hacen los analistas (comprar/vender).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `date` | Fecha del dato. | date | no |  |
| `firm` | Casa de análisis (Goldman...). | character varying(200) | no |  |
| `to_grade` | Nueva recomendación. | character varying(100) | sí |  |
| `from_grade` | Recomendación anterior. | character varying(100) | sí |  |
| `action` | Tipo de cambio (up/down/init). | character varying(50) | sí |  |
| `price_target` | Precio objetivo fijado. | numeric(14,4) | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

### Esquema `fi`
_Renta fija: bonos, ratings, curvas de tipos._

#### `fi.bond` · tabla · ~5,061 filas
Bonos (sobre todo deuda pública de EE.UU.).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `issuer_id` | Emisor del bono. | integer | sí | FK → fi.bond_issuer.id |
| `isin` | Código ISIN (identificador internacional del valor). | character varying(12) | sí |  |
| `name` | Nombre. | character varying(300) | sí |  |
| `coupon_rate` | Tipo de cupón (%). | numeric(8,4) | sí |  |
| `coupon_frequency` | Frecuencia del cupón. | smallint | sí |  |
| `maturity_date` | Fecha de vencimiento. | date | sí |  |
| `issue_date` | Fecha de emisión. | date | sí |  |
| `face_value` | Valor nominal. | numeric(14,2) | sí |  |
| `currency_code` | Moneda del importe. | character varying(3) | sí |  |
| `bond_type` | Tipo de bono. | character varying(30) | sí |  |
| `is_callable` | Si es amortizable anticipadamente. | boolean | no |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `fi.bond_issuer` · tabla · ~53 filas
Emisores de bonos (países).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `name` | Nombre. | character varying(300) | sí |  |
| `issuer_type` | Tipo de emisor (soberano...). | character varying(20) | no |  |
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | sí | FK → ref.country.code |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `fi.country_risk_premium` · tabla · ~175 filas
Prima de riesgo por país (datasets de Damodaran, NYU).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | no | FK → ref.country.code |
| `year` | Año. | smallint | no |  |
| `equity_risk_premium` |  | numeric(8,4) | sí |  |
| `country_risk_premium` |  | numeric(8,4) | sí |  |
| `default_spread` |  | numeric(8,4) | sí |  |
| `moodys_rating` |  | character varying(10) | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `fi.credit_rating` · tabla · ~10,563 filas
Ratings de crédito (calificaciones de solvencia).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `issuer_id` | Emisor del bono. | integer | no | FK → fi.bond_issuer.id |
| `agency` | Agencia de rating (Fitch...). | character varying(20) | no |  |
| `rating` | Calificación de crédito. | character varying(10) | no |  |
| `outlook` | Perspectiva (positiva/estable/negativa). | character varying(20) | sí |  |
| `rating_date` | Fecha del rating. | date | no |  |
| `previous_rating` | Rating anterior. | character varying(10) | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `fi.yield_curve` · tabla · ~68,422 filas
Curvas de tipos de interés (rendimiento de la deuda por plazo).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | no | FK → ref.country.code |
| `date` | Fecha del dato. | date | no |  |
| `maturity_months` | Plazo en meses. | smallint | no |  |
| `yield_pct` | Rendimiento (%). | numeric(8,4) | no |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

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
| `exchange` | Bolsa/mercado donde cotiza. | character varying(50) | sí |  |
| `yfinance_ticker` | Símbolo en yfinance. | character varying(20) | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `commodity.price_daily` · tabla · ~197,123 filas
Precio diario de cada materia prima.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `commodity_id` | Materia prima a la que pertenece. | integer | no | FK → commodity.commodity.id |
| `date` | Fecha del dato. | date | no |  |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `commodity.price_intraday` · tabla · ~0 filas
Precio intraday commodity (particionado por ts).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2023_08` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2023_09` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2023_10` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2023_11` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2023_12` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2024_01` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2024_02` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2024_03` · tabla · ~5,231 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2024_04` · tabla · ~10,719 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2024_05` · tabla · ~10,745 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2024_06` · tabla · ~9,248 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2024_07` · tabla · ~10,128 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2024_08` · tabla · ~10,514 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2024_09` · tabla · ~9,837 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2024_10` · tabla · ~11,294 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2024_11` · tabla · ~9,497 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2024_12` · tabla · ~9,768 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2025_01` · tabla · ~10,020 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2025_02` · tabla · ~9,297 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2025_03` · tabla · ~10,260 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2025_04` · tabla · ~10,211 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2025_05` · tabla · ~10,416 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2025_06` · tabla · ~9,961 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2025_07` · tabla · ~10,106 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2025_08` · tabla · ~9,784 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2025_09` · tabla · ~10,059 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2025_10` · tabla · ~11,014 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2025_11` · tabla · ~8,925 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2025_12` · tabla · ~10,085 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2026_01` · tabla · ~8,987 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2026_02` · tabla · ~8,960 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2026_03` · tabla · ~10,413 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2026_04` · tabla · ~9,851 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2026_05` · tabla · ~9,459 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2026_06` · tabla · ~10,042 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2026_07` · tabla · ~10,376 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2026_08` · tabla · ~1,896 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2026_09` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2026_10` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

#### `commodity.price_intraday_2026_11` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `commodity_id` | Materia prima a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume` | Volumen negociado. | bigint | sí |  |

### Esquema `forex`
_Divisas y tipos de cambio._

#### `forex.currency_pair` · tabla · ~115 filas
Pares de divisas (EUR/USD...).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `base_currency` | Divisa base. | character varying(3) | no | FK → ref.currency.code |
| `quote_currency` | Divisa cotizada. | character varying(3) | no | FK → ref.currency.code |
| `pair_code` | Código del par (EURUSD...). | character varying(7) | no |  |
| `category` | Categoría o dominio. | character varying(20) | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `forex.rate_daily` · tabla · ~677,061 filas
Tipo de cambio diario de cada par.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `pair_id` | Par de divisas al que pertenece. | integer | no | FK → forex.currency_pair.id |
| `date` | Fecha del dato. | date | no |  |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `forex.rate_intraday` · tabla · ~0 filas
Tipo de cambio intraday (particionado por ts).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2023_08` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2023_09` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2023_10` · tabla · ~17,670 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2023_11` · tabla · ~48,264 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2023_12` · tabla · ~44,496 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2024_01` · tabla · ~47,618 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2024_02` · tabla · ~44,642 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2024_03` · tabla · ~44,529 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2024_04` · tabla · ~46,109 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2024_05` · tabla · ~48,217 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2024_06` · tabla · ~42,278 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2024_07` · tabla · ~49,162 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2024_08` · tabla · ~48,402 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2024_09` · tabla · ~45,457 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2024_10` · tabla · ~49,343 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2024_11` · tabla · ~45,899 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2024_12` · tabla · ~47,299 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2025_01` · tabla · ~49,450 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2025_02` · tabla · ~44,129 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2025_03` · tabla · ~46,107 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2025_04` · tabla · ~48,109 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2025_05` · tabla · ~46,485 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2025_06` · tabla · ~45,485 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2025_07` · tabla · ~49,716 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2025_08` · tabla · ~45,808 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2025_09` · tabla · ~49,594 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2025_10` · tabla · ~51,269 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2025_11` · tabla · ~44,219 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2025_12` · tabla · ~51,239 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2026_01` · tabla · ~48,941 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2026_02` · tabla · ~44,837 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2026_03` · tabla · ~49,283 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2026_04` · tabla · ~49,423 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2026_05` · tabla · ~45,968 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2026_06` · tabla · ~48,785 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2026_07` · tabla · ~51,483 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2026_08` · tabla · ~9,173 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2026_09` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2026_10` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

#### `forex.rate_intraday_2026_11` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `pair_id` | Par de divisas al que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |

### Esquema `crypto`
_Criptomonedas._

#### `crypto.coin` · tabla · ~256 filas
Criptomonedas (Bitcoin, Ethereum...).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `coingecko_id` | ID en CoinGecko. | character varying(100) | no |  |
| `symbol` | Símbolo o código corto. | character varying(20) | no |  |
| `name` | Nombre. | character varying(200) | no |  |
| `category` | Categoría o dominio. | character varying(50) | sí |  |
| `market_cap_rank` | Puesto por capitalización. | smallint | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `crypto.market_dominance` · tabla · ~0 filas
Snapshot diario del mercado crypto.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `date` | Fecha del dato. | date | no |  |
| `total_market_cap_usd` | Capitalización total del mercado cripto (USD). | numeric(18,2) | sí |  |
| `btc_dominance_pct` | % que representa Bitcoin. | numeric(6,3) | sí |  |
| `eth_dominance_pct` | % que representa Ethereum. | numeric(6,3) | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `crypto.price_daily` · tabla · ~267,232 filas
Precio diario de cada cripto.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `coin_id` | Cripto a la que pertenece. | integer | no | FK → crypto.coin.id |
| `date` | Fecha del dato. | date | no |  |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume_usd` | Volumen negociado (USD). | numeric(18,2) | sí |  |
| `market_cap_usd` | Capitalización bursátil en dólares. | numeric(18,2) | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `crypto.price_intraday` · tabla · ~0 filas
Precio intraday crypto (particionado por ts).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2023_08` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2023_09` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2023_10` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2023_11` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2023_12` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2024_01` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2024_02` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2024_03` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2024_04` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2024_05` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2024_06` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2024_07` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2024_08` · tabla · ~124,440 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2024_09` · tabla · ~149,040 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2024_10` · tabla · ~154,194 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2024_11` · tabla · ~149,918 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2024_12` · tabla · ~156,860 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2025_01` · tabla · ~156,722 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2025_02` · tabla · ~141,930 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2025_03` · tabla · ~157,658 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2025_04` · tabla · ~152,640 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2025_05` · tabla · ~157,717 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2025_06` · tabla · ~152,342 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2025_07` · tabla · ~156,984 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2025_08` · tabla · ~156,984 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2025_09` · tabla · ~151,916 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2025_10` · tabla · ~156,973 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2025_11` · tabla · ~120,844 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2025_12` · tabla · ~156,258 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2026_01` · tabla · ~157,744 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2026_02` · tabla · ~142,480 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2026_03` · tabla · ~157,728 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2026_04` · tabla · ~146,922 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2026_05` · tabla · ~155,027 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2026_06` · tabla · ~145,586 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2026_07` · tabla · ~153,726 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2026_08` · tabla · ~30,462 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2026_09` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2026_10` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

#### `crypto.price_intraday_2026_11` · tabla · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `coin_id` | Cripto a la que pertenece. | integer | no | PK |
| `ts` |  | timestamp with time zone | no | PK |
| `interval` |  | character varying(3) | no | PK |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | sí |  |
| `volume_usd` |  | numeric(18,2) | sí |  |

### Esquema `fund`
_ETFs y fondos._

#### `fund.fund` · tabla · ~496 filas
ETFs y fondos de inversión.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `ticker` | Símbolo bursátil (p.ej. AAPL). | character varying(20) | sí |  |
| `name` | Nombre. | character varying(500) | no |  |
| `fund_type` | Tipo (ETF, fondo...). | character varying(20) | no |  |
| `asset_class` | Clase de activo. | character varying(50) | sí |  |
| `geography` | Geografía a la que invierte. | character varying(100) | sí |  |
| `strategy` | Estrategia. | character varying(100) | sí |  |
| `provider` | Gestora. | character varying(100) | sí |  |
| `expense_ratio` | Comisión anual (%). | numeric(6,4) | sí |  |
| `aum_usd` | Patrimonio gestionado (USD). | numeric(18,2) | sí |  |
| `inception_date` | Fecha de creación del fondo. | date | sí |  |
| `currency_code` | Moneda del importe. | character varying(3) | sí |  |
| `exchange_id` | Bolsa de valores. | integer | sí | FK → ref.exchange.id |
| `is_active` | Si sigue cotizando (no deslistada). | boolean | no |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `fund.nav_daily` · tabla · ~1,379,929 filas
Valor liquidativo (NAV) diario de cada fondo.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `fund_id` | Fondo al que pertenece. | integer | no | FK → fund.fund.id |
| `date` | Fecha del dato. | date | no |  |
| `nav` | Valor liquidativo (NAV). | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

### Esquema `alt`
_Datos alternativos: sentimiento, vivienda._

#### `alt.sentiment_indicator` · tabla · ~0 filas
Definición de indicador de sentimiento.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `code` | Código identificador. | character varying(50) | no |  |
| `name` | Nombre. | character varying(200) | sí |  |
| `description` | Descripción libre. | text | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `alt.sentiment_value` · tabla · ~6,254 filas
Valor diario de indicador de sentimiento.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `indicator_id` | Indicador al que pertenece. | integer | no | FK → alt.sentiment_indicator.id |
| `date` | Fecha del dato. | date | no |  |
| `value` | Valor del dato. | numeric(12,4) | no |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

## Economía mundial

### Esquema `macro`
_Economía mundial como series país × indicador × fecha._

#### `macro.data_point` · tabla · ~9,089,682 filas
El dato en sí: el valor de una serie en una fecha (p.ej. inflación de España en 2022 = 8,3%).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `series_id` | Serie temporal a la que pertenece. | integer | no | FK → macro.series.id |
| `date` | Fecha del dato. | date | no |  |
| `value` | El valor del indicador en esa fecha. | numeric(20,6) | no |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |
| `fetched_at` | Cuándo se descargó. | timestamp with time zone | no |  |
| `is_forecast` |  | boolean | no |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `macro.data_point_vintage` · tabla · ~85,467 filas
Como data_point pero 'point-in-time': guarda qué valor se conocía en cada fecha de publicación. Permite reconstruir los datos disponibles en el pasado sin sesgo de revisión (p.ej. el PIB de EE.UU. que se sabía en 2008, antes de revisarse).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `series_id` | Serie temporal a la que pertenece. | integer | no | FK → macro.series.id |
| `obs_date` | Fecha a la que se refiere el dato (p.ej. el trimestre medido). | date | no |  |
| `vintage_date` | Fecha de publicación: desde cuándo se conocía ese valor. | date | no |  |
| `value` | El valor tal como se publicó en esa fecha (luego puede haberse revisado). | numeric(20,6) | no |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `macro.indicator` · tabla · ~1,835 filas
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
| `seasonal_adjustment` | Ajuste estacional aplicado. | character varying(20) | sí |  |
| `description` | Descripción libre. | text | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `macro.indicator_source` · tabla · ~1,762 filas
Cómo se llama cada indicador en cada fuente (el mismo 'PIB' tiene códigos distintos en IMF y World Bank).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `indicator_id` | Indicador al que pertenece. | integer | no | FK → macro.indicator.id |
| `source_id` | Fuente de la que procede el dato. | integer | no | FK → meta.data_source.id |
| `external_code` | Código del indicador en la fuente. | character varying(200) | no |  |
| `external_name` | Nombre en la fuente. | character varying(500) | sí |  |
| `priority` | Prioridad si hay varias fuentes. | smallint | no |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `macro.series` · tabla · ~272,274 filas
Una serie = un indicador para un país concreto (p.ej. 'inflación de España'). Agrupa sus valores en el tiempo.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `indicator_id` | Indicador al que pertenece. | integer | no | FK → macro.indicator.id |
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | sí | FK → ref.country.code |
| `region_code` | Región (para agregados regionales: mundo, UE...). | character varying(20) | sí |  |
| `last_value` | Último valor conocido de la serie. | numeric(20,6) | sí |  |
| `last_date` | Fecha del último dato disponible. | date | sí |  |
| `point_count` | Cuántos datos tiene la serie. | integer | no |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

### Esquema `trade`
_Comercio internacional bilateral (país × socio)._

#### `trade.flow` · tabla · ~1,121,103 filas
Comercio entre dos países: cuánto exporta/importa un país a otro cada año (a nivel total o por producto HS).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `reporter_code` | País que declara (exporta/importa). | character varying(3) | no | FK → ref.area.code |
| `partner_code` | País socio comercial. | character varying(3) | no | FK → ref.area.code |
| `product_code` | Producto (Total = todos los productos). | character varying(20) | no | FK → ref.hs_product.code |
| `flow` | Sentido: X = exportación, M = importación. | character varying(1) | no |  |
| `period` | Año del dato. | smallint | no |  |
| `value_usd_k` | Valor comerciado en miles de dólares. | numeric(20,3) | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |
| `fetched_at` | Cuándo se descargó. | timestamp with time zone | no |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

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
| `fetched_at` | Cuándo se descargó. | timestamp with time zone | no |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

### Esquema `agri`
_Producción agrícola por país, cultivo/ganado y elemento._

#### `agri.production` · tabla · ~2,938,249 filas
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
| `fetched_at` | Cuándo se descargó. | timestamp with time zone | no |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

### Esquema `country`
_Perfiles de país: demografía, impuestos._

#### `country.demographics` · tabla · ~1,040 filas
Datos demográficos por país.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | no | FK → ref.country.code |
| `year` | Año. | smallint | no |  |
| `total_population` | Población total. | bigint | sí |  |
| `median_age` | Edad mediana. | numeric(5,2) | sí |  |
| `urban_population_pct` | % de población urbana. | numeric(6,3) | sí |  |
| `life_expectancy` | Esperanza de vida. | numeric(5,2) | sí |  |
| `fertility_rate` | Tasa de fertilidad. | numeric(4,2) | sí |  |
| `labor_force` | Población activa. | bigint | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `country.profile` · tabla · ~212 filas
Perfil de cada país (datos generales).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | no | PK |
| `population` | Población. | bigint | sí |  |
| `population_year` | Año de la población. | smallint | sí |  |
| `gdp_usd` | PIB (USD). | numeric(18,2) | sí |  |
| `gdp_per_capita_usd` | PIB por habitante (USD). | numeric(12,2) | sí |  |
| `hdi` | Índice de Desarrollo Humano. | numeric(5,4) | sí |  |
| `gini_index` | Índice de Gini (desigualdad). | numeric(5,2) | sí |  |
| `ease_of_business_rank` | Ranking de facilidad para hacer negocios. | smallint | sí |  |
| `political_stability_index` | Índice de estabilidad política. | numeric(6,4) | sí |  |
| `last_updated` | Última actualización. | timestamp with time zone | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `country.tax_rate` · tabla · ~155 filas
Tipos impositivos por país y año.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | no | FK → ref.country.code |
| `year` | Año. | smallint | no |  |
| `corporate_tax_rate` | Impuesto de sociedades (%). | numeric(6,3) | sí |  |
| `top_income_tax_rate` | Tipo máximo de IRPF (%). | numeric(6,3) | sí |  |
| `vat_rate` | IVA (%). | numeric(6,3) | sí |  |
| `capital_gains_tax_rate` | Impuesto sobre plusvalías (%). | numeric(6,3) | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

### Esquema `realestate`
_Inmobiliario: índices de precio de vivienda por país._

#### `realestate.price_index` · tabla · ~85 filas
Catálogo de índices de precio de vivienda (BIS, OCDE, Case-Shiller).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `code` | Código identificador. | character varying(80) | no |  |
| `name` | Nombre. | character varying(300) | no |  |
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | sí | FK → ref.country.code |
| `segment` |  | character varying(20) | sí |  |
| `measure` |  | character varying(20) | sí |  |
| `frequency` | Frecuencia (anual, mensual, diario...). | character varying(20) | sí |  |
| `base_period` |  | character varying(20) | sí |  |
| `unit` | Unidad de medida. | character varying(50) | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `realestate.price_index_value` · tabla · ~14,982 filas
Serie temporal de cada índice inmobiliario.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `index_id` | Índice de mercado. | integer | no | FK → realestate.price_index.id |
| `date` | Fecha del dato. | date | no |  |
| `value` | Valor del dato. | numeric(18,6) | no |  |
| `is_forecast` |  | boolean | no |  |
| `fetched_at` | Cuándo se descargó. | timestamp with time zone | no |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

### Esquema `calendar`
_Calendario económico: publicaciones macro y sus fechas._

#### `calendar.release` · tabla · ~330 filas
Publicación periódica de un organismo estadístico (nóminas, IPC, PIB...).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `external_id` |  | character varying(50) | no |  |
| `name` | Nombre. | character varying(300) | no |  |
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | sí | FK → ref.country.code |
| `agency` |  | character varying(200) | sí |  |
| `link` |  | character varying(500) | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `calendar.release_date` · tabla · ~91,326 filas
Fecha en que una publicación sale o saldrá; `is_scheduled` marca las futuras.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `release_id` |  | integer | no | FK → calendar.release.id |
| `date` | Fecha del dato. | date | no |  |
| `is_scheduled` |  | boolean | no |  |
| `fetched_at` | Cuándo se descargó. | timestamp with time zone | no |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

## Derivados

### Esquema `deriv`
_Derivados: snapshots de cadenas de opciones._

#### `deriv.cot_contract` · tabla · ~946 filas
Contrato de futuros del informe COT de la CFTC.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `code` | Código identificador. | character varying(12) | no | PK |
| `name` | Nombre. | character varying(200) | no |  |
| `exchange` |  | character varying(20) | sí |  |
| `commodity_group` |  | character varying(60) | sí |  |
| `commodity_subgroup` |  | character varying(80) | sí |  |
| `contract_units` |  | character varying(120) | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `deriv.cot_report` · tabla · ~286,694 filas
Posicionamiento semanal declarado a la CFTC.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `contract_code` |  | character varying(12) | no | FK → deriv.cot_contract.code |
| `report_date` |  | date | no |  |
| `open_interest` |  | bigint | sí |  |
| `comm_long` |  | bigint | sí |  |
| `comm_short` |  | bigint | sí |  |
| `noncomm_long` |  | bigint | sí |  |
| `noncomm_short` |  | bigint | sí |  |
| `noncomm_spread` |  | bigint | sí |  |
| `nonrept_long` |  | bigint | sí |  |
| `nonrept_short` |  | bigint | sí |  |
| `traders_total` |  | integer | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |
| `fetched_at` | Cuándo se descargó. | timestamp with time zone | no |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `deriv.futures_contract` · tabla · ~0 filas
Contrato de futuros (índice, bono, divisa).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `code` | Código identificador. | character varying(20) | no |  |
| `name` | Nombre. | character varying(200) | no |  |
| `underlying` |  | character varying(50) | sí |  |
| `category` | Categoría o dominio. | character varying(30) | sí |  |
| `yfinance_ticker` |  | character varying(30) | no |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `deriv.futures_daily` · tabla · ~92,083 filas
Precio diario de futuros.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `contract_id` |  | integer | no | FK → deriv.futures_contract.id |
| `date` | Fecha del dato. | date | no |  |
| `open` | Precio de apertura. | numeric(24,10) | sí |  |
| `high` | Precio máximo del día. | numeric(24,10) | sí |  |
| `low` | Precio mínimo del día. | numeric(24,10) | sí |  |
| `close` | Precio de cierre. | numeric(24,10) | no |  |
| `volume` | Volumen negociado. | bigint | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `deriv.option_snapshot` · tabla · ~69,602 filas
Foto diaria de las opciones (contratos de compra/venta) de las empresas más líquidas.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `snapshot_date` | Día de la foto (los datos se acumulan por día). | date | no |  |
| `expiry` | Fecha de vencimiento del contrato. | date | no |  |
| `option_type` | C = call (compra), P = put (venta). | character varying(1) | no |  |
| `strike` | Precio de ejercicio del contrato. | numeric(14,4) | no |  |
| `last_price` | Último precio del contrato. | numeric(14,4) | sí |  |
| `bid` | Precio de compra (bid). | numeric(14,4) | sí |  |
| `ask` | Precio de venta (ask). | numeric(14,4) | sí |  |
| `volume` | Volumen negociado. | integer | sí |  |
| `open_interest` | Contratos abiertos vivos. | integer | sí |  |
| `implied_vol` | Volatilidad implícita. | numeric(10,6) | sí |  |
| `fetched_at` | Cuándo se descargó. | timestamp with time zone | no |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `deriv.volatility_daily` · tabla · ~56,877 filas
Precio diario de índice de volatilidad.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `index_id` | Índice de mercado. | integer | no | FK → deriv.volatility_index.id |
| `date` | Fecha del dato. | date | no |  |
| `open` | Precio de apertura. | numeric(10,4) | sí |  |
| `high` | Precio máximo del día. | numeric(10,4) | sí |  |
| `low` | Precio mínimo del día. | numeric(10,4) | sí |  |
| `close` | Precio de cierre. | numeric(10,4) | no |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí | FK → meta.data_source.id |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `deriv.volatility_index` · tabla · ~0 filas
Índice de volatilidad de referencia.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | integer | no | PK |
| `code` | Código identificador. | character varying(20) | no |  |
| `name` | Nombre. | character varying(200) | no |  |
| `underlying` |  | character varying(50) | sí |  |
| `yfinance_ticker` |  | character varying(30) | no |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

## Medallion — aterrizaje y analítica

### Esquema `bronze`
_Aterrizaje crudo (JSONB) de las fuentes nuevas._

#### `bronze.analyst_snapshot` · tabla · ~99,120 filas
Foto diaria de datos de analistas de yfinance (por ticker).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |
| `ingested_at` | Cuándo se guardó el dato crudo. | timestamp with time zone | no |  |
| `ticker` | Símbolo bursátil (p.ej. AAPL). | character varying(20) | no |  |
| `snapshot_date` | Día de la foto (los datos se acumulan por día). | date | no |  |
| `payload` | Respuesta cruda de la API (JSON), tal cual llegó. | jsonb | no |  |

#### `bronze.api_response` · tabla · ~319 filas
La respuesta cruda de una API macro, guardada tal cual por si hay que reprocesarla.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |
| `ingested_at` | Cuándo se guardó el dato crudo. | timestamp with time zone | no |  |
| `source_name` | Nombre de la fuente. | character varying(50) | no |  |
| `dataset` | Conjunto de datos descargado. | character varying(120) | no |  |
| `params` | Parámetros usados en la ejecución. | jsonb | sí |  |
| `payload` | Respuesta cruda de la API (JSON), tal cual llegó. | jsonb | no |  |

#### `bronze.constituents_snapshot` · tabla · ~6 filas
Foto cruda de constituyentes de un índice (Wikipedia/GitHub).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |
| `ingested_at` | Cuándo se guardó el dato crudo. | timestamp with time zone | no |  |
| `index_code` | Índice (SP500...). | character varying(50) | no |  |
| `source_kind` | Origen (wikipedia/github). | character varying(30) | no |  |
| `payload` | Respuesta cruda de la API (JSON), tal cual llegó. | jsonb | no |  |

#### `bronze.sec_companyfacts` · tabla · ~28,351 filas
El JSON crudo con todos los datos financieros que publica la SEC de cada empresa.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |
| `ingested_at` | Cuándo se guardó el dato crudo. | timestamp with time zone | no |  |
| `cik` | Identificador CIK de la empresa en SEC. | character varying(10) | no |  |
| `ticker` | Símbolo bursátil (p.ej. AAPL). | character varying(20) | sí |  |
| `payload` | Respuesta cruda de la API (JSON), tal cual llegó. | jsonb | no |  |

#### `bronze.yf_profile` · tabla · ~4,967 filas
El perfil completo de una empresa tal cual lo devuelve yfinance.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |
| `ingested_at` | Cuándo se guardó el dato crudo. | timestamp with time zone | no |  |
| `ticker` | Símbolo bursátil (p.ej. AAPL). | character varying(20) | no |  |
| `snapshot_date` | Día de la foto (los datos se acumulan por día). | date | no |  |
| `payload` | Respuesta cruda de la API (JSON), tal cual llegó. | jsonb | no |  |

### Esquema `gold`
_Capa analítica point-in-time: hechos, dimensiones y marts._

#### `gold.dim_company` · tabla · ~11,012 filas
Ficha resumida de cada empresa para análisis (con su sector ya incorporado).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_key` | Clave subrogada de la empresa. | integer | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `ticker` | Símbolo bursátil (p.ej. AAPL). | character varying(20) | no |  |
| `name` | Nombre. | character varying(500) | sí |  |
| `sector_id` | Sector GICS. | integer | sí |  |
| `sector_name` | Nombre del sector. | character varying(200) | sí |  |
| `industry_id` | Industria (nivel 2 GICS). | integer | sí |  |
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | sí |  |
| `currency_code` | Moneda del importe. | character varying(3) | sí |  |
| `is_active` | Si sigue cotizando (no deslistada). | boolean | no |  |
| `delisted_date` | Fecha en que dejó de cotizar. | date | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `gold.dim_country` · tabla · ~250 filas
Ficha de cada país (región, grupo de renta).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | no | PK |
| `name` | Nombre. | character varying(200) | no |  |
| `region` | Región. | character varying(100) | sí |  |
| `sub_region` | Subregión. | character varying(100) | sí |  |
| `income_group` | Grupo de renta. | character varying(50) | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `gold.dim_data_source` · vista · ~0 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `name` | Nombre. | character varying(100) | sí |  |
| `display_name` |  | character varying(200) | sí |  |
| `base_url` |  | character varying(500) | sí |  |
| `is_enabled` |  | boolean | sí |  |
| `total_runs` |  | bigint | sí |  |
| `successful_runs` |  | bigint | sí |  |
| `last_run` |  | timestamp with time zone | sí |  |
| `total_records` |  | bigint | sí |  |

#### `gold.dim_date` · tabla · ~23,593 filas
Calendario: una fila por día, con año, trimestre...

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `date_key` | La fecha (clave). | date | no | PK |
| `year` | Año. | smallint | no |  |
| `quarter` | Trimestre (1-4). | smallint | no |  |
| `month` | Mes (1-12). | smallint | no |  |
| `day_of_week` | Día de la semana. | smallint | no |  |
| `is_month_end` | Si es fin de mes. | boolean | no |  |
| `is_trading_day` | Si hubo mercado ese día. | boolean | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `gold.dim_indicator` · vista · ~0 filas
Catálogo autodocumentado de indicadores macro (código, fuente, cobertura, rango).

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `code` | Código identificador. | character varying(100) | sí |  |
| `name` | Nombre. | character varying(300) | sí |  |
| `category` | Categoría o dominio. | character varying(100) | sí |  |
| `unit` | Unidad de medida. | character varying(50) | sí |  |
| `frequency` | Frecuencia (anual, mensual, diario...). | character varying(20) | sí |  |
| `sources` | Fuentes que proveen el indicador. | text | sí |  |
| `n_countries` | Nº de países cubiertos. | bigint | sí |  |
| `first_date` | Fecha del primer dato. | date | sí |  |
| `last_date` | Fecha del último dato. | date | sí |  |
| `n_points` | Nº total de datos. | bigint | sí |  |

#### `gold.fact_factor_scores` · tabla · ~175,255 filas
Puntuaciones de factores de inversión (Value/Quality/Momentum) de cada empresa, normalizadas por sector.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `as_of_date` | Fecha de referencia del cálculo. | date | no |  |
| `factor` | value, quality o momentum. | character varying(30) | no |  |
| `universe` | Universo de cálculo (sp500_pit...). | character varying(30) | no |  |
| `raw_value` | Valor crudo del factor. | numeric(18,6) | sí |  |
| `z_score` | Puntuación normalizada (global). | numeric(10,6) | sí |  |
| `z_sector_neutral` | Puntuación normalizada dentro de su sector (para comparar manzanas con manzanas). | numeric(10,6) | sí |  |
| `percentile` | Percentil dentro del universo. | numeric(7,4) | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `gold.fact_fundamentals_pit` · tabla · ~33,174,290 filas
Todos los datos financieros de las empresas US con la fecha en que se publicaron (para saber qué se sabía en cada momento). Es la tabla más grande.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `id` | Identificador único de la fila. | bigint | no | PK |
| `company_id` | Empresa a la que pertenece. | integer | no | FK → equity.company.id |
| `statement_type` | Tipo: income/balance/cashflow o la taxonomía XBRL. | character varying(10) | no |  |
| `fiscal_year` | Año fiscal del periodo. | smallint | no |  |
| `fiscal_quarter` | Trimestre fiscal (vacío = dato anual). | smallint | sí |  |
| `period_end_date` | Fecha de cierre del periodo contable. | date | no |  |
| `filed_date` | Fecha en que se publicó/presentó el dato. | date | no |  |
| `publish_date` | Fecha de publicación. | date | sí |  |
| `metric` | Concepto financiero (revenue, net_income o el código XBRL completo). | character varying(150) | no |  |
| `value` | Importe del concepto. | numeric(28,6) | sí |  |
| `currency_code` | Moneda del importe. | character varying(3) | sí |  |
| `form` | Formulario SEC (10-K, 10-Q...). | character varying(10) | sí |  |
| `source_id` | Fuente de la que procede el dato. | integer | sí |  |
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `gold.index_membership` · tabla · ~1,264 filas
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
| `fetch_run_id` | Descarga que trajo el dato (auditoría). | integer | sí |  |

#### `gold.mart_benchmark_returns` · materializada · ~32,464 filas
Retorno diario del pool S&P 500 equiponderado (survivorship-free) vs SPY.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `date` | Fecha del dato. | date | sí |  |
| `method` | Método: equal_weight (pool) o spy. | character varying(20) | sí |  |
| `ret` | Retorno diario. | numeric | sí |  |

#### `gold.mart_climate_risk` · materializada · ~40,539 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | sí |  |
| `year` | Año. | smallint | sí |  |
| `ndgain_score` |  | numeric | sí |  |
| `ndgain_vulnerability` |  | numeric | sí |  |
| `ndgain_readiness` |  | numeric | sí |  |
| `co2_mt` |  | numeric | sí |  |
| `co2_per_capita_t` |  | numeric | sí |  |
| `co2_share_global_pct` |  | numeric | sí |  |
| `ghg_mt` |  | numeric | sí |  |
| `renewable_energy_pct` |  | numeric | sí |  |
| `edgar_co2_energy_mt` |  | numeric | sí |  |
| `edgar_co2_industry_mt` |  | numeric | sí |  |
| `edgar_ch4_mt` |  | numeric | sí |  |
| `edgar_n2o_mt` |  | numeric | sí |  |

#### `gold.mart_company_macro` · materializada · ~118,561 filas
Cada empresa cruzada con la macro de su país: PIB, inflación, paro, tipos... por año. Para correlacionar rendimiento empresarial con el ciclo económico.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | sí |  |
| `ticker` | Símbolo bursátil (p.ej. AAPL). | character varying(20) | sí |  |
| `company_name` |  | character varying(500) | sí |  |
| `sector_name` |  | character varying(200) | sí |  |
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | sí |  |
| `year` | Año. | smallint | sí |  |
| `gdp_growth_pct` |  | numeric | sí |  |
| `inflation_pct` |  | numeric | sí |  |
| `unemployment_pct` |  | numeric | sí |  |
| `policy_rate_pct` |  | numeric | sí |  |
| `gov_debt_pct_gdp` |  | numeric | sí |  |
| `current_account_pct_gdp` |  | numeric | sí |  |
| `life_expectancy_yrs` |  | numeric | sí |  |
| `income_gini` |  | numeric | sí |  |
| `exports_usd_bn` |  | numeric | sí |  |
| `imports_usd_bn` |  | numeric | sí |  |
| `fdi_inflows_usd_bn` |  | numeric | sí |  |
| `reserves_total_usd_bn` |  | numeric | sí |  |

#### `gold.mart_country_governance` · materializada · ~11,227 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | sí |  |
| `year` | Año. | smallint | sí |  |
| `wgi_corruption_control` |  | numeric | sí |  |
| `wgi_gov_effectiveness` |  | numeric | sí |  |
| `wgi_political_stability` |  | numeric | sí |  |
| `wgi_rule_of_law` |  | numeric | sí |  |
| `wgi_regulatory_quality` |  | numeric | sí |  |
| `wgi_voice_accountability` |  | numeric | sí |  |
| `ti_cpi_score` |  | numeric | sí |  |
| `fh_freedom_score` |  | numeric | sí |  |
| `fh_political_rights` |  | numeric | sí |  |
| `fh_civil_liberties` |  | numeric | sí |  |
| `fsi_total` |  | numeric | sí |  |
| `fsi_cohesion` |  | numeric | sí |  |
| `fsi_economic` |  | numeric | sí |  |
| `vdem_polyarchy` |  | numeric | sí |  |
| `vdem_liberal` |  | numeric | sí |  |
| `vdem_corruption` |  | numeric | sí |  |
| `vdem_media_freedom` |  | numeric | sí |  |
| `vdem_judicial_indep` |  | numeric | sí |  |

#### `gold.mart_country_year` · materializada · ~40,539 filas
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
| `life_expectancy_yrs` | Esperanza de vida al nacer, en años (WHO). | numeric | sí |  |
| `infant_mortality_per_1000` | Mortalidad infantil por cada 1.000 nacidos vivos (WHO). | numeric | sí |  |
| `health_exp_pct_gdp` | Gasto sanitario como % del PIB (WHO). | numeric | sí |  |
| `income_top1_pct` | % de la renta nacional que se lleva el 1% más rico (WID). | numeric | sí |  |
| `income_top10_pct` | % de la renta del 10% más rico (WID). | numeric | sí |  |
| `wealth_top1_pct` | % de la riqueza en manos del 1% más rico (WID). | numeric | sí |  |
| `income_gini` | Índice de Gini de la renta (0 = igualdad total, 1 = desigualdad máxima) (WID). | numeric | sí |  |
| `policy_rate_pct` | Tipo de interés oficial del banco central, en % (BIS). | numeric | sí |  |
| `education_exp_pct_gdp` | Gasto público en educación como % del PIB (World Bank). | numeric | sí |  |
| `tertiary_enrollment_pct` | Matrícula universitaria bruta, % de la población en edad (World Bank). | numeric | sí |  |
| `internet_users_pct` | Personas que usan internet, % de la población (World Bank). | numeric | sí |  |
| `mobile_per_100` | Suscripciones de telefonía móvil por cada 100 personas (World Bank). | numeric | sí |  |
| `rd_exp_pct_gdp` | Gasto en investigación y desarrollo como % del PIB (World Bank). | numeric | sí |  |
| `poverty_190_pct` | Población bajo la línea de pobreza de 3 USD/día (World Bank). | numeric | sí |  |
| `corruption_control_score` | Control de la corrupción (0-100): cuánto se controlan los sobornos y la corrupción pública (World Bank WGI). | numeric | sí |  |
| `gov_effectiveness_score` | Eficacia del gobierno (0-100): calidad de servicios públicos y burocracia. | numeric | sí |  |
| `political_stability_score` | Estabilidad política (0-100): ausencia de violencia y terrorismo. | numeric | sí |  |
| `rule_of_law_score` | Estado de derecho (0-100): confianza en contratos, policía, tribunales. | numeric | sí |  |
| `regulatory_quality_score` | Calidad regulatoria (0-100): políticas que favorecen el sector privado. | numeric | sí |  |
| `voice_accountability_score` | Voz y rendición de cuentas (0-100): libertad de expresión, prensa y voto. | numeric | sí |  |
| `tourism_arrivals` |  | numeric | sí |  |
| `tourism_receipts_usd_bn` |  | numeric | sí |  |
| `tourism_expenditure_usd_bn` |  | numeric | sí |  |
| `net_migration` |  | numeric | sí |  |
| `migrant_stock` |  | numeric | sí |  |
| `migrant_stock_pct` |  | numeric | sí |  |
| `refugees_hosted` |  | numeric | sí |  |
| `fdi_inflows_usd_bn` |  | numeric | sí |  |
| `fdi_outflows_usd_bn` |  | numeric | sí |  |
| `fdi_net_usd_bn` |  | numeric | sí |  |
| `bop_goods_exports_bn` |  | numeric | sí |  |
| `bop_goods_imports_bn` |  | numeric | sí |  |
| `bop_services_exports_bn` |  | numeric | sí |  |
| `bop_services_imports_bn` |  | numeric | sí |  |
| `bop_primary_income_net_bn` |  | numeric | sí |  |
| `reserves_total_usd_bn` |  | numeric | sí |  |
| `reserves_months_imports` |  | numeric | sí |  |
| `remittances_received_usd_bn` |  | numeric | sí |  |
| `ti_cpi_score` |  | numeric | sí |  |
| `fh_freedom_score` |  | numeric | sí |  |
| `fh_political_rights` |  | numeric | sí |  |
| `fh_civil_liberties` |  | numeric | sí |  |
| `population_total` |  | numeric | sí |  |
| `pop_growth_pct` |  | numeric | sí |  |
| `urban_pop_pct` |  | numeric | sí |  |
| `fertility_rate` |  | numeric | sí |  |
| `labor_force_total` |  | numeric | sí |  |
| `labor_participation_pct` |  | numeric | sí |  |
| `exports_pct_gdp` |  | numeric | sí |  |
| `imports_pct_gdp` |  | numeric | sí |  |
| `trade_openness_pct` |  | numeric | sí |  |
| `tax_revenue_pct_gdp` |  | numeric | sí |  |
| `market_cap_pct_gdp` |  | numeric | sí |  |
| `broad_money_pct_gdp` |  | numeric | sí |  |
| `credit_private_pct_gdp` |  | numeric | sí |  |
| `lending_rate` |  | numeric | sí |  |
| `deposit_rate` |  | numeric | sí |  |
| `real_interest_rate` |  | numeric | sí |  |
| `renewable_energy_pct` |  | numeric | sí |  |
| `military_exp_usd_mn` |  | numeric | sí |  |
| `military_exp_pct_gdp` |  | numeric | sí |  |
| `military_exp_pc` |  | numeric | sí |  |
| `hdi_score` |  | numeric | sí |  |
| `gender_dev_index` |  | numeric | sí |  |
| `gender_ineq_index` |  | numeric | sí |  |
| `ndgain_score` |  | numeric | sí |  |
| `ndgain_vulnerability` |  | numeric | sí |  |
| `ndgain_readiness` |  | numeric | sí |  |
| `fragile_state_index` |  | numeric | sí |  |
| `vdem_polyarchy` |  | numeric | sí |  |
| `vdem_liberal` |  | numeric | sí |  |
| `vdem_corruption` |  | numeric | sí |  |
| `vdem_media_freedom` |  | numeric | sí |  |
| `vdem_judicial_indep` |  | numeric | sí |  |
| `undesa_pop_total` |  | numeric | sí |  |
| `median_age` |  | numeric | sí |  |
| `old_depend_ratio` |  | numeric | sí |  |
| `young_depend_ratio` |  | numeric | sí |  |
| `undesa_fertility` |  | numeric | sí |  |
| `patent_applications` |  | numeric | sí |  |
| `patent_grants` |  | numeric | sí |  |
| `literacy_rate_pct` |  | numeric | sí |  |
| `mean_school_years` |  | numeric | sí |  |
| `pupil_teacher_ratio` |  | numeric | sí |  |
| `gfs_tax_total_pct` |  | numeric | sí |  |
| `gfs_tax_income_pct` |  | numeric | sí |  |
| `gfs_spend_defense_pct` |  | numeric | sí |  |
| `gfs_spend_health_pct` |  | numeric | sí |  |
| `gfs_spend_education_pct` |  | numeric | sí |  |
| `gfs_spend_social_pct` |  | numeric | sí |  |
| `edgar_co2_energy_mt` |  | numeric | sí |  |
| `edgar_co2_industry_mt` |  | numeric | sí |  |
| `edgar_ch4_mt` |  | numeric | sí |  |
| `edgar_n2o_mt` |  | numeric | sí |  |
| `is_forecast` |  | boolean | sí |  |
| `primary_energy_twh` | Energía primaria consumida (TWh). | numeric | sí |  |
| `electricity_twh` | Electricidad generada (TWh). | numeric | sí |  |
| `renewables_elec_twh` | Electricidad renovable (TWh). | numeric | sí |  |
| `renewables_share_elec_pct` | % de la electricidad que es renovable. | numeric | sí |  |
| `exports_usd_bn` | Exportaciones de bienes (miles de millones USD). | numeric | sí |  |
| `imports_usd_bn` | Importaciones de bienes (miles de millones USD). | numeric | sí |  |
| `trade_balance_usd_bn` | Balanza comercial (exportaciones − importaciones). | numeric | sí |  |

#### `gold.mart_crypto_overview` · materializada · ~246 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `symbol` | Símbolo o código corto. | character varying(20) | sí |  |
| `name` | Nombre. | character varying(200) | sí |  |
| `category` | Categoría o dominio. | character varying(50) | sí |  |
| `market_cap_rank` |  | smallint | sí |  |
| `last_date` | Fecha del último dato disponible. | date | sí |  |
| `last_price` |  | numeric(24,10) | sí |  |
| `last_volume` |  | numeric(18,2) | sí |  |
| `last_mcap` |  | numeric(18,2) | sí |  |
| `return_30d_pct` |  | numeric | sí |  |
| `return_1y_pct` |  | numeric | sí |  |

#### `gold.mart_earnings_surprise` · materializada · ~182,045 filas
Sorpresas de beneficios: lo que los analistas esperaban vs lo que reportó la empresa, con el porcentaje de sorpresa.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `company_id` | Empresa a la que pertenece. | integer | sí |  |
| `ticker` | Símbolo bursátil (p.ej. AAPL). | character varying(20) | sí |  |
| `year` | Año. | smallint | sí |  |
| `announcement_date` |  | date | sí |  |
| `eps_estimate` |  | numeric(12,4) | sí |  |
| `reported_eps` |  | numeric(12,4) | sí |  |
| `surprise` |  | numeric | sí |  |
| `surprise_pct` |  | numeric(10,4) | sí |  |

#### `gold.mart_etf_category` · materializada · ~104 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `asset_class` |  | character varying(50) | sí |  |
| `geography` |  | character varying(100) | sí |  |
| `strategy` |  | character varying(100) | sí |  |
| `n_funds` |  | bigint | sí |  |
| `avg_nav` |  | numeric | sí |  |
| `avg_return_1y_pct` |  | numeric | sí |  |
| `total_nav_points` |  | numeric | sí |  |

#### `gold.mart_pool_membership` · vista · ~0 filas
Universo S&P 500 point-in-time expandido a días de cotización.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `index_id` | Índice de mercado. | integer | sí |  |
| `company_id` | Empresa a la que pertenece. | integer | sí |  |
| `date` | Fecha del dato. | date | sí |  |

#### `gold.mart_sector_country` · materializada · ~250 filas
Cuántas empresas hay de cada sector en cada país, cuántas están activas y su capitalización media. Muestra dónde se concentra cada industria.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `sector_name` |  | character varying(200) | sí |  |
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | sí |  |
| `country_name` |  | character varying(200) | sí |  |
| `region` |  | character varying(100) | sí |  |
| `n_companies` |  | bigint | sí |  |
| `n_active` |  | bigint | sí |  |
| `avg_market_cap` |  | numeric | sí |  |

#### `gold.mart_sovereign_risk` · materializada · ~40,539 filas
Riesgo soberano: combina el rating crediticio del país, su deuda, balance fiscal y volatilidad del PIB en los últimos 5 años.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | sí |  |
| `year` | Año. | smallint | sí |  |
| `gdp_growth_pct` |  | numeric | sí |  |
| `inflation_pct` |  | numeric | sí |  |
| `unemployment_pct` |  | numeric | sí |  |
| `gov_debt_pct_gdp` |  | numeric | sí |  |
| `gov_balance_pct_gdp` |  | numeric | sí |  |
| `current_account_pct_gdp` |  | numeric | sí |  |
| `reserves_total_usd_bn` |  | numeric | sí |  |
| `reserves_months_imports` |  | numeric | sí |  |
| `rating_agency` |  | character varying(20) | sí |  |
| `sovereign_rating` |  | character varying(10) | sí |  |
| `rating_outlook` |  | character varying(20) | sí |  |
| `gdp_vol_5y` |  | numeric | sí |  |

#### `gold.mart_trade_dependency` · materializada · ~2,638 filas
Dependencia comercial: quiénes son los 3 socios principales de cada país, cuánto concentra en ellos y con cuántos países comercia.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `reporter_code` | País que declara (exporta/importa). | character varying(3) | sí |  |
| `year` | Año. | smallint | sí |  |
| `top1_partner` |  | text | sí |  |
| `top1_trade_k` |  | numeric | sí |  |
| `top2_partner` |  | text | sí |  |
| `top3_partner` |  | text | sí |  |
| `top3_concentration_pct` |  | numeric | sí |  |
| `n_partners` |  | bigint | sí |  |

#### `gold.mart_trade_matrix` · materializada · ~442,027 filas
Matriz de comercio: exportaciones e importaciones entre cada par de países.

| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `reporter_code` | País que declara (exporta/importa). | character varying(3) | sí |  |
| `partner_code` | País socio comercial. | character varying(3) | sí |  |
| `year` | Año. | smallint | sí |  |
| `exports_usd_k` | Exportaciones del reporter al socio (miles de USD). | numeric(20,3) | sí |  |
| `imports_usd_k` | Importaciones del reporter desde el socio (miles de USD). | numeric(20,3) | sí |  |

#### `gold.mart_volatility_regime` · materializada · ~56,904 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `code` | Código identificador. | character varying(20) | sí |  |
| `index_name` |  | character varying(200) | sí |  |
| `date` | Fecha del dato. | date | sí |  |
| `value` | Valor del dato. | numeric(10,4) | sí |  |
| `sma_20` |  | numeric | sí |  |
| `sma_60` |  | numeric | sí |  |
| `std_60d` |  | numeric | sí |  |
| `regime` |  | text | sí |  |

#### `gold.mart_yield_curve` · materializada · ~16,142 filas
| Columna | Qué es | Tipo | Nulo | Clave |
|---|---|---|---|---|
| `country_code` | País (código ISO-3, p.ej. ESP). | character varying(3) | sí |  |
| `date` | Fecha del dato. | date | sí |  |
| `yield_3m` |  | numeric | sí |  |
| `yield_2y` |  | numeric | sí |  |
| `yield_5y` |  | numeric | sí |  |
| `yield_10y` |  | numeric | sí |  |
| `yield_30y` |  | numeric | sí |  |
| `spread_10y_2y` |  | numeric | sí |  |
| `spread_10y_3m` |  | numeric | sí |  |
| `invertida_10y_2y` |  | boolean | sí |  |
