"""Tests del orquestador del pipeline (dry-run, sin BD)."""

from stonks.pipeline import CADENCES, PIPELINE, run_update


def test_cadencias_definidas():
    assert set(CADENCES) == {
        "daily",
        "weekly",
        "monthly",
        "yearly",
    }
    assert set(PIPELINE) == set(CADENCES)


def test_yearly_incluye_imf_macro():
    nombres = [s.name for s in PIPELINE["yearly"]]
    assert "imf-macro" in nombres


def test_weekly_incluye_sectores():
    nombres = [s.name for s in PIPELINE["weekly"]]
    assert "sectors" in nombres


def test_daily_incluye_volatility():
    nombres = [s.name for s in PIPELINE["daily"]]
    assert "volatility" in nombres


def test_daily_incluye_index_futures():
    nombres = [s.name for s in PIPELINE["daily"]]
    assert "index-futures" in nombres


def test_daily_incluye_intraday_multi():
    nombres = [s.name for s in PIPELINE["daily"]]
    assert "intraday-crypto-1h" in nombres
    assert "intraday-forex-1h" in nombres
    assert "intraday-commodity-1h" in nombres


def test_daily_tiene_8_pasos():
    assert len(PIPELINE["daily"]) == 8


def test_dry_run_no_construye_gold():
    resumen = run_update("weekly", dry_run=True, build=True)
    assert resumen.get("sectors") == "dry-run"
    assert "gold" not in resumen
