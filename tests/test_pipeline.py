"""Tests del orquestador del pipeline (dry-run, sin BD)."""

from stonks.pipeline import CADENCES, PIPELINE, run_update


def test_cadencias_definidas():
    assert set(CADENCES) == {"daily", "weekly", "monthly"}
    assert set(PIPELINE) == set(CADENCES)


def test_weekly_incluye_sectores():
    nombres = [s.name for s in PIPELINE["weekly"]]
    assert "sectors" in nombres


def test_dry_run_no_construye_gold():
    # En dry-run cada paso queda marcado y no se reconstruye gold.
    resumen = run_update("weekly", dry_run=True, build=True)
    assert resumen.get("sectors") == "dry-run"
    assert "gold" not in resumen
