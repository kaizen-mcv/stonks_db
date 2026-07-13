# Capa transform

Normalización **bronze → silver/gold** de forma idempotente. Todas las
subclases heredan `base.py::BaseTransform` (auditoría en
`meta.transform_run`), leen del origen, normalizan y hacen upsert con
`insert().on_conflict_do_update(...)`. Se invocan desde el pipeline
(`stonks update -c <cadencia>`).

**Mercados financieros**
- `sectors.py` — sector GICS en `equity.company` (desde yfinance).
- `constituents.py` — universo S&P 500 point-in-time + deslistadas.
- `fundamentals_pit.py` — SEC EDGAR → `gold.fact_fundamentals_pit`.
- `analyst.py` — snapshots de analistas → `equity.analyst_*`.
- `factors.py` — factores sector-neutral → `gold.fact_factor_scores`.

**Economía mundial**
- `macro_indicators.py` — respuestas macro (IMF/OWID) → `macro.*`.
- `trade.py` — SDMX de WITS → `trade.flow`.
