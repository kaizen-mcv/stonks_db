# Auditoría de certificación — agosto de 2026

Cuarta auditoría de `stonks_db`, y la que cierra la serie. Las tres
anteriores miraron la estructura, la veracidad de los datos crudos y la
lógica de la capa analítica. Esta responde a la pregunta que quedó
abierta: **¿son fiables todos los datos?**

## La respuesta, y por qué no es "sí"

Con datos de terceros no se puede garantizar que cada cifra sea cierta.
Si el World Bank publica mal un PIB, esta base lo reproduce fielmente y
no hay forma de saberlo desde dentro. Decir "todos los datos son
correctos" sería una promesa que nadie puede cumplir.

Lo que sí se puede garantizar, y es lo que ahora está garantizado, es
que **de cada una de las 94 tablas consta cómo se ha verificado, o
consta explícitamente que no se puede verificar y por qué**:

| Estado | Tablas | |
|---|---:|---:|
| Contrastadas contra una cifra publicada fuera | 21 | 22 % |
| Coherentes, sin cifra externa con la que comparar | 72 | 77 % |
| No verificables, con motivo escrito | 1 | 1 % |
| **Sin certificar** | **0** | **0 %** |

El detalle tabla por tabla está en [CERTIFICACION.md](CERTIFICACION.md).
Un test falla si alguien añade una tabla y no declara cómo se comprueba,
así que ese cero se mantiene solo.

## Lo que se ha arreglado

### Cuatro defectos de unidad, de la misma familia

Los tres primeros ya se conocían de auditorías anteriores
(`market_cap_usd` en yenes, `GDP_NOMINAL` etiquetado `billion_usd` con
dólares absolutos). Esta encontró cuatro más:

- **`equity.holder.pct_held` guardaba una fracción.** BlackRock
  figuraba con 0,08 en Apple cuando tiene el 7,79 %. El máximo de las
  74.847 filas era 0,9643 y ninguna pasaba de 1.
- **`equity.holder.value_usd` y
  `equity.insider_transaction.value_usd` estaban en moneda local.** La
  posición de Vanguard en Samsung figuraba con 18.123.636.562.500, que
  son wones: unos 12.700 millones de dólares.
- **`gold.fact_factor_scores.percentile` iba de 0 a 1**, porque
  `pandas.rank(pct=True)` devuelve una fracción y la columna se llama
  percentil.
- **`fund.nav_daily` guardaba el NAV ajustado por distribuciones.** SPY
  figuraba a 461,39 el 29/12/2023 cuando cerró a 475,31. Era el mismo
  defecto de `auto_adjust` que se corrigió en `yfinance_.py`, pero el
  fetcher de fondos se había quedado fuera. Se recargaron los 496
  fondos: **529.088 valores liquidativos corregidos**.

Todos los habría cazado de golpe el check nuevo:
`check_unidades_de_columna`, que comprueba que una columna llamada
`_pct` no contenga fracciones y que una llamada `_usd` no tenga
magnitudes de moneda local. Hoy da cero sospechosas sobre 18 columnas.

### Londres: el divisor se aplicaba por sufijo, no por moneda

El ticker acabado en `.L` se dividía siempre entre 100, porque la Bolsa
de Londres cotiza en peniques. Pero **hay valores de la LSE que Yahoo
devuelve en otra moneda**: Compass Group e InterContinental Hotels
llegan en dólares y Metlen en euros. A los tres se les dividió un
precio que no estaba en peniques.

Compass Group figuraba a 0,33 cuando cotiza sobre 32 dólares. El
detector inicial —"precio menor que 1"— solo encontró dos de los tres:
IHG se había quedado en 1,61 y pasaba el filtro. El criterio correcto
es el que ahora usa el código: dividir solo cuando la moneda declarada
es la del mercado.

### Insiders imposibles

Doce operaciones tenían un precio implícito de más de cien veces el de
mercado; una de HYEX figuraba con 307 billones de dólares, a 23,5
millones por acción sobre un valor que cotiza por debajo de 1,40. Es
basura de Yahoo en cotizadas OTC. Purgadas, y con un test que impide
que vuelvan.

### El desbordamiento que cortaba una serie entera

`fund.nav_daily.volume` era `INTEGER`, y SPY negoció 2.174.492.800
participaciones el 10/10/2008: por encima del límite de 2.147.483.647.
La recarga de fondos moría en esa fila y perdía el resto de la serie de
ese fondo. Ampliado a `BIGINT`, aquí y en `deriv.futures_daily`.

## Lo que se ha construido

### Un corpus de valores de referencia

`tests/referencias.yml`: 14 cifras concretas, cada una anclada a una
fecha fija y con la fuente donde se comprobó. Cubren los 13 esquemas
con datos propios de mercado, y un test falla si aparece un esquema
nuevo sin ninguna.

Es la diferencia entre comprobar que los datos son **coherentes** y
comprobar que son **ciertos**. Los otros tests detectan corrupción; solo
este detecta que una serie entera esté equivocada de forma consistente.

Tres reglas que salieron de escribirlo:

1. **Anclar a fecha fija, nunca a "el último valor".** La primera
   referencia de Londres fallaba al día siguiente de escribirla.
2. **La consulta tiene que ser precisa.** Una consulta de interés
   abierto del oro devolvía 1.324 en vez de 458.584 porque cogía el
   contrato de PAX GOLD en lugar del principal de COMEX.
3. **Tolerancia realista.** La población de India de 2023 sale 1.438 M
   en la base y 1.428 M en la publicación: las dos son correctas según
   la revisión que se mire.

### Las unidades del catálogo macro

Era el hueco de mayor alcance: **1.670 indicadores de 1.835 (el 91 %)
sin unidad declarada**, así que el check de plausibilidad solo podía
auditar el 9 % del catálogo.

Ninguno era irrecuperable. La unidad nunca se perdió en tránsito: o
estaba en el propio nombre —"(% of GDP)", "(current US$)", "(per 1,000
people)"— o estaba escrita como literal en el fetcher que la descargó.
El defecto no era de captura sino de persistencia: 20 de los 23 sitios
donde se construye un `Indicator` omitían el argumento `unit`.

Resultado: **cero indicadores con `unit` a NULL**. 1.463 deducidos del
nombre, 65 traídos de la API de FRED (que da `units` gratis en
`/fred/series`, y el fetcher nunca lo llamaba), 7 declarados a mano
donde la fuente lo documenta y el nombre no, y 39 marcados
`desconocida`, que es una respuesta distinta de NULL: dice que se miró.

La inferencia se validó contra la magnitud observada, y ahí saltaron
ocho etiquetas mal deducidas que sin ese contraste habrían pasado:
"Carbon intensity of GDP (kg CO2e per constant 2015 US$)" no está en
dólares, "Number of deaths ages 5-9 years" no se mide en años, y el
capital de Penn World Table es un índice con base 2017=1, no un importe.
Hoy el check da **cero unidades implausibles**.

### Trazabilidad

De 68 tablas de datos, 25 tenían `source_id` y **solo 5**
`fetch_run_id`. Ahora las tienen 63 y 68 respectivamente. El origen se
rellenó hacia atrás donde se podía deducir: la mayoría de las tablas las
escribe un único fetcher, y `macro.series` se resolvió por la fuente
dominante de sus propios datos.

`fetch_run_id` **no se puede rellenar hacia atrás** —esa información
nunca se guardó—, así que las filas históricas quedan sin linaje de
ejecución para siempre y solo lo llevan las nuevas. Es un corte
consciente.

### La segunda fuente

`check_precios_cruzados` compara una muestra rotatoria contra Tiingo.
Sin clave registrada no se ejecuta, pero **se registra como omitido**,
no se salta en silencio: la diferencia entre "no diverge" y "no se ha
mirado" es justo lo que estas cuatro auditorías han ido persiguiendo.

Al montarlo salió otro defecto: el fetcher de Tiingo guardaba
`adjClose` en la columna `close`. Como Tiingo rellena huecos en la misma
columna que yfinance, media serie habría quedado ajustada y la otra
media no.

## Lo que sigue pendiente

1. **La clave de Tiingo** (`STONKS_TIINGO_KEY`, gratuita). Hasta
   entonces, `equity.price_daily` está contrastada contra referencias
   puntuales pero no contra una segunda fuente sistemática.
2. **`fetch_run_id` solo lo escriben cuatro fetchers** (precios, 360°,
   fondos y crypto). El resto tiene la columna y la deja a NULL; hay que
   ir añadiendo `**self.linaje()` a medida que se toquen.
3. **39 indicadores con unidad `desconocida`.** Se pueden resolver
   leyendo el `sourceNote` del World Bank, que se descarga y se
   descarta sin guardar.
4. **Las cinco tablas de `bronze` no tienen `source_id`**, a propósito:
   ya llevan `fetch_run_id` y `meta.fetch_run` tiene la fuente.

## Cómo se comprueba todo esto

```bash
.venv/bin/python -m pytest tests/ -q      # suite completa
.venv/bin/stonks certify --estricto       # cero tablas sin certificar
.venv/bin/stonks audit --estricto         # los 11 checks de veracidad
python scripts/gen_certificacion.py       # regenera CERTIFICACION.md
```

Y las cuatro consultas que deben dar cero:

```sql
SELECT count(*) FROM macro.indicator WHERE unit IS NULL;
SELECT count(*) FROM meta.table_certification
 WHERE estado = 'sin_certificar';
SELECT count(*) FROM equity.holder WHERE pct_held > 100;
SELECT count(*) FROM equity.price_daily WHERE close <= 0;
```
