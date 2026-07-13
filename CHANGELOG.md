# Changelog

Todos los cambios relevantes del proyecto se documentan aqui.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el versionado [Semantic Versioning](https://semver.org/lang/es/).

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

[Unreleased]: https://github.com/kaizen-mcv/stonks_db/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/kaizen-mcv/stonks_db/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/kaizen-mcv/stonks_db/releases/tag/v0.1.0
