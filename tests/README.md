# Tests

Suite con `pytest`. Ejecutar desde la raíz del proyecto:

```bash
.venv/bin/pytest
```

- `test_sectors.py` — mapeo Yahoo → GICS (lógica pura, sin red ni BD).
- `test_pipeline.py` — orquestador en `--dry-run` (sin BD).
- `test_gold_build.py` — `build_gold()` idempotente y benchmark
  (requiere conexión a `stonks_db`; se omite si no hay BD).

Requiere instalar el extra dev: `pip install -e ".[dev]"`.
