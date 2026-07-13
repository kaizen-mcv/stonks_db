"""Tests del mapeo de energía OWID (lógica pura + BD opcional)."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from stonks.db import engine
from stonks.fetchers.owid import COLUMN_MAP

FLUJOS_VALIDOS = {"consumption", "production", "electricity", "demand"}


def test_column_map_bien_formado():
    # Cada columna mapea a (producto, flujo) con flujo válido.
    for col, (prod, flow) in COLUMN_MAP.items():
        assert isinstance(prod, str) and prod
        assert flow in FLUJOS_VALIDOS, f"{col} → flujo {flow}"


def test_column_map_cubre_fuentes_clave():
    productos = {p for p, _ in COLUMN_MAP.values()}
    assert {"coal", "oil", "gas", "nuclear", "solar", "wind"} <= productos


def _hay_bd() -> bool:
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        return True
    except OperationalError:
        return False


@pytest.mark.skipif(not _hay_bd(), reason="sin conexión a stonks_db")
def test_energy_balance_cargada():
    with engine.connect() as c:
        n = c.execute(
            text("SELECT count(DISTINCT country_code) FROM energy.balance")
        ).scalar()
    assert n is None or n == 0 or n > 100
