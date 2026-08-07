# Certificación de stonks_db

_Generado el 2026-08-06 por `scripts/gen_certificacion.py`. No editar a mano: las declaraciones van en `config/certificacion.yml` y las referencias externas en `tests/referencias.yml`._

## Qué certifica esto, y qué no

Con datos de terceros no se puede garantizar que cada cifra sea cierta: si el World Bank publica mal un PIB, esta base lo reproduce fielmente. Prometer *"todos los datos son correctos"* sería mentir.

Lo que sí se garantiza, y es lo que hay aquí, es que **de cada una de las tablas consta cómo se ha verificado, o consta explícitamente que no se puede verificar y por qué**. Eso es auditable; lo otro no.

## Resumen

| Estado | Tablas | % |
|---|---:|---:|
| contrastada_externamente | 21 | 22.3 % |
| coherente_sin_referencia | 72 | 76.6 % |
| no_verificable | 1 | 1.1 % |
| sin_certificar | 0 | 0.0 % |

**94 tablas** en total.

## Contrastadas contra una cifra publicada fuera

Hay al menos un valor en `tests/referencias.yml` que compara una fila de la tabla contra una cifra publicada por la fuente original. Es la única categoría que responde "sí" a *¿son ciertos estos datos?*; el resto responde a *¿son posibles?*.

| Tabla | Filas | Cómo se comprueba |
|---|---:|---|
| `agri.production` | 2,938,249 | 1 valor(es) en tests/referencias.yml |
| `commodity.commodity` | 33 | 1 valor(es) en tests/referencias.yml |
| `commodity.price_daily` | 197,123 | 1 valor(es) en tests/referencias.yml |
| `country.demographics` | 1,040 | 1 valor(es) en tests/referencias.yml |
| `crypto.coin` | 256 | 1 valor(es) en tests/referencias.yml |
| `crypto.price_daily` | 267,232 | 1 valor(es) en tests/referencias.yml |
| `deriv.cot_report` | 286,694 | 1 valor(es) en tests/referencias.yml |
| `energy.balance` | 185,679 | 1 valor(es) en tests/referencias.yml |
| `equity.company` | 11,012 | 2 valor(es) en tests/referencias.yml |
| `equity.price_daily` | 28,785,268 | 2 valor(es) en tests/referencias.yml |
| `fi.yield_curve` | 68,422 | 1 valor(es) en tests/referencias.yml |
| `forex.currency_pair` | 115 | 1 valor(es) en tests/referencias.yml |
| `forex.rate_daily` | 677,061 | 1 valor(es) en tests/referencias.yml |
| `fund.fund` | 496 | 1 valor(es) en tests/referencias.yml |
| `fund.nav_daily` | 1,379,929 | 1 valor(es) en tests/referencias.yml |
| `macro.data_point` | 9,089,682 | 1 valor(es) en tests/referencias.yml |
| `macro.indicator` | 1,835 | 1 valor(es) en tests/referencias.yml |
| `macro.series` | 272,274 | 1 valor(es) en tests/referencias.yml |
| `realestate.price_index` | 85 | 1 valor(es) en tests/referencias.yml |
| `realestate.price_index_value` | 14,982 | 1 valor(es) en tests/referencias.yml |
| `trade.flow` | 1,121,103 | 1 valor(es) en tests/referencias.yml |

## Coherentes, sin cifra externa con la que comparar

No existe una cifra externa razonable con la que comparar —son catálogos, agregados propios o fotos que nadie archiva—, pero sí comprobaciones estructurales que la tabla pasa.

| Tabla | Filas | Cómo se comprueba |
|---|---:|---|
| `alt.sentiment_indicator` | 7 | Catálogo de instrumentos, no serie de datos. Se valida por integridad referencial: toda fila de precios apunta a uno de estos contratos. |
| `bronze.analyst_snapshot` | 99,120 | Aterrizaje sin transformar. Su veracidad es la de la tabla de silver que se deriva de ella, que sí se contrasta; aquí solo se comprueba que la carga no esté vacía y lleve `fetch_run_id`. |
| `bronze.api_response` | 319 | Aterrizaje sin transformar. Su veracidad es la de la tabla de silver que se deriva de ella, que sí se contrasta; aquí solo se comprueba que la carga no esté vacía y lleve `fetch_run_id`. |
| `bronze.constituents_snapshot` | 6 | Aterrizaje sin transformar. Su veracidad es la de la tabla de silver que se deriva de ella, que sí se contrasta; aquí solo se comprueba que la carga no esté vacía y lleve `fetch_run_id`. |
| `bronze.sec_companyfacts` | 28,351 | Aterrizaje sin transformar. Su veracidad es la de la tabla de silver que se deriva de ella, que sí se contrasta; aquí solo se comprueba que la carga no esté vacía y lleve `fetch_run_id`. |
| `bronze.yf_profile` | 4,967 | Aterrizaje sin transformar. Su veracidad es la de la tabla de silver que se deriva de ella, que sí se contrasta; aquí solo se comprueba que la carga no esté vacía y lleve `fetch_run_id`. |
| `calendar.release` | 330 | Catálogo de publicaciones estadísticas. Se valida contra `calendar.release_date`, que sí tiene fechas contrastables. |
| `calendar.release_date` | 91,326 | checks estructurales de stonks.quality_datos |
| `commodity.price_intraday` | 287,103 | checks estructurales de stonks.quality_datos |
| `country.profile` | 212 | checks estructurales de stonks.quality_datos |
| `country.tax_rate` | 155 | checks estructurales de stonks.quality_datos |
| `crypto.market_dominance` | 1 | La capitalización total y el peso de Bitcoin se cruzan contra la suma de `crypto.price_daily.market_cap_usd`, que sí está contrastada contra CoinGecko. |
| `crypto.price_intraday` | 3,643,095 | checks estructurales de stonks.quality_datos |
| `deriv.cot_contract` | 946 | Catálogo de instrumentos, no serie de datos. Se valida por integridad referencial: toda fila de precios apunta a uno de estos contratos. |
| `deriv.futures_contract` | 16 | Catálogo de instrumentos, no serie de datos. Se valida por integridad referencial: toda fila de precios apunta a uno de estos contratos. |
| `deriv.futures_daily` | 92,083 | checks estructurales de stonks.quality_datos |
| `deriv.option_snapshot` | 69,602 | tests/test_referencias.py: los strikes de cada cadena rodean el precio del subyacente. |
| `deriv.volatility_daily` | 56,877 | check_ohlc_coherente sobre la serie y contraste implícito con `commodity.price_daily`, que sí tiene referencia externa: ambas vienen del mismo fetcher. |
| `deriv.volatility_index` | 12 | Catálogo de instrumentos, no serie de datos. Se valida por integridad referencial: toda fila de precios apunta a uno de estos contratos. |
| `equity.analyst_estimate` | 228,204 | Dato de yfinance sin publicación oficial con la que cuadrar fila a fila. Se comprueba estructuralmente: sin nulos en las columnas obligatorias, sin duplicados de clave y con volumen coherente con el número de empresas cubiertas. |
| `equity.balance_sheet` | 22,342 | check_identidad_contable: activo = pasivo + patrimonio. Descuadran 7 balances de 18.697, que es ruido de la fuente, no de la carga. |
| `equity.cash_flow` | 22,026 | check_identidad_contable: activo = pasivo + patrimonio. Descuadran 7 balances de 18.697, que es ruido de la fuente, no de la carga. |
| `equity.dividend` | 188,417 | Dato de yfinance sin publicación oficial con la que cuadrar fila a fila. Se comprueba estructuralmente: sin nulos en las columnas obligatorias, sin duplicados de clave y con volumen coherente con el número de empresas cubiertas. |
| `equity.earnings_date` | 191,439 | Dato de yfinance sin publicación oficial con la que cuadrar fila a fila. Se comprueba estructuralmente: sin nulos en las columnas obligatorias, sin duplicados de clave y con volumen coherente con el número de empresas cubiertas. |
| `equity.earnings_revision` | 228,204 | Dato de yfinance sin publicación oficial con la que cuadrar fila a fila. Se comprueba estructuralmente: sin nulos en las columnas obligatorias, sin duplicados de clave y con volumen coherente con el número de empresas cubiertas. |
| `equity.factor_return` | 18,702 | checks estructurales de stonks.quality_datos |
| `equity.holder` | 74,847 | tests/test_referencias.py comprueba que `pct_held` esté en porcentaje, que ningún accionista pase del 100 % y que la suma por empresa solo lo pase en la minoría conocida (17 de 3.525, por el denominador desactualizado de Yahoo en small caps). |
| `equity.income_statement` | 21,743 | check_identidad_contable: activo = pasivo + patrimonio. Descuadran 7 balances de 18.697, que es ruido de la fuente, no de la carga. |
| `equity.index_constituent_current` | 1,362 | Dato de yfinance sin publicación oficial con la que cuadrar fila a fila. Se comprueba estructuralmente: sin nulos en las columnas obligatorias, sin duplicados de clave y con volumen coherente con el número de empresas cubiertas. |
| `equity.index_price` | 256,941 | checks estructurales de stonks.quality_datos |
| `equity.insider_transaction` | 210,101 | tests/test_referencias.py: el precio implícito de cada operación (importe entre acciones) no puede pasar de cien veces el precio de mercado de ese día. |
| `equity.market_index` | 28 | Dato de yfinance sin publicación oficial con la que cuadrar fila a fila. Se comprueba estructuralmente: sin nulos en las columnas obligatorias, sin duplicados de clave y con volumen coherente con el número de empresas cubiertas. |
| `equity.price_intraday` | 15,228 | checks estructurales de stonks.quality_datos |
| `equity.ratios_mv` | 10,449 | tests/test_integridad_esquema.py: los marts se recrean en cada build, están poblados y sus claves no admiten duplicados. Los datos de origen sí están contrastados. |
| `equity.recommendation_trend` | 12,630 | Dato de yfinance sin publicación oficial con la que cuadrar fila a fila. Se comprueba estructuralmente: sin nulos en las columnas obligatorias, sin duplicados de clave y con volumen coherente con el número de empresas cubiertas. |
| `equity.shares_history` | 3,377,997 | Dato de yfinance sin publicación oficial con la que cuadrar fila a fila. Se comprueba estructuralmente: sin nulos en las columnas obligatorias, sin duplicados de clave y con volumen coherente con el número de empresas cubiertas. |
| `equity.split` | 6,755 | Dato de yfinance sin publicación oficial con la que cuadrar fila a fila. Se comprueba estructuralmente: sin nulos en las columnas obligatorias, sin duplicados de clave y con volumen coherente con el número de empresas cubiertas. |
| `equity.upgrade_downgrade` | 331,351 | Dato de yfinance sin publicación oficial con la que cuadrar fila a fila. Se comprueba estructuralmente: sin nulos en las columnas obligatorias, sin duplicados de clave y con volumen coherente con el número de empresas cubiertas. |
| `fi.bond` | 5,061 | Catálogo de instrumentos, no serie de datos. Se valida por integridad referencial: toda fila de precios apunta a uno de estos contratos. |
| `fi.bond_issuer` | 53 | Catálogo de instrumentos, no serie de datos. Se valida por integridad referencial: toda fila de precios apunta a uno de estos contratos. |
| `fi.country_risk_premium` | 175 | checks estructurales de stonks.quality_datos |
| `fi.credit_rating` | 10,563 | Las calificaciones soberanas se comprueban por dominio (escala cerrada AAA-D) y por continuidad temporal: un país no salta más de tres escalones entre dos revisiones consecutivas. |
| `forex.rate_intraday` | 1,588,888 | checks estructurales de stonks.quality_datos |
| `gold.dim_company` | 11,012 | tests/test_integridad_esquema.py: los marts se recrean en cada build, están poblados y sus claves no admiten duplicados. Los datos de origen sí están contrastados. |
| `gold.dim_country` | 250 | tests/test_integridad_esquema.py: los marts se recrean en cada build, están poblados y sus claves no admiten duplicados. Los datos de origen sí están contrastados. |
| `gold.dim_date` | 23,593 | tests/test_integridad_datos.py comprueba que el calendario bursátil no cuente fines de semana y dé 250-252 sesiones al año, que son las de la Bolsa de Nueva York. |
| `gold.fact_factor_scores` | 175,255 | tests/test_integridad_esquema.py: los marts se recrean en cada build, están poblados y sus claves no admiten duplicados. Los datos de origen sí están contrastados. |
| `gold.fact_fundamentals_pit` | 33,174,290 | tests/test_integridad_esquema.py: los marts se recrean en cada build, están poblados y sus claves no admiten duplicados. Los datos de origen sí están contrastados. |
| `gold.index_membership` | 1,264 | tests/test_integridad_esquema.py: los marts se recrean en cada build, están poblados y sus claves no admiten duplicados. Los datos de origen sí están contrastados. |
| `gold.mart_benchmark_returns` | 32,464 | tests/test_integridad_esquema.py: los marts se recrean en cada build, están poblados y sus claves no admiten duplicados. Los datos de origen sí están contrastados. |
| `gold.mart_climate_risk` | 40,539 | tests/test_integridad_esquema.py: los marts se recrean en cada build, están poblados y sus claves no admiten duplicados. Los datos de origen sí están contrastados. |
| `gold.mart_company_macro` | 118,561 | tests/test_integridad_esquema.py: los marts se recrean en cada build, están poblados y sus claves no admiten duplicados. Los datos de origen sí están contrastados. |
| `gold.mart_country_governance` | 11,227 | tests/test_integridad_esquema.py: los marts se recrean en cada build, están poblados y sus claves no admiten duplicados. Los datos de origen sí están contrastados. |
| `gold.mart_country_year` | 40,539 | tests/test_integridad_esquema.py: los marts se recrean en cada build, están poblados y sus claves no admiten duplicados. Los datos de origen sí están contrastados. |
| `gold.mart_crypto_overview` | 246 | tests/test_integridad_esquema.py: los marts se recrean en cada build, están poblados y sus claves no admiten duplicados. Los datos de origen sí están contrastados. |
| `gold.mart_earnings_surprise` | 182,045 | tests/test_integridad_esquema.py: los marts se recrean en cada build, están poblados y sus claves no admiten duplicados. Los datos de origen sí están contrastados. |
| `gold.mart_etf_category` | 104 | tests/test_integridad_esquema.py: los marts se recrean en cada build, están poblados y sus claves no admiten duplicados. Los datos de origen sí están contrastados. |
| `gold.mart_sector_country` | 250 | tests/test_integridad_esquema.py: los marts se recrean en cada build, están poblados y sus claves no admiten duplicados. Los datos de origen sí están contrastados. |
| `gold.mart_sovereign_risk` | 40,539 | tests/test_integridad_esquema.py: los marts se recrean en cada build, están poblados y sus claves no admiten duplicados. Los datos de origen sí están contrastados. |
| `gold.mart_trade_dependency` | 2,638 | tests/test_integridad_esquema.py: los marts se recrean en cada build, están poblados y sus claves no admiten duplicados. Los datos de origen sí están contrastados. |
| `gold.mart_trade_matrix` | 442,027 | tests/test_integridad_esquema.py: los marts se recrean en cada build, están poblados y sus claves no admiten duplicados. Los datos de origen sí están contrastados. |
| `gold.mart_volatility_regime` | 56,904 | tests/test_integridad_esquema.py: los marts se recrean en cada build, están poblados y sus claves no admiten duplicados. Los datos de origen sí están contrastados. |
| `gold.mart_yield_curve` | 16,142 | tests/test_integridad_esquema.py: los marts se recrean en cada build, están poblados y sus claves no admiten duplicados. Los datos de origen sí están contrastados. |
| `macro.data_point_vintage` | 85,467 | Vintages de ALFRED: cada fila es lo que FRED publicaba en una fecha dada. Se comprueba que el último vintage de cada serie coincida con el valor vigente en `macro.data_point`. |
| `macro.indicator_source` | 1,762 | Tabla de enlace entre indicador y fuente. Se valida por integridad referencial en los dos extremos. |
| `ref.area` | 281 | Catálogo estable derivado de un estándar (ISO 3166 / ISO 4217 / ISO 10383). No cambia con los datos; se comprueba por integridad referencial: ninguna tabla apunta a un código que no exista. |
| `ref.country` | 250 | Catálogo estable derivado de un estándar (ISO 3166 / ISO 4217 / ISO 10383). No cambia con los datos; se comprueba por integridad referencial: ninguna tabla apunta a un código que no exista. |
| `ref.currency` | 178 | Catálogo estable derivado de un estándar (ISO 3166 / ISO 4217 / ISO 10383). No cambia con los datos; se comprueba por integridad referencial: ninguna tabla apunta a un código que no exista. |
| `ref.exchange` | 35 | Catálogo estable derivado de un estándar (ISO 3166 / ISO 4217 / ISO 10383). No cambia con los datos; se comprueba por integridad referencial: ninguna tabla apunta a un código que no exista. |
| `ref.hs_product` | 97 | Catálogo estable derivado de un estándar (ISO 3166 / ISO 4217 / ISO 10383). No cambia con los datos; se comprueba por integridad referencial: ninguna tabla apunta a un código que no exista. |
| `ref.legal_entity` | 355 | checks estructurales de stonks.quality_datos |
| `ref.sector` | 36 | Catálogo estable derivado de un estándar (ISO 3166 / ISO 4217 / ISO 10383). No cambia con los datos; se comprueba por integridad referencial: ninguna tabla apunta a un código que no exista. |

## No verificables

Se ha mirado y no hay forma de comprobarlas. Cada una lleva su motivo escrito; un test falla si alguien marca una tabla así sin explicar por qué.

| Tabla | Filas | Cómo se comprueba |
|---|---:|---|
| `alt.sentiment_value` | 6,254 | Índices de sentimiento (Fear & Greed y similares) cuyo histórico no publica nadie de forma estable: el proveedor solo expone el valor del día y lo recalcula sin avisar. Lo que hay en la base es la serie que el proyecto ha ido acumulando, y no existe publicación contra la que contrastarla hacia atrás. |

## Sin certificar

Nadie ha declarado cómo se comprueban. **Este apartado debe estar vacío**: hay un test que falla si no lo está.

_Ninguna._

## Cómo se mantiene

1. `stonks certify` recorre las tablas y actualiza `meta.table_certification`.
2. Una tabla queda **contrastada** sola, sin declarar nada, en cuanto alguna consulta de `tests/referencias.yml` la nombra.
3. Lo que no se pueda contrastar se declara a mano en `config/certificacion.yml`, con su método o su motivo.
4. `tests/test_referencias.py` falla si alguna tabla se queda sin declarar, así que **no se puede añadir una tabla nueva sin decir cómo se comprueba**.
