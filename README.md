# Stonks — Base de Datos Global de Inversión

Base de datos PostgreSQL con información económica y financiera
mundial para toma de decisiones de inversión.

## Dominios

| Schema | Contenido |
|--------|-----------|
| `macro` | PIB, inflación, desempleo, tipos de interés |
| `equity` | Empresas cotizadas, precios, fundamentales |
| `fi` | Renta fija, curvas de tipos, ratings |
| `commodity` | Materias primas, futuros |
| `forex` | Tipos de cambio |
| `crypto` | Criptomonedas |
| `fund` | ETFs y fondos de inversión |
| `realestate` | Índices inmobiliarios, REITs |
| `alt` | ESG, sentimiento, insider trading |
| `calendar` | Calendario económico |
| `country` | Perfiles de país, fiscalidad |

## Instalación

```bash
cd /home/marc/Projects/db-projects/stonks
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Uso

```bash
# Crear BD y tablas
createdb stonks_db
stonks init

# Ver estado
stonks status

# Descargar datos macro (World Bank)
stonks macro fetch --source world_bank

# Descargar precios equity (yfinance)
stonks equity fetch --ticker AAPL
```

## Fuentes de datos

- **World Bank API** — Indicadores macroeconómicos globales
- **IMF Data** — Tipos de interés, deuda pública
- **yfinance** — Precios de acciones, ETFs, commodities
- **ECB** — Tipos de cambio, datos eurozona
- **CoinGecko** — Criptomonedas
