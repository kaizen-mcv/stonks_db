"""Tests de la clasificación de periodos PIT (lógica pura)."""

from stonks.transform.fundamentals_pit import _classify_period, _quarter


def test_quarter_desde_fp():
    assert _quarter("FY") is None
    assert _quarter(None) is None
    assert _quarter("Q1") == 1
    assert _quarter("Q4") == 4


def test_clasifica_anual_por_duracion():
    # ~365 días → anual (fiscal_quarter None)
    assert _classify_period("2020-01-01", "2020-12-31", "FY") == (True, None)


def test_clasifica_trimestral_por_duracion():
    # ~90 días con fp Q2 → trimestral
    assert _classify_period("2020-01-01", "2020-03-31", "Q1") == (True, 1)


def test_descarta_acumulado_6m():
    # ~180 días (semestre acumulado) → se descarta
    assert _classify_period("2020-01-01", "2020-06-30", "Q2") is None


def test_trimestral_sin_quarter_se_descarta():
    # 90 días pero fp no da trimestre → no se puede clasificar
    assert _classify_period("2020-01-01", "2020-03-31", "FY") is None


def test_instantaneo_balance_usa_fp():
    # Sin 'start' (concepto instantáneo de balance): periodo lo da fp.
    assert _classify_period(None, "2020-12-31", "FY") == (True, None)
    assert _classify_period(None, "2020-03-31", "Q1") == (True, 1)
