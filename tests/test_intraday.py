"""Tests del sistema intraday (sin BD)."""

from stonks.utils.partitions import (
    INTRADAY_TABLES,
    RETENTION,
)


def test_intraday_tables_completas():
    """4 dominios con tabla intraday."""
    assert len(INTRADAY_TABLES) == 4
    dominios = {t.split(".")[0] for t in INTRADAY_TABLES}
    assert dominios == {
        "equity",
        "crypto",
        "forex",
        "commodity",
    }


def test_retencion_configurada():
    assert RETENTION["1m"] == 30
    assert RETENTION["5m"] == 180
    assert RETENTION["1h"] == 1095


def test_intraday_multi_domain_config():
    from stonks.fetchers.intraday_multi import (
        DOMAIN_CONFIG,
    )

    assert set(DOMAIN_CONFIG) == {
        "crypto",
        "forex",
        "commodity",
    }
    for _domain, cfg in DOMAIN_CONFIG.items():
        assert "upsert_sql" in cfg
        assert "ticker_query" in cfg
        assert "ticker_fmt" in cfg
        assert "tables" in cfg
        assert "has_volume" in cfg


def test_period_map():
    from stonks.fetchers.intraday_multi import PERIOD_MAP

    assert PERIOD_MAP["1m"] == "7d"
    assert PERIOD_MAP["5m"] == "60d"
    assert PERIOD_MAP["1h"] == "730d"


def test_volatility_indices_count():
    from stonks.fetchers.volatility import (
        VOLATILITY_INDICES,
    )

    assert len(VOLATILITY_INDICES) == 12


def test_index_futures_count():
    from stonks.fetchers.index_futures import (
        INDEX_FUTURES,
    )

    assert len(INDEX_FUTURES) == 16
    categorias = {f[3] for f in INDEX_FUTURES}
    assert categorias == {
        "equity",
        "fixed_income",
        "currency",
    }
