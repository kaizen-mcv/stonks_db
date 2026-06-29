# Capa transform

Normalización **bronze → silver/gold** de forma idempotente.

- `base.py` — `BaseTransform`: auditoría en `meta.transform_run`
  (`_start_run` / `_finish_run`) y método abstracto `transform()`.
- `sectors.py` — `SectorTransform`: mapea la taxonomía de sectores de
  yfinance a GICS y puebla `equity.company.sector_id`.

Las subclases leen del origen, normalizan y hacen upsert con
`insert().on_conflict_do_update(...)`. Se invocan desde el pipeline
(`stonks update -c <cadencia>`).

Próximas (fases B/C): `constituents.py`, `fundamentals_pit.py`,
`analyst.py`, `factors.py`.
