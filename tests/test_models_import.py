"""Test de importación de todos los modelos."""

from stonks.db import Base


def test_todos_los_modelos_registrados():
    import stonks.models  # noqa: F401

    tablas = Base.metadata.tables
    assert len(tablas) >= 65, f"Solo {len(tablas)} tablas registradas"


def test_schemas_esperados():
    import stonks.models  # noqa: F401

    schemas = {t.schema for t in Base.metadata.tables.values() if t.schema}
    esperados = {
        "ref",
        "meta",
        "equity",
        "crypto",
        "forex",
        "fund",
        "commodity",
        "macro",
        "fi",
        "trade",
        "bronze",
        "gold",
        "energy",
        "agri",
        "country",
        "deriv",
        "alt",
    }
    faltantes = esperados - schemas
    assert not faltantes, f"Schemas faltantes: {faltantes}"


def test_tablas_intraday_registradas():
    """Las tablas intraday particionadas existen."""
    import stonks.models  # noqa: F401

    tablas = set(Base.metadata.tables.keys())
    esperadas = {
        "equity.price_intraday",
        "crypto.price_intraday",
        "forex.rate_intraday",
        "commodity.price_intraday",
    }
    faltantes = esperadas - tablas
    assert not faltantes, f"Tablas intraday faltantes: {faltantes}"


def test_tablas_deriv_registradas():
    """Los modelos de derivados existen."""
    import stonks.models  # noqa: F401

    tablas = set(Base.metadata.tables.keys())
    esperadas = {
        "deriv.volatility_index",
        "deriv.volatility_daily",
        "deriv.futures_contract",
        "deriv.futures_daily",
    }
    faltantes = esperadas - tablas
    assert not faltantes, f"Tablas deriv faltantes: {faltantes}"
