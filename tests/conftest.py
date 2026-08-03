"""Fixtures y marcas compartidas para tests."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from stonks.db import engine


def hay_bd() -> bool:
    """Comprueba si stonks_db está accesible."""
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        return True
    except OperationalError:
        return False


requires_db = pytest.mark.skipif(
    not hay_bd(), reason="sin conexión a stonks_db"
)


@pytest.fixture
def db_conn():
    """Conexión a BD para tests que lo necesiten."""
    with engine.connect() as conn:
        yield conn
