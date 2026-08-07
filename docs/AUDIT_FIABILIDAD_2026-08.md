# Auditoría de fiabilidad — stonks_db (2026-08-06)

Tercera auditoría. La primera (`AUDIT_2026-08.md`) miró la
**estructura**; la segunda (`AUDIT_DATOS_2026-08.md`) la **veracidad de
los datos crudos**. Esta mira la **lógica de negocio de la capa
analítica** y cierra los agujeros que dejaron las dos anteriores.

---

## 1. Los agujeros de lo ya arreglado

Lo más incómodo de esta auditoría: las correcciones anteriores tenían
huecos.

### 1.1 Los `NaN` atravesaban las 18 restricciones

`max(close)` en `equity.price_daily` devolvía **`NaN`**. PostgreSQL
admite `NaN` en `NUMERIC` y lo ordena **por encima de cualquier
número**, así que `'NaN'::numeric > 0` es `TRUE` y los `CHECK` de
`close > 0` no lo filtraban.

Había **1.007 valores**: 913 en `equity.price_daily` (766 empresas),
91 en `equity.index_price`, 2 en `fund.nav_daily` y 1 en
`commodity.price_daily`. Bastaban para envenenar **26 días completos**
de `gold.mart_benchmark_returns`: un solo precio `NaN` convierte en
`NaN` el retorno de todo el mercado ese día.

Ojo con la semántica, porque es contraintuitiva: en `NUMERIC`, a
diferencia de IEEE 754, **`NaN = NaN` es `TRUE`**. El truco habitual de
`x = x` no sirve como filtro. La expresión que funciona es
`x > 0 AND x < 'Infinity'`, porque `NaN` se ordena por encima del
infinito y falla la segunda condición. De paso cubre los infinitos, que
`NUMERIC` también admite desde PostgreSQL 14.

### 1.2 El techo numérico era demasiado bajo

`NUMERIC(20,10)` deja diez dígitos enteros, es decir valores por debajo
de 10¹⁰, y ya había producido cinco fallos de `NumericValueOutOfRange`.
Ampliado a `NUMERIC(24,10)`: techo de 10¹⁴ sin perder decimales.

### 1.3 `is_forecast` nunca llegó a la capa gold

La primera auditoría añadió la marca a `macro.data_point`. Pero
`gold/build.py` **no la mencionaba ni una vez**, así que
`stonks world ESP` mostraba 2.091 bn de PIB para 2026 —la previsión del
FMI— presentada igual que un dato realizado. El sesgo look-ahead que se
corrigió abajo seguía intacto una capa más arriba, y precisamente en el
comando que uno usaría para mirar la economía de un país.

---

## 2. El defecto que bloqueaba todos los demás

`gold/build.py` creaba los catorce marts con
`CREATE MATERIALIZED VIEW **IF NOT EXISTS**`. Una vez creada, una vista
materializada **conserva su definición SQL para siempre**: cambiar el
fichero no tenía ningún efecto y el build terminaba diciendo que todo
había ido bien.

Once de los catorce llevaban congelados desde su creación. No había
forma de saber si el SQL del repositorio era el que estaba en la base.

Es el primero que había que arreglar, porque sin él ninguna otra
corrección de gold habría surtido efecto.

---

## 3. Los marts no describían la realidad

### 3.1 `mart_company_macro` era un producto cartesiano

Iba de **1750 a 2031**, con **1.012.469 filas (43 %) anteriores a
1900**. Apple tenía fila para 1750. El JOIN emparejaba solo por país,
sin ninguna noción de cuándo existió la empresa.

Acotado con el historial real de cotización de cada empresa y con
`delisted_date`: de 2.376.605 filas a **118.307**, desde 1962.

### 3.2 `mart_sovereign_risk` estampaba el rating de hoy en todos los años

Tomaba `rn = 1` (la calificación más reciente) y la aplicaba a cada
año, incluido 1750. Cualquier estudio de "rating contra prima
histórica" salía circular: el rating ya incorporaba lo que iba a pasar.

Ahora cada año lleva la calificación vigente **ese** año.

### 3.3 `mart_crypto_overview` cubría 4 monedas de 246

Filtraba por `max(date)` **global** en vez de por moneda, y como no
todas tienen barra el mismo día el JOIN interno eliminaba el 98 % del
universo. El patrón correcto (`DISTINCT ON` + `<=`) ya estaba escrito
cuarenta líneas más abajo, en `mart_etf_category`; aquí no se había
aplicado.

Ahora cubre las **246**.

### 3.4 El calendario bursátil contaba fines de semana

`dim_date.is_trading_day` estaba puesto al literal `TRUE` para cada día
generado: los **6.740 fines de semana** figuraban como hábiles. Quien
contara días de mercado obtenía 365 al año en lugar de ~252, y las
anualizaciones de volatilidad y de Sharpe salían desviadas en
√(365/252), un **20 %**.

Ahora se deduce de si hubo cotización. Con un matiz que costó dos
intentos: la primera versión daba **310 sesiones en 2023** porque
incluía la bolsa saudí, **que abre en domingo**. Acotado al mercado
estadounidense, que es quien consume este calendario, da **250 sesiones
en 2023 y 252 en 2024**: exactamente las del NYSE.

---

## 4. Unidades: la capitalización y los precios de Londres

### 4.1 `market_cap_usd` no estaba en dólares

Contenía la capitalización en la moneda de cotización. Toyota figuraba
con **34.510.747.992.064**, que son yenes; su valor real ronda los
230.000 millones de dólares. La media de las coreanas salía a 148.667
"miles de millones de dólares".

Se convierte con `forex.rate_daily`, admitiendo pares invertidos
(`EURUSD`, `AUDUSD`) y **exigiendo que el tipo tenga menos de 30 días**:
un tipo de cambio rancio convertiría mal y en silencio. Toyota pasa a
**218,9 bn USD**.

### 4.2 Los precios de Londres estaban en peniques

`AZN.L` figuraba a **12.087** cuando AstraZeneca cotiza a 120 GBP.
Yahoo devuelve los mercados de Londres, Johannesburgo y Tel Aviv en la
subunidad de su moneda (`GBp`, `ZAc`, `ILA`), y esos códigos ni
siquiera existen en `ref.currency`.

Hay una asimetría de la fuente que conviene dejar escrita porque me
llevó a un error intermedio: Yahoo cotiza los **precios** en peniques
pero informa la **capitalización en libras**, aunque el campo
`currency` diga `GBp` en los dos casos. Solo hay que dividir los
precios.

Resultado tras recargar las 23 empresas afectadas:

| Ticker | Antes | Ahora | Real |
|---|---|---|---|
| AZN.L | 12.087 | 120,87 | ~120 GBP |
| SHEL.L | 3.280 | 32,82 | ~33 GBP |
| BP.L | 517 | 5,17 | ~5 GBP |
| HSBA.L | 1.513 | 15,13 | ~15 GBP |

---

## 5. Los fallos que llevaban tres meses invisibles

De las 2.454 ejecuciones fallidas en 90 días, **1.882 eran el mismo
error**: "No se pudo crear empresa", en unos 24 tickers internacionales
que el cron reintentaba cada noche.

Dos causas distintas:

- **`.JO` (Johannesburgo)**: Yahoo devuelve la moneda `ZAc`, que no
  existe en `ref.currency`, y la clave foránea reventaba. Resuelto con
  la normalización de subunidades.
- **`CYBR` y `TATAMOTORS.NS`**: Yahoo ya no resuelve esos tickers
  (404). Comentados en `config/companies.yml` con el motivo, en lugar
  de borrarlos, para no perder la traza de que estuvieron en el
  universo.

Y un tercero que se destapó al arreglar los anteriores: el error de
`autoflush` de SQLAlchemy era en realidad una **violación de la
restricción `close BETWEEN low AND high`**. yfinance devuelve de vez en
cuando un cierre fuera del rango del día (HSBA.L el 2008-06-13 llega
con `open=high=low=7,198` y `close=7,163`). Ahora el fetcher sanea la
vela: conserva el cierre, que es lo que importa, y anula las otras tres
columnas en lugar de inventar un rango que las contenga.

---

## 6. Dos correcciones al análisis previo

El informe del agente que exploró la capa gold señaló dos riesgos que,
al medirlos, resultaron **sobredimensionados**. Conviene dejarlo por
escrito para no arrastrar la alarma:

- **"3,1 M de filas con la clave de deduplicación colisionando"**. Medí
  **cero colisiones** en 1.174.081 claves. El desfase entre
  `fiscal_year` y el año de `period_end_date` existe en el 13 % de las
  filas, pero es **convención contable**: el ejercicio fiscal 2025 de
  Apple empieza en octubre de 2024, así que su primer trimestre cierra
  en diciembre de 2024. No se pierde ningún dato.
- **"7.847 fechas imposibles"**. Las genuinamente imposibles son
  **272** (periodos cerrando en 2105 o en 6016, erratas de las propias
  presentaciones ante la SEC). El resto son legítimas: recuentos de
  acciones con fecha posterior a la firma del informe.

La tabla point-in-time está, en lo esencial, **bien construida**: usa
la fecha de presentación real de EDGAR y el desfase medio con el cierre
de trimestre es de **68 días**, que es lo realista. Aun así se amplió
la clave con `period_end_date` como defensa y se purgaron las 272.

---

## 7. Lo que confirma que los datos son fiables

| Comprobación | Resultado |
|---|---|
| Identidad contable (activo = pasivo + patrimonio) | 7 descuadran de 18.697 (**0,04 %**) |
| World Bank vs FMI, PIB per cápita | 3,57 % de desvío sobre 190 países |
| Comercio espejo (X de A hacia B vs M de B desde A) | 36,1 % sobre 194.477 pares, dentro de lo normal por CIF/FOB |
| Precios contra la realidad | AAPL, KO, MSFT y las 23 de Londres cuadran |
| Panel de país | PIB, paro, inflación y deuda de España cuadran |

La capitalización contra acciones × precio sí descuadra en 234 de 1.584
(14,8 %), lo que es esperable: la capitalización es una foto de hoy y
las acciones en circulación cambian entre publicaciones. Queda como
check permanente con tolerancia del 25 %.

---

## 8. Lo que vigila el sistema ahora

Tres checks nuevos en `src/stonks/quality_datos.py`, que se suman a los
siete de la auditoría anterior:

| Check | Qué detecta |
|---|---|
| `check_identidad_contable` | Balances que no cuadran |
| `check_capitalizacion` | Errores de unidad y acciones desactualizadas |
| `check_comercio_espejo` | Desvío entre exportaciones e importaciones declaradas |

Y ocho tests nuevos en `tests/test_integridad_datos.py`, que ahora son
18: precios negativos, OHLC coherente, unidades, tablas vacías,
empalmes de serie, SLA de frescura, coherencia entre fuentes, precisión,
`adj_close`, marts recreados, empresas que no cotizan antes de existir,
calendario bursátil, proyecciones marcadas, cobertura de crypto,
capitalización en dólares, fechas del point-in-time y **documentación
al día**.

Ese último cierra un desfase que venía de largo: **23 de 99 tablas no
estaban en el diccionario de datos**, incluido todo lo que añadieron
las dos auditorías anteriores. Regenerado con
`scripts/gen_data_dictionary.py`, al que le faltaban los esquemas
`realestate` y `calendar`. Ahora el test falla si alguien añade una
tabla y no la documenta.

---

## 9. Antes y después

| Métrica | Antes | Ahora |
|---|---|---|
| Valores `NaN` en precios | 1.007 | **0** |
| Días de benchmark envenenados | 26 | **0** |
| Marts que se actualizan al cambiar el SQL | 3 de 14 | **14 de 14** |
| `mart_company_macro` | 2,38 M filas desde 1750 | 118 k desde 1962 |
| `mart_crypto_overview` | 4 monedas | **246** |
| Sesiones bursátiles en 2024 | 366 | **252** |
| Años proyectados marcados en gold | 0 | 1.125 |
| Toyota, capitalización | 34.510 bn | **219 bn** |
| AZN.L, cotización | 12.087 | **120,87** |
| Tablas documentadas | 76 de 99 | **99 de 99** |
| Tests | 108 | **116** |

## 10. Deuda conocida

- 1.670 indicadores (91 %) siguen sin unidad declarada.
- `gold.fact_fundamentals_pit.source_id` está a NULL en los 33 M de
  filas, y ninguna tabla guarda `fetch_run_id`: no se puede responder
  "qué ejecución escribió esta fila".
- `revenue` no tiene historia anterior a 2018 para las empresas que
  adoptaron ASC 606, lo que introduce un sesgo de selección
  correlacionado con sector y tamaño.
- 3.152 empresas (28,6 %) siguen sin ningún precio.
- Tiingo sigue sin clave: no hay segunda fuente de precios ni
  validación cruzada de cotizaciones.
