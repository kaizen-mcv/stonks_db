# stonks_db

Base de datos PostgreSQL que reúne, con **fuentes oficiales gratuitas**,
los **mercados financieros globales** y la **economía mundial** en un
único modelo medallion (bronze → silver → gold), listo para análisis
cuantitativo.

- **~22 millones de filas**, **250 países**, histórico profundo
  (mercados desde 1927, macro desde 1950, energía desde 1900, CO2 desde
  1750, comercio desde 1988, BOP desde 1948).
- **Point-in-time** donde importa: fundamentales con fecha de publicación
  (SEC EDGAR), universo S&P 500 sin sesgo de supervivencia y factores
  replayables para backtests honestos.
- **Medallion**: aterrizaje crudo auditado (`bronze`), dominios
  normalizados (`silver`) y capa analítica lista para leer (`gold`).

---

## Índice

- [Documentación](#documentación)
- [Características](#características)
- [Arquitectura](#arquitectura)
- [Estructura de la base de datos](#estructura-de-la-base-de-datos)
- [Fuentes de datos](#fuentes-de-datos)
- [Instalación](#instalación)
- [Uso](#uso)
- [Actualización (cron)](#actualización-cron)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Tests](#tests)
- [Matriz de cobertura](#matriz-de-cobertura)
- [Limitaciones conocidas](#limitaciones-conocidas)

---

## Documentación

Empieza por el **hub de documentación**:
**[docs/README.md](docs/README.md)** — incluye una guía *"cómo entender la
BD en 5 minutos"* (capas, claves universales y dónde buscar cada cosa).

| Documento | Para qué |
|---|---|
| [docs/README.md](docs/README.md) | Índice + guía rápida de comprensión |
| [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md) | **Diccionario de datos**: cada tabla y columna (tipo, PK/FK, filas) |
| [docs/SCHEMA_RELATIONS.md](docs/SCHEMA_RELATIONS.md) | Diagrama ER y relaciones |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Diseño interno (medallion, fetchers, transforms) |

---

## Características

- **Mercados financieros**: ~10.500 empresas (incl. deslistadas), precios
  diarios (11M+), fundamentales, dividendos, índices, renta fija,
  25 commodities, 55 pares forex, 96 crypto, 100 fondos (ETF+MF) y
  sentimiento.
- **Economía mundial**: ~250 países con PIB, precios, empleo, fiscal,
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
| `ref` | country, currency, exchange, sector, hs_product | Países (250), divisas, bolsas, sectores GICS, catálogo HS |
| `meta` | data_source, fetch_run, transform_run, data_quality | Fuentes y **auditoría** de descargas/transformaciones |

### Mercados financieros (silver) — ~12,3M filas
| Esquema | Tablas principales | Filas |
|---|---|---|
| `equity` | company, price_daily, income_statement, balance_sheet, cash_flow, dividend, split, market_index, index_price, analyst_estimate, earnings_revision, index_constituent_current, ratios_mv | **~11M** (precios 11M) |
| `fi` | bond, bond_issuer, credit_rating, yield_curve | ~84K |
| `commodity` | commodity, price_daily | ~155K |
| `forex` | currency_pair, rate_daily | ~335K |
| `crypto` | coin, price_daily, market_dominance | ~222K |
| `fund` | fund, nav_daily | ~507K |
| `alt` | sentiment_indicator, sentiment_value, housing_index* | ~6K |

### Economía mundial (silver)
| Esquema | Tablas | Filas |
|---|---|---|
| `macro` | indicator, indicator_source, series, data_point | **~9,1M** (país × indicador × fecha) |
| `trade` | flow | **~973K** (comercio bilateral, 1988→2023) |
| `energy` | balance | ~186K (país × fuente × flujo, TWh) |
| `country` | profile, demographics, tax_rate | ~1K |

### Medallion
| Esquema | Tablas / vistas | Papel |
|---|---|---|
| `bronze` | api_response, sec_companyfacts, constituents_snapshot, analyst_snapshot | Aterrizaje crudo JSONB |
| `gold` | dim_date, dim_company, dim_country, index_membership, fact_fundamentals_pit, fact_factor_scores, mart_benchmark_returns, **mart_country_year**, mart_trade_matrix, mart_company_macro, mart_sovereign_risk, mart_trade_dependency, mart_earnings_surprise, mart_sector_country, **mart_country_governance**, **mart_climate_risk**, dim_indicator (vista), dim_data_source (vista) | Analítica point-in-time y *marts* (**10 MVs**) |

**Tablas gold clave para analizar:**
- `gold.mart_country_year` — panel ancho **país × año** (~123 métricas:
  PIB, inflación, paro, deuda, fiscal, ahorro, comercio, CO2/GHG, energía,
  salud, desigualdad, educación, infraestructura, I+D, pobreza, governance,
  turismo, migración, FDI, BOP, reservas, remesas, TI CPI, Freedom House,
  demografía, apertura comercial, desarrollo financiero, SIPRI militar,
  HDI, Heritage, ND-GAIN, FSI, **V-Dem democracia, UN DESA demografía,
  WIPO patentes, UNESCO educación, IMF GFS fiscal, EDGAR emisiones**).
- `gold.mart_company_macro` — **empresa + macro del país** (2,3M filas).
- `gold.mart_sovereign_risk` — **rating + deuda + volatilidad GDP**.
- `gold.mart_trade_dependency` — **top socios + concentración comercial**.
- `gold.mart_earnings_surprise` — **EPS estimado vs reportado** (181K).
- `gold.mart_sector_country` — **sector × país** (exposición geográfica).
- `gold.mart_country_governance` — **gobernanza multidimensional**
  (WGI + TI CPI + FH + Heritage + FSI + V-Dem).
- `gold.mart_climate_risk` — **riesgo climático** (ND-GAIN + OWID emisiones +
  EDGAR sectoriales + renovables).
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
| **World Bank** (WDI) | Indicadores de desarrollo (~200 países) | No |
| **World Bank WITS** | Comercio bilateral | No |
| **UN Comtrade** | Comercio por producto HS | Sí (gratis) |
| **IMF IFS** (SDMX 3.0) | Tipos interés, CPI, broad money (190+ países) | No |
| **ECB SDW** | M1/M2/M3, EURIBOR, tipos BCE, lending | No |
| **OECD** (SDMX) | CPI, CLI, confianza, vivienda, productividad, I+D, Gini | No |
| **Eurostat** (JSON-stat) | Macro UE: HICP, paro, IP, PIB, PPI, vivienda, turismo | No |
| **BIS** (SDMX) | Tipos política, crédito/PIB, REER, vivienda, debt service | No |
| **ILOSTAT** (SDMX) | Empleo, paro y participación (~275 áreas) | No |
| **Penn World Table** | TFP, capital humano, horas (185 países, 1950-2023) | No |
| **WHO GHO** | Salud (esperanza vida, mortalidad...) | No |
| **WID.world** | Desigualdad renta/riqueza (desde 1800) | No |
| **FRED/ALFRED** | Macro US + vintages point-in-time | Sí (gratis) |
| **Our World in Data** | Energía y emisiones CO2/GHG | No |
| **Transparency Intl** | Corruption Perceptions Index (180 países, 2012-2024) | No |
| **Freedom House** | Libertad política/civil (190 países, 2002-2023) | No |
| **IMF BOP** (SDMX 3.0) | Balanza de pagos trimestral (9 series, 200 países) | No |
| **SIPRI** | Gasto militar (USD, % PIB, per cápita, 170+ países) | No |
| **UNDP HDR** | HDI, GDI, GII, MPI (190 países, 1990-2023) | No |
| **Heritage Foundation** | Libertad económica (12 sub-índices, 184 países) | No |
| **ND-GAIN** | Vulnerabilidad + readiness climática (192 países) | No |
| **FSI** (Fund for Peace) | Fragile States Index (178 países, 2006-2025) | No |
| **V-Dem** | Democracia: polyarchy, liberal, corrupción (202 países) | No |
| **UN DESA** | Proyecciones demográficas a 2100 (237 países) | No |
| **UNCTAD** | FDI bilateral + Liner Shipping Connectivity | No |
| **WIPO** | Patentes (solicitudes/concesiones, 200+ países) | No |
| **UNESCO UIS** | Educación: alfabetización, años escolarización | No |
| **IMF DOTS** (SDMX 3.0) | Comercio bilateral mensual (exports/imports) | No |
| **IMF GFS** | Finanzas públicas detalladas (gasto por función) | No |
| **EDGAR** (JRC) | Emisiones GHG sectoriales (CO2/CH4/N2O, 1970-2022) | No |
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

Configuración vía `STONKS_*` en `.env` (ver `.env.example`): `STONKS_DB_URL`,
`STONKS_FRED_API_KEY`, `STONKS_COINGECKO_KEY`, `STONKS_COMTRADE_KEY`,
`STONKS_EIA_KEY`, `STONKS_SEC_CONTACT_EMAIL` (todos opcionales).

---

## Uso

```bash
# Estado y exploración
stonks status                    # conteos por tabla
stonks audit                     # auditoría de calidad (fantasmas, cobertura, huecos)
stonks world ESP                 # panel de un país (PIB, CO2, comercio...)
stonks world CHN -n 10
stonks asset AAPL                # ficha 360° de una empresa (profundidad)
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
├── scripts/               # Utilidades: build_universe, cron, gen_data_dictionary
├── config/                # sources.yml, indicators.yml, companies.yml
├── docs/                  # README (hub), ARCHITECTURE, SCHEMA_RELATIONS, DATA_DICTIONARY
└── tests/                 # pytest
```

---

## Tests

```bash
pytest -v                  # ~30 tests (lógica pura + BD si está disponible)
ruff check . && ruff format --check .
```

Los tests de BD se **omiten** automáticamente si no hay conexión, así que
la suite corre también en CI sin PostgreSQL.

---

## Matriz de cobertura

Honesta sobre qué hay con fuentes gratuitas (✅ completo · ⚠️ parcial ·
❌ no viable gratis):

| Área | Estado | Detalle |
|---|---|---|
| Acciones (precios) | ✅ | ~10.500 empresas, histórico 1962+ |
| Fundamentales US | ✅ | **point-in-time, ~9.500 conceptos XBRL** (SEC) |
| Empresa 360° | ✅ | holders, insiders, upgrades, recomendaciones, calendario, shares |
| Fundamentales no-US | ⚠️ | foto yfinance (sin PIT) |
| ETFs / índices | ✅ | 90 ETFs + 10 mutual funds, histórico máximo |
| Bonos | ⚠️ | índices y spreads (FRED); universo corp. ❌ |
| Commodities | ✅ | 25 productos, OHLCV, hist. máximo |
| Forex | ✅ | 55 pares (EUR+USD+crosses), OHLC, desde 1996 |
| Crypto | ✅ | 96 coins, OHLCV yfinance (BTC 2014+) + CoinGecko |
| Opciones | ⚠️ | snapshots diarios (top líquidas); histórico profundo ❌ |
| Inmobiliario | ⚠️ | índices de precios (FRED); transacciones ❌ |
| Macro mundial | ✅ | IMF + **World Bank WDI (~1.500 indicadores)**, 250 países |
| Macro mensual/trimestral | ✅ | CPI/CLI/Gini (OECD), Eurostat (15 series), BIS (7), ECB SDW (11), **IMF IFS** (7), **IMF BOP** (9 series Q, 200 países) |
| Turismo / migración | ✅ | arrivals, receipts, net migration, refugees (World Bank) |
| FDI / BOP desglosado | ✅ | inflows/outflows + goods/services/income (WB anual + IMF Q + **UNCTAD** FDI+LSCI) |
| Gobernanza / libertad | ✅ | WGI + TI CPI + Freedom House + **Heritage** + **FSI** + **V-Dem** |
| Gasto militar | ✅ | **SIPRI** (USD, % PIB, per cápita, 170+ países, 1949-2024) |
| Desarrollo humano | ✅ | **UNDP HDI** + GDI + GII + MPI (190 países, 1990-2023) |
| Riesgo climático | ✅ | **ND-GAIN** (vulnerabilidad + readiness, 192 países) |
| Demografía (proyecciones) | ✅ | **UN DESA** (población, edad mediana, dependencia) |
| Patentes / innovación | ✅ | **WIPO** (solicitudes/concesiones, 200+ países) |
| Emisiones sectoriales | ✅ | **EDGAR** (CO2 energía/industria, CH4, N2O, 1970-2022) |
| Productividad / TFP | ✅ | Penn World Table 11.0 (185 países, 1950-2023) |
| Vintages point-in-time macro | ✅ | 10 series US clave (FRED/ALFRED) |
| Comercio | ✅ | bilateral 1988+ país×país + **por producto HS (Comtrade)** |
| Energía / CO2 | ✅ | por fuente + emisiones (OWID) |
| Agricultura | ✅ | producción por cultivo/ganado (FAOSTAT) |
| Salud | ✅ | esperanza de vida, mortalidad, gasto sanitario (WHO) |
| Trabajo | ✅ | paro y participación (ILOSTAT, ~200-275 áreas) |
| Desigualdad renta/riqueza | ✅ | top 1%/10%, Gini desde 1800 (WID.world) |
| Educación/pobreza | ✅ | WDI + **UNESCO UIS** (alfabetización, años escolarización, ratio alumno/profesor) |
| Comercio bilateral mensual | ✅ | **IMF DOTS** (exports/imports mensuales, 200 países) |
| Finanzas públicas detalladas | ✅ | **IMF GFS** (impuestos + gasto por función: defensa/salud/educación/social) |
| Derivados full, private equity, tick | ❌ | no existen en fuentes gratuitas |

## Limitaciones conocidas

Todas derivadas de usar solo fuentes gratuitas:

- **Macro mensual OECD/UE/eurozona** más detallada; para 190+ países hay
  tipos de interés y CPI mensual (IMF IFS); el resto del mundo tiene
  también la macro anual de IMF + World Bank.
- **Vintages point-in-time solo de 10 series US clave** (FRED/ALFRED);
  para el resto guardamos la última versión (el crudo queda en `bronze`).
- **Fundamentales PIT solo US** (SEC EDGAR); el resto usa la foto de
  yfinance.
- **Comercio por producto a nivel HS2 frente al Mundo** (Comtrade,
  requiere clave gratuita); el bilateral país×país sigue a nivel 'Total'.
- **Cobertura a nivel de organismos internacionales**, no de oficinas
  nacionales de estadística ni datos sub-nacionales (cola infinita).
- **Deslistadas antiguas sin precios**: ~198/563 tienen histórico en
  yfinance; el resto (quiebras/absorciones antiguas) no es recuperable
  gratis.
