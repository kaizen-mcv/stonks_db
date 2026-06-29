"""Tests del mapeo de sectores Yahoo → GICS (sin red ni BD)."""

from stonks.transform.sectors import YAHOO_TO_GICS, _norm


def test_norm_quita_acentos_y_minusculas():
    assert _norm("  Energía ") == "energia"
    assert _norm("Technology") == "technology"
    assert _norm("") == ""


def test_mapeo_cubre_los_11_sectores_yahoo():
    # Los 11 sectores propios de Yahoo deben tener código GICS nivel 1.
    yahoo = {
        "technology",
        "financial services",
        "healthcare",
        "consumer cyclical",
        "consumer defensive",
        "communication services",
        "industrials",
        "basic materials",
        "energy",
        "utilities",
        "real estate",
    }
    assert yahoo <= set(YAHOO_TO_GICS)


def test_codigos_gics_son_nivel_1():
    # Todos los códigos destino son de 2 dígitos (sector, no industria).
    assert all(len(code) == 2 for code in YAHOO_TO_GICS.values())


def test_mapeos_clave():
    assert YAHOO_TO_GICS[_norm("Technology")] == "45"
    assert YAHOO_TO_GICS[_norm("Financial Services")] == "40"
    assert YAHOO_TO_GICS[_norm("Energy")] == "10"
