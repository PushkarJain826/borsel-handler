"""Alembic environment configuration for synchronous migrations."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from borsel.core.config import settings
from borsel.db.base import Base

# Import models package as the model discovery entry point so all models
# are registered with Base.metadata before migrations inspect the metadata.
import borsel.models  # noqa: F401

# ---------- Alembic Config object ------------------------------------------
config = context.config

# Configure Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Derive a synchronous URL from the application's async DATABASE_URL.
# postgresql+asyncpg://... → postgresql+psycopg://...
sync_url = settings.DATABASE_URL.replace("+asyncpg", "+psycopg")
config.set_main_option("sqlalchemy.url", sync_url)

# SQLAlchemy MetaData — Alembic uses this to detect schema changes.
target_metadata = Base.metadata

BORSEL_SCHEMAS = {
    "reference",
    "market",
    "corporate",
    "ingestion",
    "quality",
    "fundamentals",
    "system",
    "public",
}


def include_object(object, name, type_, reflected, compare_to):
    """Filter out non-application schemas (e.g. TimescaleDB internal catalogs)."""
    if type_ == "table":
        schema = getattr(object, "schema", None) or "public"
        return schema in BORSEL_SCHEMAS
    return True


# ---------- Offline mode ---------------------------------------------------
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Generates SQL scripts without connecting to the database.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------- Online mode ----------------------------------------------------
def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Creates a synchronous engine and runs migrations inside a transaction.
    """
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
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


# ---------- Entry point ----------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
