"""Modelos SQLAlchemy para todos los dominios."""

# Importar todos los modelos para registrarlos
# en Base.metadata (orden importa para FKs)
from stonks.models import meta  # noqa: F401
from stonks.models import ref  # noqa: F401
from stonks.models import macro  # noqa: F401
from stonks.models import equity  # noqa: F401
from stonks.models import fixed_income  # noqa: F401
from stonks.models import commodity  # noqa: F401
from stonks.models import forex  # noqa: F401
from stonks.models import crypto  # noqa: F401
from stonks.models import fund  # noqa: F401
from stonks.models import country  # noqa: F401
from stonks.models import alternative  # noqa: F401
