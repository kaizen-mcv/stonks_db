"""Motor SQLAlchemy y gestión de sesiones."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
    sessionmaker,
)

from stonks.config import settings

# Todos los esquemas PostgreSQL del proyecto
SCHEMAS = [
    "meta",
    "ref",
    "macro",
    "equity",
    "fi",
    "commodity",
    "forex",
    "crypto",
    "deriv",
    "fund",
    "realestate",
    "alt",
    "calendar",
    "country",
]

engine = create_engine(
    settings.db_url,
    echo=False,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_session() -> Session:
    """Crear una sesión de base de datos."""
    return SessionLocal()


def create_schemas() -> None:
    """Crear los esquemas PostgreSQL."""
    with engine.connect() as conn:
        for schema in SCHEMAS:
            conn.execute(
                text(f"CREATE SCHEMA IF NOT EXISTS {schema}")
            )
        conn.commit()


def init_db() -> None:
    """Crear esquemas y todas las tablas."""
    import stonks.models  # noqa: F401
    create_schemas()
    Base.metadata.create_all(bind=engine)


def drop_db() -> None:
    """Borrar todas las tablas y esquemas."""
    import stonks.models  # noqa: F401
    Base.metadata.drop_all(bind=engine)
    with engine.connect() as conn:
        for schema in reversed(SCHEMAS):
            conn.execute(
                text(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
            )
        conn.commit()
