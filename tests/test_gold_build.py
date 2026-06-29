"""Tests de la capa gold (requieren BD; se omiten si no hay conexión)."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from stonks.db import engine
from stonks.gold.build import build_gold


def _hay_bd() -> bool:
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        return True
    except OperationalError:
        return False


pytestmark = pytest.mark.skipif(
    not _hay_bd(), reason="sin conexión a stonks_db"
)


def test_build_gold_es_idempotente():
    build_gold()
    with engine.connect() as c:
        d1 = c.execute(text("SELECT count(*) FROM gold.dim_date")).scalar()
        c1 = c.execute(text("SELECT count(*) FROM gold.dim_company")).scalar()
    build_gold()
    with engine.connect() as c:
        d2 = c.execute(text("SELECT count(*) FROM gold.dim_date")).scalar()
        c2 = c.execute(text("SELECT count(*) FROM gold.dim_company")).scalar()
    assert (d1, c1) == (d2, c2)


def test_benchmark_tiene_metodo_spy():
    build_gold()
    with engine.connect() as c:
        metodos = {
            r[0]
            for r in c.execute(
                text("SELECT DISTINCT method FROM gold.mart_benchmark_returns")
            )
        }
    # spy siempre presente; equal_weight aparece tras poblar membership.
    assert "spy" in metodos
