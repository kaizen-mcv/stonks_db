"""Tests de la capa gold (requieren BD)."""

from conftest import requires_db
from sqlalchemy import text

from stonks.db import engine
from stonks.gold.build import build_gold

pytestmark = requires_db


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
    assert "spy" in metodos
