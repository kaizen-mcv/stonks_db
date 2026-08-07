# Changelog

Todos los cambios relevantes del proyecto se documentan aqui.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el versionado [Semantic Versioning](https://semver.org/lang/es/).

## [0.8.1] - 2026-08-07

Tres defectos encontrados desde fuera, construyendo un tablero de BI
sobre la base. Ninguno era del tablero: los tres afectaban a decisiones
de inversión y estaban en el origen.

### Corregido — los ratios mezclaban dos monedas

`equity.income_statement` y sus hermanas guardaban la moneda de
**cotización**, no la de reporte: el fetcher escribía
`currency_code=comp.currency_code`. No son la misma, y la diferencia
rompe cualquier ratio que divida un precio entre una magnitud contable.

- Central Puerto cotiza en dólares y reporta en pesos: PER **0,006**.
- Novo Nordisk reporta en coronas; su ADR daba PER **2,0** frente a
  12,7 en Copenhague, con el mismo beneficio por acción.

Eran 620 PER no comparables de 2.285, y **salen los primeros al ordenar
por PER**: justo donde uno busca gangas.

El dato correcto nunca se perdió —Yahoo lo da en `financialCurrency` y
el perfil entero se guardaba en `bronze.yf_profile`—, así que se
recupera de ahí. `equity.ratios_mv` calcula ahora PER, P/VC, P/V y
rentabilidad del flujo de caja **en dólares**, y deja el ratio a NULL
cuando falta el tipo de cambio de alguna de las dos monedas, con una
columna `moneda_coherente` que lo dice.

Quedan 1.941 PER, todos comparables entre sí, frente a los 2.285 de
antes con 620 que no lo eran. La diferencia son 1.465 empresas cuyo
registro nunca se completó —`name` sigue siendo el ticker porque
`fetch_company_info` no llegó a ejecutarse— y de las que por tanto no
se sabe en qué moneda reportan. Se recuperan ejecutando
`EquityDeepFetcher`, que captura el perfil.

Un intento intermedio de rellenarlas suponiendo el dólar cuando
`country_code = 'USA'` reintrodujo el defecto: a esos registros
incompletos se les había puesto 'USA' por defecto, y entre ellos hay
ADR que reportan en otra moneda (Grupo Aval en pesos colombianos,
Kaspi en tenges, Canon en yenes). Revertido: sin perfil descargado no
hay evidencia, y una unidad supuesta vale menos que ninguna.

### Corregido — el BPA se quedaba congelado

Booking figuraba con un BPA de **165,57** cuando Yahoo ya daba 6,62
tras el split, y de ahí salía un PER de 1,25 en un valor que cotiza a
31 veces beneficios. La causa: `fundamentals.py` hacía
`if exists: continue`, así que un periodo cargado una vez no se volvía
a mirar nunca — y un split cambia todo el histórico de BPA.

Es el **tercer sitio** con el mismo patrón, después de `coingecko.py` y
`funds.py`. Recargadas las 30 empresas afectadas.

### Corregido — retornos imposibles en el índice equiponderado

`gold.mart_benchmark_returns` tenía saltos diarios imposibles; el peor,
un **+2.539 %** el 2012-04-03. Compuestos daban un índice de 10⁵⁰.

No era del mart sino de los precios: Titanium Metals cotizaba sobre
10.000 y aparecía un día con un OHLC plano de 1,40; TNB alternaba entre
28.000 y 1,44 en **599 sesiones**. Purgadas 2.002 velas aisladas —diez
veces fuera de sus dos vecinas— de 28,9 M de filas.

El criterio no mira el volumen a propósito: Banco Santander Chile marca
1.989 entre 20,3 y 20,4 con 14,7 millones de títulos negociados. Lo que
delata el artefacto es la forma.

Además, el mart acota el retorno de cada miembro a ±100 % antes de
promediar: una media no tiene defensa frente a un valor extremo, y no
debería depender de que la limpieza se haya hecho. El índice acumulado
pasa de 10⁵⁰ a **31,66×** desde 1996 (12,2 % anual).

### Corregido — no había regiones

`ref.country.region` tenía **1 valor de 250** filas, y `sub_region`,
`income_group`, `capital` y las coordenadas estaban enteras a NULL:
`seed_countries()` salía de pycountry, que solo da código y nombre. Sin
región no hay mapa ni agregado por continente.

Nuevo `seed_regiones()`, que combina dos fuentes porque ninguna trae
todo: la clasificación **M49 de la ONU** (`config/regiones_m49.csv`)
para región y subregión, y la **API del World Bank** para grupo de
renta, capital y coordenadas. 250 países con región, 249 con
subregión, 215 con grupo de renta.

De paso, la única fila que había decía "Europe" mientras el resto pasó
a "Europa": un `GROUP BY region` habría partido el continente en dos.

### Añadido

- `check_precios_aislados`: velas diez veces fuera de sus dos vecinas.
- Cuatro tests: los ratios no mezclan monedas, el BPA cuadra con el
  beneficio declarado, los países tienen región en un solo idioma, y
  el equiponderado no da saltos por encima del ±25 %.

## [0.8.0] - 2026-08-06

Auditoría de **certificación**: la que cierra la serie. Deja constancia,
tabla por tabla, de cómo se ha verificado cada una. Informe en
`docs/AUDIT_CERTIFICACION_2026-08.md` y estado en
`docs/CERTIFICACION.md`.

Con datos de terceros no se puede garantizar que cada cifra sea cierta.
Lo que ahora sí está garantizado es que de las **94 tablas**, ninguna
queda sin declarar cómo se comprueba: 21 contrastadas contra una cifra
publicada fuera, 72 coherentes sin referencia externa, 1 no verificable
con su motivo y **0 sin certificar**.

### Añadido

- **`tests/referencias.yml`**: 14 valores conocidos, anclados a fecha
  fija y con la fuente donde se comprobaron. Cubren los 13 esquemas con
  datos propios de mercado; un test falla si aparece un esquema nuevo
  sin ninguno.
- **`meta.table_certification` y `stonks certify`**: recorren las
  tablas, deciden su estado y lo persisten. Un test falla si alguna
  queda sin certificar, así que no se puede añadir una tabla sin decir
  cómo se comprueba.
- **`check_unidades_de_columna`**: comprueba que una columna llamada
  `_pct` no guarde fracciones y que una llamada `_usd` no tenga
  magnitudes de moneda local. Habría cazado de golpe los cuatro
  defectos de unidad de esta auditoría y los dos de las anteriores.
- **`check_precios_cruzados`**: contrasta una muestra rotatoria contra
  Tiingo. Sin clave se registra como **omitido**, no se salta en
  silencio.
- **`stonks.seed.unidades`**: deduce la unidad de un indicador de su
  nombre y la aplica en `seed_all()`.
- **`linaje()` en `BaseFetcher`**: origen y ejecución para estampar en
  cada fila escrita.

### Corregido — cuatro defectos de unidad de la misma familia

- **`equity.holder.pct_held` guardaba una fracción**: BlackRock
  figuraba con 0,08 en Apple en vez del 7,79 %.
- **`equity.holder.value_usd` e
  `equity.insider_transaction.value_usd` estaban en moneda local**: la
  posición de Vanguard en Samsung, con 18 billones de wones.
- **`gold.fact_factor_scores.percentile` iba de 0 a 1**, porque
  `pandas.rank(pct=True)` devuelve una fracción.
- **`fund.nav_daily` guardaba el NAV ajustado**: SPY a 461,39 el
  29/12/2023 cuando cerró a 475,31. Era el `auto_adjust` que se
  corrigió en `yfinance_.py` y no en el fetcher de fondos. **529.088
  valores liquidativos corregidos** al recargar los 496 fondos.

### Corregido — otros

- **El divisor de Londres se aplicaba por sufijo del ticker, no por la
  moneda declarada.** Compass Group figuraba a 0,33 cuando cotiza sobre
  32 dólares: Yahoo devuelve algunos valores de la LSE en dólares o
  euros, y se les dividía entre 100 igual. Afectaba a CPG.L, IHG.L y
  MTLN.L.
- **Tiingo guardaba `adjClose` en la columna `close`**, y como rellena
  huecos en la misma columna que yfinance, media serie habría quedado
  ajustada y la otra media no.
- **`fund.nav_daily.volume` desbordaba `INTEGER`**: SPY negoció
  2.174.492.800 participaciones el 10/10/2008, y la recarga moría en esa
  fila perdiendo el resto de la serie. Ampliado a `BIGINT`, aquí y en
  `deriv.futures_daily`.
- **12 operaciones de insider con precios imposibles** (una de HYEX a
  23,5 millones por acción sobre un valor que cotiza a 1,40). Purgadas.
- **1.670 indicadores sin unidad declarada (el 91 %)**: ahora **cero**.
  1.463 deducidos del nombre, 65 traídos de `/fred/series` —que la da
  gratis y el fetcher nunca llamaba—, 7 declarados a mano y 39 marcados
  `desconocida`, que es distinto de NULL.
- **Trazabilidad**: `source_id` pasa de 25 a 63 tablas de 68, y
  `fetch_run_id` de 5 a 68.

### Nota

`fetch_run_id` no se puede rellenar hacia atrás: esa información nunca
se guardó. Las filas históricas quedan sin linaje de ejecución y solo lo
llevan las nuevas.

## [0.7.0] - 2026-08-06

Auditoría de **fiabilidad**: lógica de negocio de la capa analítica y
cierre de los agujeros que dejaron las dos anteriores. Informe en
`docs/AUDIT_FIABILIDAD_2026-08.md`.

### Corregido — agujeros de lo ya arreglado

- **Los `NaN` atravesaban las 18 restricciones.** PostgreSQL ordena
  `NaN` por encima de cualquier número, así que `'NaN'::numeric > 0` es
  `TRUE`. Había 1.007 valores, suficientes para envenenar 26 días
  completos de `mart_benchmark_returns`. Ojo con la semántica: en
  `NUMERIC`, al contrario que en IEEE 754, `NaN = NaN` es `TRUE`, así
  que `x = x` no sirve de filtro; la expresión correcta es
  `x > 0 AND x < 'Infinity'`.
- **`NUMERIC(20,10)` topaba en 10¹⁰** y ya había dado cinco fallos de
  desbordamiento. Ampliado a `NUMERIC(24,10)`.
- **`is_forecast` nunca llegó a gold**: `stonks world ESP` mostraba la
  previsión del FMI para 2026 igual que un dato realizado. Propagada a
  `mart_country_year` y marcada con asterisco en el CLI.

### Corregido — la capa analítica no describía la realidad

- **Once de los catorce marts nunca se actualizaban.**
  `CREATE MATERIALIZED VIEW IF NOT EXISTS` conserva la definición
  original para siempre: cambiar el SQL no tenía efecto y el build
  terminaba "OK". Era el defecto que bloqueaba todos los demás.
- **`mart_company_macro` era un producto cartesiano**: de 1750 a 2031,
  con el 43 % de sus filas anteriores a 1900 y Apple cotizando en el
  siglo XVIII. Acotado por el historial real de cotización: de 2,38 M
  de filas a 118.307.
- **`mart_sovereign_risk` estampaba el rating de hoy sobre todos los
  años**, lo que hacía circular cualquier estudio de rating contra
  prima histórica. Ahora cada año lleva la calificación vigente.
- **`mart_crypto_overview` cubría 4 monedas de 246** por filtrar con un
  `max(date)` global. Ahora las 246.
- **El calendario bursátil marcaba los 6.740 fines de semana como
  hábiles**: 365 sesiones al año en vez de 252, con las
  anualizaciones desviadas un 20 %. Ahora 250 en 2023 y 252 en 2024,
  las del NYSE.

### Corregido — unidades

- **`market_cap_usd` no estaba en dólares.** Toyota figuraba con 34,5
  billones, que eran yenes. Se convierte con `forex.rate_daily`,
  admitiendo pares invertidos y exigiendo que el tipo tenga menos de
  30 días. Toyota pasa a 219 bn USD.
- **Los precios de Londres estaban en peniques**: AZN.L a 12.087
  cuando AstraZeneca cotiza a 120 GBP. Normalizadas las subunidades
  (`GBp`, `ZAc`, `ILA`) y recargadas las 23 empresas afectadas.
  Atención a la asimetría de Yahoo: cotiza los precios en peniques
  pero informa la capitalización en libras, con el mismo campo
  `currency`.

### Corregido — fallos sistemáticos

- **1.882 fallos de "No se pudo crear empresa"** en 90 días: los `.JO`
  reventaban la clave foránea por la moneda `ZAc`, y `CYBR` y
  `TATAMOTORS.NS` ya no existen en Yahoo (comentados en el YAML con el
  motivo).
- El error de `autoflush` era en realidad una violación de
  `close BETWEEN low AND high`: yfinance devuelve a veces un cierre
  fuera del rango del día. El fetcher sanea la vela conservando el
  cierre.

### Añadido

- Tres checks de coherencia cruzada: `check_identidad_contable`,
  `check_capitalizacion` y `check_comercio_espejo`.
- Ocho tests nuevos (18 en total en `test_integridad_datos.py`), entre
  ellos uno que **falla si una tabla de la base no está documentada**.
- Diccionario de datos regenerado: de 76 tablas documentadas de 99 a
  las **99**. Al generador le faltaban los esquemas `realestate` y
  `calendar`.

### Verificado

Identidad contable: 7 balances descuadran de 18.697 (0,04 %). World
Bank contra FMI: 3,57 % de desvío sobre 190 países. Comercio espejo:
36,1 % sobre 194.477 pares, dentro de lo normal por CIF/FOB.

Dos riesgos señalados en el análisis previo resultaron
sobredimensionados al medirlos: la clave del point-in-time tiene **cero
colisiones** en 1,17 M de claves (el desfase de `fiscal_year` es
convención contable, no corrupción), y las fechas genuinamente
imposibles son **272**, no 7.847.

## [0.6.0] - 2026-08-06

Auditoría de **datos**: veracidad y completitud. La de v0.5.0 miró la
estructura; esta mira el contenido. Informe completo en
`docs/AUDIT_DATOS_2026-08.md`.

### Verificado

- Los datos macro son reales: PIB de EE. UU. 2023 = 27,81 billones
  (real 27,72), PIB PPP de India y China correctamente diferenciados,
  Bitcoin cuadra al céntimo en tres fechas de control.
- World Bank contra FMI en PIB per cápita 2022: **190 países, desvío
  medio del 3,57 %**, solo 22 discrepan más del 10 %.
- Frescura entre 0 y 2 días en todos los dominios.

### Corregido

- **Los precios de renta variable estaban mal etiquetados.**
  `yfinance_.py` no pasaba `auto_adjust`, que en yfinance 1.3 vale
  `True` por defecto: `close` contenía el precio ajustado por splits y
  dividendos (AAPL 2023-12-29 = 190,55 en vez de 192,53), `adj_close`
  estaba vacía en las 24.089.385 filas, y el ajuste retroactivo
  generaba **22.166 precios negativos** en 19 empresas (mínimo
  −246.247). De ahí salían 10.672 filas con `high < low` y 13.635 con
  el cierre fuera de rango.
- **`NUMERIC(14,4)` truncaba a cero las acciones sub-céntimo**: 29.443
  filas en 48 empresas. Ampliado a `NUMERIC(20,10)` en 42 columnas de
  once tablas, con las columnas de cada tabla en un único `ALTER` para
  evitar reescrituras repetidas de 4 GB.
- **Tres tablas intraday estaban a cero por un bug de una línea.** No
  es que los fetchers nunca se hubieran ejecutado: se ejecutaron doce
  veces y fallaron las doce con `ts = null`. `batch_download` hacía
  `reset_index()` y yfinance nombra ese índice `Date` en diario y
  `Datetime` en intradía; al concatenar lotes heterogéneos pandas
  creaba ambas columnas rellenando con `NaT`. Además, un solo `ts`
  malo tiraba el chunk de 10.000. **5.513.881 filas recuperadas.**
- **`GDP_NOMINAL` declaraba `billion_usd` con valores en USD
  absolutos** (mediana 8,2e9): error de factor mil millones. Igual
  `GDP_PPP`. Comprobado que los indicadores del FMI sí son correctos.
  Además se normalizaron 32 etiquetas de unidad a 18.
- **Cuatro `coin_id` de crypto empalmaban dos activos distintos**
  (COMP, APT, SUI, GTC), defecto introducido por la deduplicación de
  la auditoría anterior. Purgadas 2.971 filas ajenas y recargadas
  desde CoinGecko; las cuatro cuadran ahora con la fuente.
- `alt.housing_index` y `alt.housing_index_value` retiradas: 0 filas,
  sin fetcher, duplicaban `realestate.price_index*`.
- `country.profile` tenía 40 países de 250 porque el fetcher usaba una
  lista fija; ahora recorre los que el World Bank reconoce.

### Causas raíz corregidas

- `seed_indicators()` solo insertaba: cambiar `config/indicators.yml`
  no tenía ningún efecto sobre la base. Por eso la unidad falsa
  sobrevivió tanto tiempo.
- `coingecko.py` hacía `if exists: continue`, así que un dato mal
  cargado se quedaba para siempre. Ahora es un upsert real.
- `fetch_prices_bulk()` nunca se había ejecutado y tenía dos bugs: un
  `TypeError` en su propio manejador de excepciones, que tapaba el
  error real, y un `pandas` sin importar.

### Añadido

- `src/stonks/quality_datos.py`: siete checks de veracidad y
  completitud (OHLC coherente, unidades plausibles, coherencia entre
  fuentes, empalme de series, SLA de frescura real, fallos de fetch,
  tablas vacías), colgados de `run_all_checks()`.
- `stonks audit` reescrito: ejecuta **todos** los checks (antes solo
  tres de ocho), persiste en `meta.data_quality` y acepta
  `--dominio`, `--detalle` y `--estricto`.
- `tests/test_integridad_datos.py`: diez invariantes de contenido
  contra la base viva, hermano de `test_integridad_esquema.py`.
- `scripts/recargar_precios_sin_ajustar.py`: recarga por tandas y
  reanudable del universo de precios.

## [0.5.0] - 2026-08-04

Auditoría profunda de cobertura de datos, diseño de base de datos y
calidad de código. El informe completo está en
`docs/AUDIT_2026-08.md`.

### Corregido

- **El esquema v0.4.0 nunca se había aplicado a la base de datos.**
  El commit estaba en git pero `stonks_db` seguía en v0.3: faltaban
  las 7 tablas de `deriv` e intraday multi-dominio, y los universos
  seguían en 54 pares forex, 96 coins, 25 commodities y 100 ETFs.
  La causa raíz era no tener sistema de migraciones.
- `trade.flow.partner_code` no tenía clave foránea mientras
  `reporter_code` sí: el socio comercial quedaba sin validar sobre
  1,07 M de filas.
- 35 columnas de clave foránea sin índice, incluidos todos los
  `source_id`. Cualquier filtro por fuente hacía *seq scan*.
- 21 columnas `timestamp` sin zona horaria conviviendo con
  `timestamptz` en el resto del modelo.
- `macro.data_point` mezclaba 9,06 M de observaciones con 32.690
  proyecciones futuras (hasta 2031) sin distinguirlas: sesgo
  look-ahead en cualquier backtest.
- El esquema `realestate` estaba documentado y declarado en
  `SCHEMAS` pero no existía en la base de datos; `calendar` existía
  sin ninguna tabla.
- `gold.mart_etf_category` y `gold.mart_yield_curve` referenciaban
  columnas inexistentes (`nav_daily.close`, curva en formato ancho).
  Nunca se habían ejecutado.
- El pipeline diario estaba programado dos veces en cron (20:30 y
  21:30): se solapaba consigo mismo y competía por los locks.

### Añadido

- **Alembic** con baseline del esquema existente. Toda evolución del
  modelo pasa ahora por una revisión versionada.
- `ref.area`: catálogo geográfico superset de `ref.country` que
  admite agregados regionales (`WLD`, `ECS`) e entidades históricas
  (`CSK`, `DDR`, `YUG`), con su país sucesor cuando es unívoco.
  Permite que declarante y socio de `trade.flow` se validen igual.
- `macro.data_point.is_forecast`, con backfill de las 32.690
  proyecciones existentes.
- **CFTC Commitments of Traders** (`deriv.cot_contract`,
  `deriv.cot_report`): 946 contratos y 286.694 informes semanales
  desde 1986. Primera medida de posicionamiento de la base.
- **GLEIF** (`ref.legal_entity`, `equity.company.lei`):
  identificadores LEI (ISO 17442). Resuelve la identidad de entidad,
  que hasta ahora se cruzaba por `ticker`, y abre el cruce con
  `borme_db` y `supliers_db`.
- **Damodaran** (`fi.country_risk_premium`): 175 primas de riesgo
  país. Rellena además `country.tax_rate`, vacía desde el inicio,
  con 155 tipos de sociedades.
- **Fama-French** (`equity.factor_return`): 18.702 observaciones de
  factores en 7 regiones, para contrastar `gold.fact_factor_scores`
  contra una referencia académica.
- **Inmobiliario** (`realestate.price_index`, `price_index_value`):
  85 índices de 41 países vía BIS y OCDE, más Case-Shiller.
- **Calendario económico** (`calendar.release`, `release_date`):
  330 publicaciones y 91.326 fechas, de las que 3.860 son futuras.
- **Constituyentes de índices mundiales**: 15 índices cargados
  (antes solo el S&P 500), 418 empresas nuevas fuera de EE. UU.
- **Tiingo** como segunda fuente de precios, para romper la
  dependencia exclusiva de yfinance. Rellena huecos sin pisar los
  datos existentes y permite validación cruzada de cierres.
- Divisas retiradas de ISO 4217 (BGN, HRK, LTL…) al seed de
  referencia: sin ellas el universo forex completo rompía la FK
  contra `ref.currency`.
- 30 tests nuevos: parseo de los fetchers incorporados y un bloque
  de invariantes de esquema (`tests/test_integridad_esquema.py`) que
  vuelve a fallar si reaparece cualquiera de los defectos corregidos.

### Reparado (fetchers que nunca cargaron datos)

Los tres fetchers escritos pero sin efecto (~1.300 líneas) se
investigaron uno a uno:

- **UNCTAD**: apuntaba a `unctadstat.unctad.org/EN/BulkDownload/*.csv`,
  hoy 404. UNCTAD rehízo el portal y sirve los mismos datos por API
  comprimidos en 7z. Reparado (dependencia nueva: `py7zr`). Carga
  **36.563 puntos**: inversión extranjera directa (flujos y stock,
  entrante y saliente, 200 países desde 1990) y el índice de
  conectividad marítima LSCI (178 países, trimestral desde 2006).
  Tenía además dos bugs latentes: la columna de economía elegida era
  el código M49 en vez del nombre, y el parseo de periodo no entendía
  trimestres, lo que descartaba LSCI entera.
- **WIPO**: el CSV bulk devuelve la página HTML del Data Center, que
  hoy es una aplicación JavaScript sin endpoint de descarga.
  Reorientado a la serie histórica que WIPO sí publica como fichero:
  **5.130 puntos de patentes 1883-1979** por oficina y origen, un
  tramo que ninguna otra fuente de la base cubre. Tenía dos bugs más:
  consultaba `ref.country.iso2` (la columna es `code_alpha2`) y un
  límite de año en 1900 que descartaba los primeros 17 años.

### Corregido (detectado por el propio pipeline nocturno)

- `crypto.coin` admitía símbolos duplicados. Al ampliar el universo a
  260 monedas, CoinGecko trajo cuatro activos con su identificador
  antiguo **y** el nuevo (SNX como `havven` y como
  `synthetix-network-token`; igual con CRO, FLOW y GT). El índice
  único de `gold.mart_crypto_overview` los rechazaba y la
  construcción de gold falló en el cron de la noche siguiente.
  Se fusionaron los pares conservando el histórico largo y el rank de
  mercado, y se añadió `UNIQUE(symbol)` para que no se repita.

### Descartado

- **Stooq** como segunda fuente de precios. Desde 2026 responde a
  toda petición programática con un desafío JavaScript de
  verificación de navegador; sortearlo sería evadir una medida
  antibot deliberada. Se sustituyó por Tiingo, que sí tiene API
  documentada (requiere clave gratuita).
- **Heritage** (Index of Economic Freedom). Mismo motivo:
  `heritage.org` devuelve 403 a todo acceso automatizado, incluida la
  portada. Se eliminó `heritage.py` y su paso del pipeline, y se
  retiraron de `gold.mart_country_year` y `mart_country_governance`
  las cinco columnas `HF_*`, que estaban a NULL en las 40.516 filas
  porque la fuente nunca llegó a cargar. La gobernanza sigue cubierta
  por V-Dem, Freedom House, TI-CPI y FSI.

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
