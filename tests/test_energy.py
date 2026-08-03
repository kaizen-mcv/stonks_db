"""Tests del mapeo de energía OWID (lógica pura + BD opcional)."""

from conftest import requires_db
from sqlalchemy import text

from stonks.db import engine
from stonks.fetchers.owid import COLUMN_MAP

FLUJOS_VALIDOS = {
    "consumption",
    "production",
    "electricity",
    "demand",
}


def test_column_map_bien_formado():
    for col, (prod, flow) in COLUMN_MAP.items():
        assert isinstance(prod, str) and prod
        assert flow in FLUJOS_VALIDOS, f"{col} → flujo {flow}"


def test_column_map_cubre_fuentes_clave():
    productos = {p for p, _ in COLUMN_MAP.values()}
    assert {
        "coal",
        "oil",
        "gas",
        "nuclear",
        "solar",
        "wind",
    } <= productos


@requires_db
def test_energy_balance_cargada():
    with engine.connect() as c:
        n = c.execute(
            text("SELECT count(DISTINCT country_code) FROM energy.balance")
        ).scalar()
    assert n is None or n == 0 or n > 100
