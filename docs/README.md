# Documentación de stonks_db

Punto de entrada a toda la documentación. `stonks_db` reúne **mercados
financieros** y **economía mundial** en un modelo **medallion**
(bronze → silver → gold) sobre PostgreSQL.

## Documentos

| Documento | Para qué |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | **Cómo funciona por dentro**: capas medallion, fetchers, transforms, pipeline; cómo añadir una fuente. |
| [SCHEMA_RELATIONS.md](SCHEMA_RELATIONS.md) | **Mapa de relaciones**: diagrama ER, esquemas y claves foráneas. |
| [DATA_DICTIONARY.md](DATA_DICTIONARY.md) | **Diccionario de datos**: cada tabla y columna (tipo, nulo, PK/FK, nº de filas). Generado desde el esquema real. |
| [TUTORIALS.md](TUTORIALS.md) | **Tutoriales**: backtests PIT, panel mundial, factores de inversión. |
| [JOIN_PATTERNS.md](JOIN_PATTERNS.md) | **15 patrones de JOIN** entre esquemas con SQL listo para copiar. |
| [FRESHNESS_SLA.md](FRESHNESS_SLA.md) | **SLAs de frescura**: lag esperado de cada dato por cadencia. |
| [CERTIFICACION.md](CERTIFICACION.md) | **¿Son fiables los datos?**: cómo se ha verificado cada tabla, o por qué no se puede. |
| [QUERY_OPTIMIZATION.md](QUERY_OPTIMIZATION.md) | **Rendimiento**: tips para consultar las tablas grandes (31M+ filas). |
| [../README.md](../README.md) | Visión general, instalación, uso y matriz de cobertura. |

---

## Cómo entender la BD en 5 minutos

### 1. Tres capas (medallion)
- **bronze** — respuestas crudas de las APIs (JSONB, tal cual llegan).
  Solo para re-derivar; normalmente no se consulta.
- **silver** — los esquemas de dominio, ya normalizados: `equity`,
  `macro`, `trade`, `fi`, `forex`... **Aquí está el detalle.**
- **gold** — capa lista para analizar: paneles anchos, hechos
  point-in-time y *marts*. **Empieza a mirar aquí.**

### 2. Claves universales (para cruzar dominios)
- **`country_code`** (ISO-3, p.ej. `ESP`) une TODO lo de economía
  mundial: `macro`, `trade`, `energy`, `agri`, `country`.
- **`company_id`** / **`ticker`** unen todo lo de una empresa: precios,
  fundamentales, holders, insiders, opciones...
- **`date`** / **`period`** (año) es el eje temporal.

### 3. Dónde buscar cada cosa

| Quiero... | Mira en... |
|---|---|
| PIB, inflación, paro, deuda... de un país | `gold.mart_country_year` o `stonks world ESP` |
| Comercio entre dos países | `gold.mart_trade_matrix` |
| Un indicador macro concreto (¿qué hay?) | `gold.dim_indicator` o `stonks indicators -s <texto>` |
| Series macro completas | `macro.data_point` (+ `macro.series`, `macro.indicator`) |
| Precio histórico de una acción | `equity.price_daily` |
| Fundamentales point-in-time de una empresa | `gold.fact_fundamentals_pit` |
| Ficha completa de una empresa | `stonks asset AAPL` |
| Accionistas / insiders / recomendaciones | `equity.holder` / `insider_transaction` / `upgrade_downgrade` |
| Factores Value/Quality/Momentum | `gold.fact_factor_scores` |
| Energía por fuente / emisiones | `energy.balance` / `macro` (OWID_CO2) |
| Producción agrícola | `agri.production` |
| Opciones | `deriv.option_snapshot` |

### 4. Explorar desde la CLI
```bash
stonks status                 # conteos por tabla
stonks world CHN              # panel económico de un país
stonks asset MSFT             # ficha 360° de una empresa
stonks indicators -c health   # catálogo de indicadores por categoría
```

### 5. Fiabilidad de los datos
- **De cada tabla consta cómo se ha verificado**, o por qué no se puede:
  [CERTIFICACION.md](CERTIFICACION.md) y `meta.table_certification`. De
  94 tablas, 21 están contrastadas contra una cifra publicada fuera del
  proyecto, 72 pasan comprobaciones estructurales, 1 está declarada no
  verificable y ninguna queda sin declarar.
- Cada descarga y transformación queda **auditada** en `meta.fetch_run` y
  `meta.transform_run`; la cobertura/frescura por dominio en
  `meta.data_quality`. Desde v0.8.0, cada fila lleva además `source_id` y
  `fetch_run_id`.
- Todo es **idempotente**: re-ejecutar no duplica.
- Los **fundamentales** y el **universo S&P 500** son *point-in-time*
  (sin sesgo de supervivencia) para backtests honestos.

Lo que esto **no** promete: que cada cifra sea cierta. Si la fuente
publica mal un dato, la base lo reproduce. Lo que sí promete es que
consta cómo se comprobó cada tabla.

---

## Regenerar el diccionario de datos

Tras cambios de esquema:

```bash
python scripts/gen_data_dictionary.py   # reescribe docs/DATA_DICTIONARY.md
python scripts/gen_certificacion.py     # recertifica y reescribe CERTIFICACION.md
```
