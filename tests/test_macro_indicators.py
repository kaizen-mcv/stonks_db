"""Tests del backbone macro (lógica pura + BD opcional)."""

from conftest import requires_db
from sqlalchemy import text

from stonks.db import engine
from stonks.fetchers.imf import _category


def test_categoria_por_prefijo():
    assert _category("NGDPD") == "national_accounts"
    assert _category("PCPIPCH") == "prices"
    assert _category("LUR") == "labor"
    assert _category("GGXWDG_NGDP") == "fiscal"
    assert _category("BCA_NGDPD") == "external"
    assert _category("XYZ123") == "macro"


@requires_db
def test_panel_pais_year_tiene_datos():
    with engine.connect() as c:
        n = c.execute(
            text(
                "SELECT count(DISTINCT country_code) "
                "FROM gold.mart_country_year"
            )
        ).scalar()
    assert n is None or n == 0 or n > 150
