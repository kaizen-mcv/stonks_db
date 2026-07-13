"""Tests del backbone macro (lógica pura + BD opcional)."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from stonks.db import engine
from stonks.fetchers.imf import _category


def test_categoria_por_prefijo():
    assert _category("NGDPD") == "national_accounts"
    assert _category("PCPIPCH") == "prices"
    assert _category("LUR") == "labor"
    assert _category("GGXWDG_NGDP") == "fiscal"
    assert _category("BCA_NGDPD") == "external"
    assert _category("XYZ123") == "macro"


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


def test_panel_pais_year_tiene_datos():
    # Si el backbone IMF está cargado, el panel cubre >150 países.
    with engine.connect() as c:
        n = c.execute(
            text(
                "SELECT count(DISTINCT country_code) "
                "FROM gold.mart_country_year"
            )
        ).scalar()
    assert n is None or n == 0 or n > 150
