# Changelog

Todos los cambios relevantes del proyecto se documentan aqui.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el versionado [Semantic Versioning](https://semver.org/lang/es/).

## [0.4.0] - 2026-08-03

### Añadido
- **Expansión total de activos del mundo**:
  - Forex: 55→102 pares (majors, minors, crosses, exóticos)
  - Commodities: 25→33 (8 futuros CME/CBOT más)
  - ETFs: 100→496 (CSV `config/etf_universe.csv`,
    loader con fallback inline)
  - Crypto: 96→253 coins (seed script `scripts/seed_crypto.py`,
    16 categorías)
- **Derivados** (schema `deriv`):
  - 4 modelos nuevos: `VolatilityIndex`, `VolatilityDaily`,
    `FuturesContract`, `FuturesDaily`
  - 12 índices de volatilidad (VIX, VVIX, VXN, RVX, OVX,
    GVZ, EVZ, VIX9D, VIX3M, VIX6M, SKEW, VX=F)
  - 16 contratos de futuros (equity 5, fixed income 4,
    currency 7) — fetchers `volatility.py`, `index_futures.py`
- **Intraday multi-dominio** (tablas particionadas RANGE):
  - `crypto.price_intraday`, `forex.rate_intraday`,
    `commodity.price_intraday` (PK compuesta, PARTITION BY ts)
  - Fetcher genérico `intraday_multi.py` con DOMAIN_CONFIG
  - `partitions.py` expandido a 4 dominios
- **CLI v0.4.0**:
  - `stonks deriv` (vol-fetch, futures-fetch, list)
  - `stonks intraday` (fetch, cleanup, partitions)
  - Intraday: `--domain`, `--interval`, `--top N`, `--tickers`
- **Pipeline daily expandido**: 8 steps (antes 3) —
  volatility, index-futures, intraday 1h (crypto/forex/commodity)
- **Scheduling**: `intraday_update.sh` (1m/5m),
  `intraday_crypto.sh` (weekend), `config/crontab.txt`
- **Gold layer**: 4 nuevas MVs —
  `mart_volatility_regime` (VIX regímenes + SMA/std),
  `mart_crypto_overview` (top coins + retornos 30d/1y),
  `mart_etf_category` (rendimiento ETF por clase/geo),
  `mart_yield_curve` (curva actual vs 1 año)
- **Tests**: `test_intraday.py` (7 tests),
  `test_models_import.py` ampliado (intraday + deriv),
  `test_pipeline.py` ampliado (daily steps),
  `test_cli.py` ampliado (deriv + intraday help)

### Cambiado
- `daily_update.sh`: +forex-yf, crypto-yf, volatilidad,
  futuros, intraday 1h, pipeline daily
- `weekly_update.sh`: +pipeline weekly, cleanup intraday,
  crear particiones
- `funds.py`: CSV loader con fallback inline
- Pipeline daily: 3→8 steps; weekly sin cambios

## [0.3.0] - 2026-08-02

### Añadido
- **Cobertura máxima de activos con histórico completo**:
  - Crypto: 30→96 coins, OHLCV via yfinance (BTC desde 2014),
    nuevo fetcher `crypto_yfinance.py`, market dominance
  - Forex: 30→55 pares (EUR + 25 USD/crosses via yfinance),
    OHLC completo, nuevo fetcher `yfinance_forex.py`
  - Commodities: +zinc, iron ore, aluminio; re-fetch `period=max`
    (155K pts, muchos desde 1997)
  - Funds: 25→100 (90 ETFs + 10 mutual funds, 507K NAVs)
  - Equity: backfill de precios para ~7.500 empresas sin datos,
    TSX (Canada) añadido al universo, exchange_id mapeado
- **FK fixes**: `crypto.price_daily.coin_id` y
  `meta.fetch_run.source_id` ahora con FOREIGN KEY real
- **HsProduct** movido de `trade.py` a `ref.py` (schema correcto)
- **Pipeline ampliado**: crypto_yfinance, yfinance_forex,
  commodities y funds integrados; retry simple (1 reintento, 5s)
- **ratios_mv** refrescado en `build_gold()`
- **Tests**: conftest.py compartido, test_fetcher_base.py (7 tests),
  test_cli.py (5 smoke tests), test_models_import.py (2 tests);
  fix pytestmark bug en test_macro_indicators.py
- **Documentación**: SCHEMA_RELATIONS.md con omisiones FK,
  .env.example completo, sources.yml limpio (sin alpha_vantage)
- Email personal eliminado de config.py

### Cambiado
- CoinGecko habilitado en sources.yml
- yfinance domains ampliados (+crypto)
- sec_edgar domains corregidos (equity+bronze)
- README: métricas actualizadas (~22M filas, 10.500 empresas)

## [Unreleased]

### Añadido
- **Arquitectura medallion** (bronze/silver/gold): esquemas `bronze`
  (aterrizaje crudo JSONB) y `gold` (analítica point-in-time), capa
  `transform/` (`BaseTransform` + `meta.transform_run`), orquestador
  `pipeline.py` con cadencias (`stonks update -c ...`) y `gold/build.py`
  idempotente.
- **Sin sesgo de supervivencia**: constituyentes históricos del S&P 500
  y empresas deslistadas en `gold.index_membership`.
- **Fundamentales point-in-time** (SEC EDGAR) en `gold.fact_fundamentals_pit`.
- **Factores** Value/Quality/Momentum sector-neutral y replayables en
  `gold.fact_factor_scores` (historial mensual 2011→hoy).
- **Sector GICS** en `equity.company` + tablas de analistas.
- **Economía mundial**: `macro` ampliado (IMF DataMapper, World Bank),
  `trade` (comercio bilateral WITS, 1988→2023) y `energy` (OWID, por
  fuente); emisiones CO2/GHG; panel `gold.mart_country_year`, matriz
  `gold.mart_trade_matrix` y catálogo `gold.dim_indicator`.
- Comandos CLI `world`, `indicators`, `update`; checks `meta.data_quality`.
- README definitivo con la estructura completa de la BD.
- **Profundidad máxima por activo**:
  - Fundamentales US point-in-time con **todos los conceptos XBRL**
    (~9.500 métricas, 12,8M hechos) en `gold.fact_fundamentals_pit`.
  - Ficha **360°** de empresa: `equity.holder`, `insider_transaction`,
    `upgrade_downgrade`, `recommendation_trend`, `shares_history`,
    `earnings_date`, perfil completo en `bronze.yf_profile`.
  - Macro completo: **World Bank WDI (~1.500 indicadores)**; índices de
    bonos/spreads e inmobiliario (FRED).
  - **Agricultura** (`agri.production`, FAOSTAT) y **opciones**
    (`deriv.option_snapshot`, snapshots diarios).
  - Comando CLI `asset <ticker>` (ficha 360°) y matriz de cobertura.

### Cambiado
- `pyproject.toml`: `pytest` en dependencias dev; CI ejecuta la suite.
- `config.py`: `sec_contact_email`.

### Eliminado
- `models/agri.py` y esquema `agri` (sin uso).
- Scripts `seed_*.py` redundantes con `stonks init` (`seed/reference.py`).

## [0.2.0] - 2026-04-23

### Añadido
- **Renta fija completa**:
  - `fi.bond_issuer`: 53 emisores soberanos (G20+)
  - `fi.bond`: 5,015 bonos US Treasury (Fiscal Data API)
  - `fi.credit_rating`: 10,563 ratings Fitch Sovereign
  - Comandos CLI: `stonks fi seed|bonds|ratings`
- **Histórico ampliado** (vía FRED `--start-date`):
  - `fi.yield_curve`: desde 1962 (antes 2000)
  - `macro.data_point`: series expandidas desde 1960
  - `alt.sentiment_value`: desde 1960
- **Actualización masiva equity**:
  - `scripts/update_all_equity.py`: actualiza las ~2,000 empresas
    fuera del YAML con `period=max`
  - `equity.price_daily`: 2.9M → 8.5M filas (1962-2026)
- Documento `docs/SCHEMA_RELATIONS.md` actualizado:
  - 45 FKs (antes 20)
  - Cobertura histórica por schema
  - Nuevas queries de ejemplo

### Cambiado
- `daily_update.sh`: incluye pasos FI (`fi bonds`, `fi ratings`)
- `FredFetcher.fetch_all()` acepta `start_date` configurable
- `CoinGeckoFetcher`: soporte para demo API key, rate limit reducido

## [0.1.0] - 2026-04-21

### Añadido
- Commit inicial
- Esquema PostgreSQL con 11 schemas y 40 tablas
- Modelos SQLAlchemy 2.0+ para todos los dominios
- Fetchers para 7 fuentes: World Bank, IMF, FRED, yfinance, ECB,
  CoinGecko, SEC EDGAR, OECD
- CLI Typer con comandos por dominio
- Datos de referencia: 249 países, 178 monedas, 35 bolsas, 36 sectores
- Documentación inicial (README, SCHEMA_RELATIONS.md)

[Unreleased]: https://github.com/kaizen-mcv/stonks_db/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/kaizen-mcv/stonks_db/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/kaizen-mcv/stonks_db/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/kaizen-mcv/stonks_db/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/kaizen-mcv/stonks_db/releases/tag/v0.1.0
