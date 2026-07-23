# Guía de rendimiento para consultas

Tips para las tablas más grandes de stonks_db.

## Tablas grandes (> 1M filas)

| Tabla | Filas | Índices clave |
|-------|-------|---------------|
| `gold.fact_fundamentals_pit` | ~31M | `(company_id, metric)`, `(company_id, filed_date)` |
| `equity.price_daily` | ~8.5M | `(company_id, date)` |
| `macro.data_point` | ~8M | `(series_id, date)` |
| `gold.mart_trade_matrix` | ~442K | `(reporter_code, partner_code, year)` |

## Reglas de oro

### 1. Siempre filtrar por la clave del índice

```sql
-- MAL: escanea 31M filas
SELECT * FROM gold.fact_fundamentals_pit
WHERE metric = 'Revenue';

-- BIEN: usa el índice (company_id, metric)
SELECT * FROM gold.fact_fundamentals_pit
WHERE company_id = 42 AND metric = 'Revenue';
```

### 2. Limitar el rango de fechas

```sql
-- MAL: todos los precios de todas las empresas
SELECT * FROM equity.price_daily;

-- BIEN: una empresa, un año
SELECT * FROM equity.price_daily
WHERE company_id = 42
  AND date BETWEEN '2023-01-01' AND '2023-12-31';
```

### 3. Usar `DISTINCT ON` en vez de subconsultas

```sql
-- Último precio de cada empresa (rápido)
SELECT DISTINCT ON (company_id) company_id, date, close
FROM equity.price_daily
ORDER BY company_id, date DESC;
```

### 4. Usar los marts gold (ya precalculados)

Los marts materializados (`mart_country_year`, `mart_company_macro`,
`mart_trade_matrix`, etc.) ya resumen millones de filas. Consulta el
mart antes de JOINear tablas base.

### 5. Usar `EXPLAIN ANALYZE` para diagnosticar

```sql
EXPLAIN ANALYZE
SELECT ... FROM gold.fact_fundamentals_pit
WHERE company_id = 42 AND metric = 'NetIncomeLoss';
```

Busca `Seq Scan` (malo en tablas grandes) → debe ser `Index Scan`
o `Bitmap Index Scan`.

## Configuración para consultas ad-hoc pesadas

```sql
-- Más memoria para ordenaciones y agregaciones grandes
SET work_mem = '256MB';

-- Para sesiones interactivas de análisis (no en producción)
SET statement_timeout = '5min';
```

## Vistas materializadas

Los marts gold son **vistas materializadas**: tablas precalculadas
que se refrescan con `build_gold()` (al final del pipeline). Son
rápidas de consultar pero reflejan el estado del último refresh.

Para forzar un refresh manual:

```sql
REFRESH MATERIALIZED VIEW gold.mart_country_year;
```

Esto puede tardar minutos si las tablas base son grandes.
