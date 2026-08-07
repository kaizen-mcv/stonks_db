"""Entorno Alembic para stonks_db.

La URL de conexión y los metadatos se toman del propio proyecto
(`stonks.config.settings` y `stonks.db.Base`), no de alembic.ini, para
que exista una única fuente de verdad.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from stonks.config import settings
from stonks.db import SCHEMAS, Base

# Importar todos los modelos registra las tablas en Base.metadata.
import stonks.models  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# La tabla de versiones vive en `meta`, junto al resto de metadatos
# operativos del proyecto.
VERSION_TABLE_SCHEMA = "meta"


def include_name(name, type_, parent_names):
    """Limitar el autogenerate a los esquemas del proyecto."""
    if type_ == "schema":
        return name in SCHEMAS
    return True


def include_object(obj, name, type_, reflected, compare_to):
    """Excluir del autogenerate lo que se gestiona fuera de Alembic.

    Las particiones de intraday las crea `stonks.utils.partitions` y
    las vistas materializadas las construye `stonks.gold.build`; ni
    unas ni otras son tablas declarativas.
    """
    if type_ == "table" and "_intraday_" in name:
        return False
    if type_ == "table" and (name.startswith("mart_") or name.endswith("_mv")):
        return False
    return True


def run_migrations_offline() -> None:
    """Generar SQL sin conectar a la base de datos."""
    context.configure(
        url=settings.db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_name=include_name,
        include_object=include_object,
        version_table_schema=VERSION_TABLE_SCHEMA,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplicar migraciones contra la base de datos."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=include_name,
            include_object=include_object,
            version_table_schema=VERSION_TABLE_SCHEMA,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
