# Capa gold

Construcción del modelo analítico **point-in-time** (esquema `gold`).

- `build.py` — `build_gold()`: reconstrucción idempotente
  (`INSERT...SELECT` + `ON CONFLICT`) de:
  - `gold.dim_date`, `gold.dim_company` (dimensiones).
  - vista `gold.mart_pool_membership` (universo PIT por día).
  - materializada `gold.mart_benchmark_returns` (retorno diario del pool
    equiponderado **honesto** vs SPY).

Se ejecuta al final del pipeline. Es seguro re-ejecutar: dos corridas
dejan el mismo estado. La auditoría se registra en
`meta.transform_run` (`domain='gold'`).

`gold.index_membership`, `gold.fact_fundamentals_pit` y
`gold.fact_factor_scores` se pueblan en las fases B y C.
