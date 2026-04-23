# Arquitectura

Este documento explica el diseno interno de `stonks_db` y como
extenderlo. Para el esquema de BD ver
[SCHEMA_RELATIONS.md](SCHEMA_RELATIONS.md).

## Principios de diseno

1. **Separacion de responsabilidades** por capas:
   `CLI → Fetchers → Models → PostgreSQL`
2. **Un fetcher por fuente externa** (FRED, yfinance, ECB, etc.)
3. **Estado incremental** en `data/state/*.json` para descargas
   resumibles sin reprocesar
4. **Auditoria completa** en `meta.fetch_run` (cada ejecucion queda
   registrada con metricas y errores)
5. **Schemas por dominio** para que la BD sea navegable
6. **Codigo simple**, sin sobreingenieria — si un script resuelve
   el problema, no hace falta una clase

## Capas

### CLI (Typer + Rich)

Entry point en `src/stonks/cli.py`. Usa sub-apps por dominio:

```python
macro_app = typer.Typer(help="Datos macroeconomicos")
equity_app = typer.Typer(help="Renta variable")
fi_app = typer.Typer(help="Renta fija")
# ...
app.add_typer(macro_app, name="macro")
app.add_typer(equity_app, name="equity")
```

Cada comando CLI delega en un fetcher:

```python
@fi_app.command("bonds")
def fi_bonds() -> None:
    from stonks.fetchers.bonds import BondFetcher
    fetcher = BondFetcher()
    stats = fetcher.fetch_us_bonds()
```

### Configuracion (Pydantic Settings)

`src/stonks/config.py` carga variables desde `.env` con prefijo
`STONKS_`. Ejemplo:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_prefix="STONKS_",
    )
    db_url: str = "postgresql+psycopg://..."
    fred_api_key: str = ""
```

### BaseFetcher

Todas las clases de descarga heredan de `BaseFetcher`
(`src/stonks/fetchers/base.py`). Proporciona:

- `_rate_limit()`: respeta `RATE_LIMIT` (segundos entre requests)
- `_get(url, params)`: GET con reintentos exponenciales
- `_start_run(params)` / `_finish_run(...)`: auditoria via
  `meta.fetch_run`
- `_load_state(key)` / `_save_state(key, data)`: JSON en
  `data/state/` para descargas incrementales

Ejemplo minimo:

```python
from stonks.fetchers.base import BaseFetcher


class MiFetcher(BaseFetcher):
    SOURCE_NAME = "mi_fuente"
    DOMAIN = "macro"
    RATE_LIMIT = 1.0  # 1 req/s

    def fetch_data(self) -> dict[str, int]:
        run_id = self._start_run(params={"type": "full"})
        stats = {"fetched": 0, "inserted": 0,
                 "updated": 0, "errors": 0}
        try:
            # ... logica de descarga
            self._finish_run(run_id, "success", **stats)
        except Exception as e:
            self._finish_run(
                run_id, "failed", **stats,
                error_log={"msg": str(e)}
            )
        return stats
```

### Models (SQLAlchemy 2.0)

Un modulo por schema en `src/stonks/models/`:

- `macro.py`: Indicator, IndicatorSource, Series, DataPoint
- `equity.py`: Company, DailyPrice, IncomeStatement, BalanceSheet...
- `fixed_income.py`: BondIssuer, Bond, CreditRating, YieldCurve
- `commodity.py`: Commodity, CommodityPrice
- `forex.py`: CurrencyPair, ForexRate
- `crypto.py`: Coin, CryptoPrice, MarketDominance
- `fund.py`: Fund, FundNav
- `alternative.py`: SentimentIndicator, SentimentValue, HousingIndex
- `country.py`: CountryProfile, Demographics, TaxRate
- `meta.py`: DataSource, FetchRun
- `ref.py`: Country, Currency, Exchange, Sector

Estilo moderno con `Mapped` y `mapped_column`:

```python
class Bond(Base):
    __tablename__ = "bond"
    __table_args__ = {"schema": "fi"}

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )
    issuer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("fi.bond_issuer.id")
    )
    isin: Mapped[str | None] = mapped_column(
        String(12), unique=True
    )
    # ...
```

## Flujo de datos tipico

```
 1. Usuario ejecuta: stonks macro fetch --source fred
 2. CLI (cli.py) importa FredFetcher
 3. FredFetcher._start_run(): crea fila en meta.fetch_run
 4. Por cada serie de FRED_SERIES:
    a. _rate_limit()  (espera si necesario)
    b. _get(url)      (GET con reintentos)
    c. Inserta en macro.data_point
 5. FredFetcher._finish_run(status="success", ...)
 6. _save_state("fred_all", {"last_fetch": "..."})
```

## Como anadir una nueva fuente de datos

Pasos para integrar, por ejemplo, una API de bonos corporativos:

### 1. Crear el fetcher

`src/stonks/fetchers/corporate_bonds.py`:

```python
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.fixed_income import Bond


class CorporateBondsFetcher(BaseFetcher):
    SOURCE_NAME = "sec_edgar"  # o el nombre de la fuente
    DOMAIN = "fi"
    RATE_LIMIT = 0.5

    def fetch_bonds(self) -> dict[str, int]:
        run_id = self._start_run(params={...})
        stats = {...}
        try:
            # Logica de descarga
            self._finish_run(run_id, "success", **stats)
        except Exception as e:
            self._finish_run(run_id, "failed", ...)
        return stats
```

### 2. Registrar la fuente en `meta.data_source`

En `scripts/seed_sources.py` o insertando directamente:

```python
session.add(DataSource(
    name="sec_edgar",
    base_url="https://data.sec.gov",
    rate_limit_rps=0.5,
    enabled=True,
))
```

### 3. Anadir comando CLI

En `src/stonks/cli.py`:

```python
@fi_app.command("corporate-bonds")
def fi_corporate_bonds() -> None:
    """Descargar bonos corporativos."""
    from stonks.fetchers.corporate_bonds import (
        CorporateBondsFetcher,
    )
    fetcher = CorporateBondsFetcher()
    stats = fetcher.fetch_bonds()
    console.print(
        f"Insertados: {stats['inserted']}"
    )
```

### 4. (Opcional) Anadir al cron diario

En `scripts/daily_update.sh`:

```bash
echo "Corporate bonds..." >> "$LOG"
stonks fi corporate-bonds >> "$LOG" 2>&1 || true
```

### 5. Documentar

- Anadir seccion en README (tabla de fuentes)
- Entry en `CHANGELOG.md`

## Convenciones del esquema de BD

- **Schemas por dominio** (macro, equity, fi, ...) para
  navegacion clara
- **FKs a `meta.data_source.id`** en tablas de datos para
  auditoria (saber de que fuente vino cada fila)
- **country_code**: siempre ISO 3166-1 alpha-3 (USA, DEU, JPN)
- **currency_code**: siempre ISO 4217 (USD, EUR, GBP)
- **Constraint unicos** por (entidad, fecha) en series temporales
  para permitir ON CONFLICT DO NOTHING en importaciones
- **Fechas en UTC**, columnas `date` para dias, `timestamp` para
  eventos

## Estado incremental

Los fetchers que soportan actualizaciones incrementales usan
`_load_state()` / `_save_state()`:

```python
state = self._load_state("us_bonds")
last = state.get("last_auction_date", "2000-01-01")

# ... descargar filtrado por last

self._save_state("us_bonds", {
    "last_auction_date": new_max_date
})
```

Los archivos JSON viven en `data/state/` (gitignored). Permiten:

- Reanudar descargas grandes si el proceso se mata
- Actualizar diariamente sin re-descargar todo
- Debuggear (mirando el JSON sabes donde quedo)

## Logging

Centralizado en `src/stonks/logger.py`. Cada run del CLI crea un
archivo diario en `data/logs/stonks_fetch_YYYYMMDD.log`.

Librerias externas (requests, urllib3, httpx) se silencian a nivel
WARNING para no contaminar los logs.

Nunca usar `print()` para debug — siempre `logger.info()` /
`logger.warning()` / `logger.error()`.
