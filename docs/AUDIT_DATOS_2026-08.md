# Auditoría de datos — stonks_db (2026-08-06)

Segunda auditoría del proyecto. La primera (`AUDIT_2026-08.md`) miró la
**estructura**: esquema, claves foráneas, índices, migraciones. Esta
mira el **contenido**: ¿son ciertos los datos, están las tablas llenas?

---

## 1. Lo que está bien

Conviene decirlo antes que los defectos, porque delimita qué se puede
usar con confianza.

**Los datos macro son reales.** Verificado contra la realidad:

| Comprobación | Base de datos | Realidad |
|---|---|---|
| PIB nominal EE. UU. 2023 | 27,81 billones | 27,72 billones |
| PIB PPP India 2023 | 14,17 billones | ~14,2 billones |
| PIB PPP China 2023 | 35,55 billones | ~35,5 billones |
| Bitcoin 2023-01-01 | 16.625 | 16.625 |
| Bitcoin 2023-12-31 | 42.265 | 42.265 |
| Bitcoin 2024-12-31 | 93.429 | 93.429 |

**Las fuentes concuerdan entre sí.** Contrastando World Bank contra
FMI en PIB per cápita de 2022 sobre **190 países**: desvío medio del
**3,57 %**, y solo 22 países (12 %) discrepan más del 10 %. Es
exactamente lo esperable entre dos organismos con metodologías
distintas, y es la prueba más directa de que los datos no están
inventados.

**La frescura es excelente.** Todos los dominios entre 0 y 2 días de
retraso. El COT a 8 días es correcto: se publica los viernes con tres
días de desfase.

---

## 2. El defecto de raíz: precios mal etiquetados

`src/stonks/fetchers/yfinance_.py` llamaba a `t.history(period=...)`
y a `yf.download(...)` **sin pasar `auto_adjust`**. En yfinance 1.3 ese
parámetro vale `True` por defecto, con tres consecuencias encadenadas:

1. La columna `close` no contenía el cierre real sino el **ajustado
   por splits y dividendos**. AAPL cerró a 192,53 el 2023-12-29 y la
   base decía 190,55.
2. La columna `adj_close` estaba **vacía en las 24.089.385 filas**
   (100 %), porque con `auto_adjust=True` yfinance ya no devuelve
   "Adj Close".
3. El ajuste retroactivo, aplicado a valores con dividendos acumulados
   grandes respecto al precio, generaba **precios negativos**: 22.166
   filas en 19 empresas, con un mínimo de **−246.247**.

De ahí salían en cascada 10.672 filas con `high < low` (al invertirse
el signo se invierte el orden) y 13.635 con `close` fuera de
`[low, high]`.

Un solo parámetro omitido explicaba casi todos los defectos de precio.

**Corrección**: `auto_adjust=False` en las dos rutas del fetcher, y
recarga completa de las 7.817 empresas con precios. Cada columna pasa
a significar lo que dice su nombre.

---

## 3. Precisión insuficiente

`equity.price_daily` usaba `NUMERIC(14,4)`. Las acciones sub-céntimo
(HCMC, MMEX y GTCH cotizan a 0,0001 $) se truncaban a `0.0000`:
**29.443 filas a cero** en 48 empresas. En crypto pasaba lo mismo con
`NUMERIC(18,8)`: BABYDOGE tenía la serie entera a cero.

**Corrección**: `NUMERIC(20,10)` en las 42 columnas de precio de once
tablas. Diez decimales dan cuatro o cinco cifras significativas a un
precio de 1e-6.

Detalle de implementación que importa: PostgreSQL reescribe la tabla
entera cada vez que cambia la escala de una columna numérica. Poner
las cinco columnas de `equity.price_daily` en un único `ALTER TABLE`
en vez de cinco separados evitó cuatro reescrituras de 4 GB. La
migración completa tardó **1 minuto y 45 segundos**.

---

## 4. Etiquetas de unidad que mentían

`GDP_NOMINAL` declaraba `billion_usd` con valores en dólares
absolutos: mediana de 8,2e9. Quien confiara en la etiqueta se
equivocaba por un factor de mil millones. Igual `GDP_PPP` con
`billion_intl_usd`.

Comprobado que los indicadores del FMI **sí** son correctos y no se
tocaron: `IMF_NGDPD` en "Billions of U.S. dollars" tiene mediana 37, e
`IMF_GDP` en "Millions of US Dollars" tiene mediana 17.000.

Se corrigió la etiqueta, no el dato: los valores en dólares absolutos
son los que devuelve el World Bank, los que consume
`gold.mart_country_year.gdp_usd` y los que se verificaron correctos.
Reescalar 18.723 observaciones habría roto la capa gold.

Además había **32 etiquetas distintas** para un puñado de conceptos
("percent", "Percent" y "%" convivían). Se normalizaron los sinónimos
inequívocos a **18**, dejando intactas las que llevan información
propia (la base de un índice, o la diferencia entre `Mt` y `t`).

**Causa raíz corregida**: `seed_indicators()` solo insertaba, nunca
actualizaba. Cambiar `config/indicators.yml` no tenía ningún efecto
sobre la base, así que el fichero y la BD podían divergir en silencio.
Por eso la unidad falsa sobrevivió tanto tiempo.

Los 1.670 indicadores sin unidad (91 % del catálogo) se quedan sin
unidad: inventársela sería peor. Los reporta el check de completitud.

---

## 5. Series que empalmaban dos activos distintos

Cuatro `coin_id` de crypto contenían dos monedas: un bloque antiguo de
valores minúsculos y, tras un hueco de meses o años, el bloque real.

| Símbolo | Bloque ajeno | Real (verificado en CoinGecko) |
|---|---|---|
| COMP | 2018-08 a 2022-01, máx 0,0033 | 15,19 – 55,38 |
| APT | 2021-11 a 2025-06, máx 0,299 | 0,55 – 5,45 |
| SUI | 2022-03 a 2024-06, máx 0,019 | 0,68 – 4,01 |
| GTC | 2026-01-27, 0,000003 | 0,066 – 0,449 |

Además de la diferencia de magnitud (de 4.789 a 17 millones de veces),
los bloques ajenos son **anteriores al lanzamiento de cada moneda**:
Compound salió en junio de 2020, Aptos en octubre de 2022, Gitcoin en
mayo de 2021 y Sui en mayo de 2023.

Este defecto lo introdujo la propia auditoría estructural al fusionar
`crypto.coin` por símbolo: unió dos monedas **y sus dos series de
precios**.

**Corrección**: purga de las 2.971 filas ajenas y recarga desde
CoinGecko. Las cuatro cuadran ahora exactamente con la fuente.

**Causa raíz corregida**: `coingecko.py` hacía `if exists: continue`,
así que un dato mal cargado se quedaba para siempre. Ahora es un
upsert real y relanzar el fetcher corrige.

---

## 6. Tres tablas vacías por un bug de una línea

`commodity.price_intraday`, `crypto.price_intraday` y
`forex.rate_intraday` estaban a **cero filas**. La primera lectura fue
que los fetchers nunca se habían ejecutado. Era falso: se habían
ejecutado **doce veces y habían fallado las doce**, siempre con el
mismo error:

```
no partition of relation "price_intraday" found for row
DETAIL: Partition key of the failing row contains (ts) = (null)
```

La causa: `batch_download` hace `reset_index()` por lote, y yfinance
nombra ese índice `Date` en diario y `Datetime` en intradía. Al
concatenar lotes heterogéneos, pandas creaba **ambas** columnas y
rellenaba con `NaT` la que faltaba. `row.get("Datetime", row.get("Date"))`
devolvía el `NaT` en lugar de caer al valor por defecto, porque la
clave existía.

Agravante: el upsert iba en chunks de 10.000 dentro de una única
transacción, así que un solo `ts` malo tiraba el lote entero. Por eso
había **cero** filas y no "algunas".

**Corrección**: normalizar el nombre del índice a `ts` en un único
punto (`batch.py`), descartar las filas sin marca de tiempo contándolas,
y aislar cada chunk en su propio `SAVEPOINT`.

**Resultado**: 5.513.881 filas recuperadas.

| Tabla | Antes | Ahora |
|---|---|---|
| crypto.price_intraday | 0 | 3.639.658 |
| forex.rate_intraday | 0 | 1.587.441 |
| commodity.price_intraday | 0 | 286.782 |

`equity.price_intraday` funcionaba por casualidad, porque sus lotes
salían homogéneos. Era la misma bomba de relojería.

---

## 7. Otras tablas vacías

- **`alt.housing_index` y `alt.housing_index_value`**: 0 filas y sin
  fetcher. Duplicaban `realestate.price_index*`, que sí tiene datos
  (85 índices de 41 países). Retiradas.
- **`country.profile`**: 40 países de 250, porque el fetcher usaba una
  lista fija de 40 códigos. Ahora recorre el catálogo entero de
  `ref.country`.
- **68 indicadores** de 1.835 sin ningún dato, y **15.998 series** de
  272.274 con `point_count = 0` (5,9 %). Restos de indicadores
  declarados que la fuente ya no publica; los reporta el check de
  indicadores fantasma.

---

## 8. Por qué nada de esto saltó solo

`src/stonks/quality.py` tenía ocho funciones de check, pero:

- `stonks audit` ejecutaba **solo tres de las ocho** y **no persistía
  nada**.
- `check_world_quality()` daba **100 % gratis** a equity, fi,
  commodity, forex y gold_pit, porque usaba `target = cnt`.
- `check_outliers()` **sí detectaba** `close <= 0`, pero solo lo
  contaba en un log.
- No existía **ni una sola constraint CHECK** en toda la base.
- `docs/FRESHNESS_SLA.md` era prosa: nada comparaba `freshness_days`
  contra esos umbrales.
- Había **2.428 ejecuciones fallidas** en 90 días que no aparecían en
  ningún sitio, incluidas las 12 del intraday.

---

## 9. Lo que vigila el sistema a partir de ahora

Nuevo módulo `src/stonks/quality_datos.py` con siete checks, colgados
de `run_all_checks()` y por tanto de cada `build_gold()`:

| Check | Qué detecta |
|---|---|
| `check_ohlc_coherente` | Precios negativos, `high < low`, cierre fuera de rango |
| `check_unidades` | Etiquetas que no cuadran con la magnitud observada |
| `check_coherencia_fuentes` | Divergencia entre World Bank y FMI |
| `check_empalme_series` | Series que unen dos activos distintos |
| `check_frescura_sla` | Retraso real contra el SLA, ahora en código |
| `check_fallos_fetch` | Fetchers que fallan de forma sistemática |
| `check_tablas_vacias` | Tablas de hechos por debajo de su mínimo |

`stonks audit` reescrito: ejecuta **los ocho checks más los siete
nuevos**, persiste en `meta.data_quality` y acepta `--dominio`,
`--detalle` y `--estricto` (este último sale con código 1 si hay
hallazgos, para poder meterlo en el cron).

Y `tests/test_integridad_datos.py` con diez invariantes contra la base
viva, hermano del `test_integridad_esquema.py` que ya vigilaba la
estructura.

---

## 10. Estado y pendientes

**Terminado**: precisión, unidades, empalmes de crypto, bug de
intraday, tablas vacías, maquinaria de calidad y tests.

**En curso**: la recarga de precios de las 7.817 empresas con
`auto_adjust=False`. Es la operación larga (varias horas) y hasta que
termine conviven las dos semánticas: cada empresa está entera en un
régimen o en el otro, nunca a medias, porque el upsert reemplaza la
fila completa.

**Pendiente, después de la recarga**:

1. Purgar las filas OHLC que sigan siendo imposibles.
2. Añadir las constraints CHECK (`close > 0`, `high >= low`,
   `close BETWEEN low AND high`) con `NOT VALID` primero y
   `VALIDATE` después, para no mantener un `ACCESS EXCLUSIVE` largo
   sobre 24 millones de filas.
3. Reconstruir la capa gold.

**Deuda conocida que no se aborda aquí**:

- 1.670 indicadores (91 %) sin unidad declarada.
- 3.164 empresas (29 %) sin ningún precio, 8.552 (78 %) sin
  capitalización.
- `crypto.price_daily` no tiene `source_id`: no hay trazabilidad de
  qué fuente escribió cada fila.
- Tiingo sigue sin clave, así que la segunda fuente de precios no
  está operativa y no hay validación cruzada de cotizaciones.
