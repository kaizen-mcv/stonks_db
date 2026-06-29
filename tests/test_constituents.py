"""Tests de la reconstrucción de membership (lógica pura, sin red ni BD)."""

from datetime import date

from stonks.transform.constituents import (
    MembershipTransform,
    _to_date,
    _yahoo_ticker,
)


def test_to_date():
    assert _to_date("2020-01-15") == date(2020, 1, 15)
    assert _to_date("") is None
    assert _to_date(None) is None


def test_yahoo_ticker_normaliza_punto():
    assert _yahoo_ticker("BRK.B") == "BRK-B"
    assert _yahoo_ticker("BF.B") == "BF-B"
    assert _yahoo_ticker("AAPL") == "AAPL"


def test_group_by_ticker_maneja_reentradas():
    # AAL entra y sale dos veces (reentrada).
    rows = [
        ["AAL", "1996-01-02", "1997-01-15"],
        ["AAL", "2015-03-23", "2024-09-23"],
        ["ZTS", "2013-06-24", ""],
    ]
    grouped = MembershipTransform._group_by_ticker(rows)
    assert len(grouped["AAL"]) == 2
    # ZTS sigue siendo miembro actual (end_date None).
    assert grouped["ZTS"] == [(date(2013, 6, 24), None)]


def test_miembro_actual_detectado():
    rows = [["ZTS", "2013-06-24", ""]]
    grouped = MembershipTransform._group_by_ticker(rows)
    ivals = grouped["ZTS"]
    is_current = any(end is None for _, end in ivals)
    assert is_current is True
