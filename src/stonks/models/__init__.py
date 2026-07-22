"""Modelos SQLAlchemy para todos los dominios."""

# Importar todos los modelos para registrarlos
# en Base.metadata (orden importa para FKs)
from stonks.models import (
    agri,  # noqa: F401
    alternative,  # noqa: F401
    bronze,  # noqa: F401
    commodity,  # noqa: F401
    country,  # noqa: F401
    crypto,  # noqa: F401
    deriv,  # noqa: F401
    energy,  # noqa: F401
    equity,  # noqa: F401
    fixed_income,  # noqa: F401
    forex,  # noqa: F401
    fund,  # noqa: F401
    gold,  # noqa: F401
    macro,  # noqa: F401
    meta,  # noqa: F401
    ref,  # noqa: F401
    trade,  # noqa: F401
)
