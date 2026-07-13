# Capa gold

Construcción del modelo analítico (esquema `gold`). `build.py::
build_gold()` reconstruye de forma idempotente (`INSERT...SELECT` +
`ON CONFLICT`, refresco de materializadas). Se ejecuta al final del
pipeline; dos corridas dejan el mismo estado. Auditado en
`meta.transform_run` (`domain='gold'`).

**Dimensiones**: `dim_date`, `dim_company`, `dim_country`,
`dim_indicator` (vista catálogo).

**Mercados financieros**: `index_membership` (universo S&P 500 PIT),
`fact_fundamentals_pit` (SEC), `fact_factor_scores` (factores),
`mart_benchmark_returns` (pool equiponderado honesto vs SPY).

**Economía mundial**: `mart_country_year` (panel ancho país×año
cross-dominio), `mart_trade_matrix` (comercio bilateral).

Los factores tienen su propio módulo de cálculo en
`transform/factors.py`; el resto de la lógica gold vive aquí como SQL.
