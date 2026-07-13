# stonks_db

Base de datos PostgreSQL que reúne, con **fuentes oficiales gratuitas**,
los **mercados financieros globales** y la **economía mundial** en un
único modelo medallion (bronze → silver → gold), listo para análisis
cuantitativo.

- **~13 millones de filas**, **~200 países**, histórico profundo
  (mercados desde 1927, macro desde 1960, energía desde 1900, CO2 desde
  1750, comercio desde 1988).
- **Point-in-time** donde importa: fundamentales con fecha de publicación
  (SEC EDGAR), universo S&P 500 sin sesgo de supervivencia y factores
  replayables para backtests honestos.
- **Medallion**: aterrizaje crudo auditado (`bronze`), dominios
  normalizados (`silver`) y capa analítica lista para leer (`gold`).

---

## Índice

- [Características](#características)
- [Arquitectura](#arquitectura)
- [Estructura de la base de datos](#estructura-de-la-base-de-datos)
- [Fuentes de datos](#fuentes-de-datos)
- [Instalación](#instalación)
- [Uso](#uso)
- [Actualización (cron)](#actualización-cron)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Tests](#tests)
- [Limitaciones conocidas](#limitaciones-conocidas)

---

## Características

- **Mercados financieros**: ~3.000 empresas (incl. deslistadas), precios
  diarios (9,3M), fundamentales, dividendos, índices, renta fija,
  commodities, forex, crypto, ETFs y sentimiento.
- **Economía mundial**: ~200 países con PIB, precios, empleo, fiscal,
  cuentas externas, energía por fuente, comercio bilateral y emisiones.
- **Sin sesgo de supervivencia**: constituyentes históricos del S&P 500
  (point-in-time) y empresas deslistadas en `gold.index_membership`.
- **Fundamentales point-in-time** reales (SEC EDGAR, fecha de `filed`).
- **Factores** Value/Quality/Momentum sector-neutral, replayables en
  cualquier fecha pasada (`gold.fact_factor_scores`).
- **Panel país-año** cross-dominio (`gold.mart_country_year`) y **matriz
  de comercio bilateral** (`gold.mart_trade_matrix`).
- Medallion idempotente y **auditado** (`meta.fetch_run`,
  `meta.transform_run`) con checks de calidad (`meta.data_quality`).
- Stack: **Python 3.11+**, **PostgreSQL 16**, SQLAlchemy 2.0, Typer, Pydantic.

---

## Arquitectura

```
┌─────────────────────────────────────────────┐
│               CLI (Typer + Rich)             │
│   init · status · world · indicators · update │
└───────────────────────┬──────────────────────┘
                        │
┌───────────────────────▼──────────────────────┐
│        Pipeline por cadencia (pipeline.py)    │
│        daily · weekly · monthly · yearly      │
└──────────┬─────────────────────────┬──────────┘
           ▼                         ▼
┌────────────────────┐    ┌────────────────────┐
│  Fetchers          │    │  Transforms         │
│  fuente → bronze/   │    │  bronze → silver/   │
│  silver (BaseFetcher)│   │  gold (BaseTransform)│
└──────────┬─────────┘    └─────────┬──────────┘
           │                        │
┌──────────▼────────────────────────▼──────────┐
│   bronze  →  silver (dominios)  →  gold        │
│   (JSONB     (ref, equity, macro,   (PIT,      │
│    crudo)     trade, energy...)      marts)    │
└───────────────────────┬───────────────────────┘
                        ▼
                  PostgreSQL 16
```

- **bronze**: respuestas crudas (JSONB, append-only) de las fuentes
  nuevas. Permite re-derivar sin volver a descargar.
- **silver**: dominios normalizados con claves foráneas. La clave
  universal es `country_code` (ISO-3) / `ticker`.
- **gold**: dimensiones, hechos point-in-time y *marts* listos para leer.
  Se reconstruye de forma idempotente con `build_gold()`.

Cada paso del pipeline se aísla (un fallo no detiene el resto), es
**idempotente** (`INSERT … ON CONFLICT DO UPDATE`) y queda **auditado**.
Ver [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Estructura de la base de datos

18 esquemas. Cifras aproximadas.

### Referencia y metadatos
| Esquema | Tablas | Contenido |
|---|---|---|
| `ref` | country, currency, exchange, sector | Países (249), divisas, bolsas, sectores GICS |
| `meta` | data_source, fetch_run, transform_run, data_quality | Fuentes y **auditoría** de descargas/transformaciones |

### Mercados financieros (silver) — ~9,7M filas
| Esquema | Tablas principales | Filas |
|---|---|---|
| `equity` | company, price_daily, income_statement, balance_sheet, cash_flow, dividend, split, market_index, index_price, analyst_estimate, earnings_revision, index_constituent_current, ratios_mv | **~9,7M** (precios 9,3M) |
| `fi` | bond, bond_issuer, credit_rating, yield_curve | ~84K |
| `commodity` | commodity, price_daily | ~105K |
| `forex` | currency_pair, rate_daily | ~183K |
| `crypto` | coin, price_daily, market_dominance | ~12K |
| `fund` | fund, nav_daily | ~132K |
| `alt` | sentiment_indicator, sentiment_value, housing_index* | ~6K |

### Economía mundial (silver)
| Esquema | Tablas | Filas |
|---|---|---|
| `macro` | indicator, indicator_source, series, data_point | **~885K** (país × indicador × año) |
| `trade` | flow | **~973K** (comercio bilateral, 1988→2023) |
| `energy` | balance | ~186K (país × fuente × flujo, TWh) |
| `country` | profile, demographics, tax_rate | ~1K |

### Medallion
| Esquema | Tablas / vistas | Papel |
|---|---|---|
| `bronze` | api_response, sec_companyfacts, constituents_snapshot, analyst_snapshot | Aterrizaje crudo JSONB |
| `gold` | dim_date, dim_company, dim_country, index_membership, fact_fundamentals_pit, fact_factor_scores, mart_benchmark_returns, **mart_country_year**, mart_trade_matrix, dim_indicator (vista) | Analítica point-in-time y *marts* |

**Tablas gold clave para analizar:**
- `gold.mart_country_year` — panel ancho **país × año** (~25 métricas:
  PIB nominal/PPP/pc/crecimiento, inflación, paro, deuda, saldo/ingreso/
  gasto público, ahorro, inversión, cuenta corriente, CO2/GHG, energía
  primaria/eléctrica/renovable, exportaciones/importaciones y balance).
- `gold.mart_trade_matrix` — matriz bilateral reporter × partner × año.
- `gold.fact_fundamentals_pit` — fundamentales US con fecha de publicación.
- `gold.fact_factor_scores` — factores sector-neutral, historial mensual.
- `gold.index_membership` — universo S&P 500 point-in-time.
- `gold.dim_indicator` (vista) — **catálogo autodocumentado** de indicadores.

Diagrama ER completo en
[docs/SCHEMA_RELATIONS.md](docs/SCHEMA_RELATIONS.md).

---

## Fuentes de datos

Todas **gratuitas y oficiales**:

| Fuente | Dominio | Clave |
|---|---|---|
| Yahoo Finance (yfinance) | Precios, fundamentales, analistas | No |
| SEC EDGAR | Fundamentales US point-in-time | No (User-Agent) |
| FRED | Macro US, yields | Sí (gratis) |
| ECB | Forex, tipos BCE | No |
| US Treasury / Fitch | Bonos, ratings | No |
| Wikipedia + GitHub (fja05680) | Constituyentes S&P 500 históricos | No |
| **IMF DataMapper** | Macro mundial (132 indicadores WEO) | No |
| **World Bank** (WDI) | Indicadores de desarrollo | No |
| **World Bank WITS** | Comercio bilateral | No |
| **Our World in Data** | Energía y emisiones CO2/GHG | No |
| CoinGecko | Crypto | Opcional |

---

## Instalación

```bash
git clone <repo> && cd stonks
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # incluye pytest y ruff

cp .env.example .env             # editar conexión y claves
createdb stonks_db
stonks init                      # crea esquemas, tablas y datos ref.
```

Configuración vía `STONKS_*` en `.env` (ver `config.py`): `STONKS_DB_URL`,
`STONKS_FRED_API_KEY` (opcional), `STONKS_SEC_CONTACT_EMAIL`.

---

## Uso

```bash
# Estado y exploración
stonks status                    # conteos por tabla
stonks world ESP                 # panel de un país (PIB, CO2, comercio...)
stonks world CHN -n 10
stonks indicators -s inflation   # catálogo de indicadores macro
stonks indicators -c fiscal

# Pipeline medallion por cadencia (idempotente, reconstruye gold)
stonks update -c daily           # foto diaria de analistas
stonks update -c weekly          # sectores, constituyentes, SEC PIT
stonks update -c monthly         # factores
stonks update -c yearly          # economía mundial: IMF, comercio, energía
stonks update -c all --dry-run   # ver los pasos sin ejecutar

# Ingesta por dominio (fuentes de mercados)
stonks equity fetch --batch global --period max
stonks macro fetch --source fred
stonks forex fetch --full
stonks fi bonds && stonks fi ratings
```

Ejemplo de consulta cross-dominio (la clave `country_code` une todo):

```sql
SELECT year, gdp_usd_bn, co2_mt, exports_usd_bn, renewables_share_elec_pct
FROM gold.mart_country_year
WHERE country_code = 'DEU' AND year BETWEEN 2015 AND 2023;
```

---

## Actualización (cron)

Dos vías complementarias:

- **Scripts por dominio** (mercados): `scripts/daily_update.sh`,
  `scripts/weekly_update.sh` (refresca también `equity.ratios_mv`).
- **Pipeline medallion**: `stonks update -c <cadencia>`.

```cron
0  22 * * 1-5  /ruta/stonks/scripts/daily_update.sh
0  23 * * 0    /ruta/stonks/scripts/weekly_update.sh
30 22 * * *    cd /ruta/stonks && .venv/bin/stonks update -c daily
0  1  * * 1    cd /ruta/stonks && .venv/bin/stonks update -c weekly
0  2  1 * *    cd /ruta/stonks && .venv/bin/stonks update -c monthly
0  3  1 1 *    cd /ruta/stonks && .venv/bin/stonks update -c yearly
```

---

## Estructura del proyecto

```
stonks/
├── src/stonks/
│   ├── cli.py              # CLI Typer (init, status, world, indicators, update)
│   ├── config.py          # Settings Pydantic
│   ├── db.py              # Engine, esquemas, init_db
│   ├── pipeline.py        # Orquestador por cadencia
│   ├── quality.py         # Checks de calidad → meta.data_quality
│   ├── fetchers/          # Fuente → bronze/silver (heredan BaseFetcher)
│   ├── transform/         # bronze → silver/gold (heredan BaseTransform)
│   ├── gold/build.py      # Reconstrucción idempotente de gold
│   ├── models/            # ORM SQLAlchemy, 1 módulo por esquema
│   └── seed/reference.py  # seed_all (países, divisas, bolsas, sectores...)
├── scripts/               # Utilidades: build_universe, cron, ratios_mv
├── config/                # sources.yml, indicators.yml, companies.yml
├── docs/                  # ARCHITECTURE.md, SCHEMA_RELATIONS.md
└── tests/                 # pytest
```

---

## Tests

```bash
pytest                     # 28 tests (lógica pura + BD si está disponible)
ruff check . && ruff format --check .
```

Los tests de BD se **omiten** automáticamente si no hay conexión, así que
la suite corre también en CI sin PostgreSQL.

---

## Limitaciones conocidas

Todas derivadas de usar solo fuentes gratuitas:

- **Frecuencia macro**: la economía real es **anual** (los mercados son
  diarios). No hay macro mensual/trimestral.
- **Sin vintages macro**: guardamos la última versión de cada dato
  (el crudo original queda en `bronze`); no es point-in-time como los
  fundamentales de equity.
- **Fundamentales PIT solo US** (SEC EDGAR); el resto usa la foto de
  yfinance.
- **Comercio a nivel producto 'Total'** (matriz país×país); el detalle
  por producto HS y FAOSTAT/WHO detallados quedan como extensión futura.
- **Deslistadas antiguas sin precios**: ~198/563 tienen histórico en
  yfinance; el resto (quiebras/absorciones antiguas) no es recuperable
  gratis.
