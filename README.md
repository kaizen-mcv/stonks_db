# stonks_db

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-336791.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![CI](https://github.com/kaizen-mcv/stonks_db/actions/workflows/ci.yml/badge.svg)](https://github.com/kaizen-mcv/stonks_db/actions/workflows/ci.yml)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

Base de datos PostgreSQL global de inversion con **~9.7M filas** de
datos historicos desde **1927**. Cubre macroeconomia, equity, renta
fija, commodities, forex, crypto, fondos, perfiles de pais y datos
alternativos. Orientada a analisis cuantitativo y toma de decisiones.

> **Stack:** Python 3.11+, PostgreSQL 14+, SQLAlchemy 2.0,
> Typer, Pydantic.

---

## Tabla de contenidos

- [Caracteristicas](#caracteristicas)
- [Arquitectura](#arquitectura)
- [Requisitos](#requisitos)
- [Instalacion](#instalacion)
- [Uso rapido](#uso-rapido)
- [Schemas y datos](#schemas-y-datos)
- [Fuentes de datos](#fuentes-de-datos)
- [Actualizacion diaria](#actualizacion-diaria)
- [Documentacion](#documentacion)
- [Contribuir](#contribuir)
- [Licencia](#licencia)

---

## Caracteristicas

- **11 schemas** / **40 tablas** / **45 foreign keys**
- **~9.7M filas** de datos historicos reales
- Cobertura historica profunda:
  - Indices desde **1927** (Dow Jones)
  - Equity y yields desde **1962**
  - Macro (FRED) desde **1960**
  - Bonos US Treasury desde **1980**
  - ETFs desde **1993**
  - Forex desde **1999**
- **15+ fetchers** modulares para fuentes gratuitas
- CLI intuitiva con Typer + Rich
- Estado incremental para actualizaciones diarias resumibles
- Auditoria completa via `meta.fetch_run`

---

## Arquitectura

```
┌─────────────────────────────────────────┐
│            CLI (Typer + Rich)           │
│    stonks init | status | fetch ...     │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│        Fetchers (src/stonks/fetchers)   │
│  FRED | yfinance | ECB | Treasury | ... │
│  BaseFetcher: rate limit, retries, state│
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│      Models (SQLAlchemy 2.0)            │
│   11 schemas · 40 tablas · 45 FKs       │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│          PostgreSQL 14+                 │
│         stonks_db (~1.7 GB)             │
└─────────────────────────────────────────┘
```

Ver [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) para detalles de
diseno.

---

## Requisitos

- **Python** 3.11 o superior
- **PostgreSQL** 14 o superior
- **Linux/macOS** (probado en Ubuntu 24.04)

---

## Instalacion

```bash
# Clonar el repositorio
git clone git@github.com:kaizen-mcv/stonks_db.git
cd stonks_db

# Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# Instalar el paquete
pip install -e .

# (Opcional) Instalar dependencias de desarrollo
pip install -e ".[dev]"
```

### Configuracion

```bash
# Crear base de datos
createdb stonks_db

# Copiar plantilla y editar
cp .env.example .env
# Editar .env con tu conexion a PostgreSQL y API keys

# Inicializar tablas y datos de referencia
stonks init
```

### API keys (opcionales pero recomendadas)

| Servicio | URL para obtener key | Uso |
|----------|---------------------|-----|
| FRED | https://fred.stlouisfed.org/docs/api/api_key.html | Datos macro US |
| CoinGecko | https://www.coingecko.com/en/api/pricing | Crypto |
| Alpha Vantage | https://www.alphavantage.co/support/#api-key | Backup yfinance |

---

## Uso rapido

```bash
# Ver comandos disponibles
stonks --help

# Ver estado de la BD
stonks status

# Descargar datos macroeconomicos (FRED, desde 1960)
stonks macro fetch --source fred --start-date 1960-01-01

# Descargar precios de una accion (historico completo)
stonks equity fetch --ticker AAPL --period max

# Descargar por batch (SP500 top, Europa o global)
stonks equity fetch --batch global --period max

# Forex historico completo (ECB)
stonks forex fetch --full

# Renta fija: emisores + bonos US + ratings
stonks fi seed
stonks fi bonds
stonks fi ratings

# ETFs, commodities, crypto, indices
stonks fund fetch --period max
stonks commodity fetch --period max
stonks crypto fetch --days 3650
stonks index fetch --period max
```

---

## Schemas y datos

| Schema | Tablas | Filas | Cobertura |
|--------|-------:|------:|-----------|
| `ref` | 4 | 425 | Paises, monedas, bolsas, sectores GICS |
| `meta` | 3 | ~8K | Fuentes, auditoria de ejecuciones |
| `macro` | 4 | ~108K | Indicadores economicos (FRED, World Bank) |
| `equity` | 9 | **~8.9M** | Empresas, precios, fundamentales, dividendos |
| `fi` | 4 | ~84K | Bonos, ratings, curvas de tipos |
| `commodity` | 2 | ~105K | Materias primas |
| `forex` | 2 | ~183K | Tipos de cambio (EUR vs 30+ divisas) |
| `crypto` | 3 | ~11K | Criptomonedas |
| `fund` | 2 | ~132K | ETFs y NAV historico |
| `country` | 3 | ~1K | Perfiles de pais, demografia |
| `alt` | 4 | ~6K | Sentimiento (VIX, consumer sentiment) |
| **Total** | **40** | **~9.7M** | |

Ver [docs/SCHEMA_RELATIONS.md](docs/SCHEMA_RELATIONS.md) para el
diagrama ER completo con todas las relaciones.

---

## Fuentes de datos

Todas las fuentes usadas son **gratuitas**:

| Fuente | Cobertura | API key | Uso |
|--------|-----------|---------|-----|
| **Yahoo Finance** (yfinance) | Acciones, ETFs, commodities, indices | No | Precios historicos |
| **FRED** (Federal Reserve) | Macro US, yields, spreads | Si (gratis) | Series economicas |
| **ECB** (European Central Bank) | Forex desde 1999 | No | Tipos de cambio EUR |
| **World Bank** | Indicadores macro globales | No | PIB, demografia |
| **US Treasury Fiscal Data** | Bonos US Treasury | No | Subastas historicas |
| **CoinGecko** | Criptomonedas | Demo key recomendada | Precios crypto |
| **ratingshistory.info** | Ratings soberanos Fitch | No | Historial de ratings |
| **IMF Data** | Deuda publica, tipos | No | Complemento macro |
| **SEC EDGAR** | Fundamentales US | No | Estados financieros |
| **OECD** | Estadisticas OCDE | No | Datos complementarios |

---

## Actualizacion diaria

Dos scripts en `scripts/`:

- `daily_update.sh`: precios equity, ETFs, forex, crypto, yields,
  bonos FI (~10 min)
- `weekly_update.sh`: fundamentales, datos macro mas lentos

Ejemplo de crontab (ejecuta a las 22:00 UTC, mercados cerrados):

```cron
0 22 * * 1-5 /ruta/a/stonks_db/scripts/daily_update.sh
0 23 * * 0   /ruta/a/stonks_db/scripts/weekly_update.sh
```

---

## Documentacion

| Documento | Descripcion |
|-----------|-------------|
| [README.md](README.md) | Este documento |
| [docs/SCHEMA_RELATIONS.md](docs/SCHEMA_RELATIONS.md) | Diagrama ER + queries de ejemplo |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Diseno interno y como extender |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Como contribuir |
| [CHANGELOG.md](CHANGELOG.md) | Cambios por version |
| [SECURITY.md](SECURITY.md) | Politica de seguridad |

---

## Estructura del proyecto

```
stonks_db/
├── src/stonks/          # Codigo fuente
│   ├── cli.py           # CLI Typer
│   ├── config.py        # Configuracion Pydantic
│   ├── db.py            # SQLAlchemy engine
│   ├── logger.py        # Logging centralizado
│   ├── fetchers/        # 15+ fetchers por fuente
│   └── models/          # Modelos por dominio (11 schemas)
├── config/              # YAMLs: paises, indicadores, sources
├── scripts/             # Seed scripts, update diario/semanal
├── docs/                # Documentacion tecnica
├── data/                # (gitignored) logs, downloads, state
├── .github/             # Templates de issues/PRs, CI
├── pyproject.toml       # Metadatos y dependencias
├── .env.example         # Plantilla de configuracion
├── LICENSE              # MIT
├── CHANGELOG.md         # Historial de cambios
├── CONTRIBUTING.md      # Guia de contribucion
├── CODE_OF_CONDUCT.md   # Codigo de conducta
├── SECURITY.md          # Politica de seguridad
└── README.md            # Este archivo
```

---

## Contribuir

Las contribuciones son bienvenidas. Por favor lee
[CONTRIBUTING.md](CONTRIBUTING.md) antes de enviar un PR.

Flujo rapido:

1. Abre una issue describiendo la propuesta
2. Fork + crear rama `feat/nombre` o `fix/nombre`
3. Hacer cambios + `ruff check .` + `ruff format .`
4. Abrir PR siguiendo la plantilla

---

## Licencia

[MIT](LICENSE) © 2026 Marc Villanueva

Los datos descargados de fuentes externas (FRED, yfinance, ECB, etc.)
estan sujetos a los terminos de uso de cada proveedor. Este proyecto
solo proporciona la infraestructura de ETL.
