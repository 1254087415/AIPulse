"""Alembic migration environment."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import hotspot models so their tables are registered in Base.metadata for
# Alembic autogenerate.
import aipulse.hotspot.models  # noqa: F401
from aipulse.core.config import get_settings
from aipulse.store.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
settings = get_settings()

# Alembic migrations run with a synchronous engine, so async driver URLs
# used by the application must be mapped to their synchronous equivalents.
_SYNC_DRIVER_REPLACEMENTS: dict[str, str] = {
    "+aiosqlite": "",
    "+aiomysql": "+pymysql",
}


def _to_sync_url(url: str) -> str:
    """Return a synchronous SQLAlchemy URL for the given async URL."""
    for async_suffix, sync_suffix in _SYNC_DRIVER_REPLACEMENTS.items():
        if async_suffix in url:
            return url.replace(async_suffix, sync_suffix, 1)
    return url


config.set_main_option("sqlalchemy.url", _to_sync_url(settings.database_url))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
