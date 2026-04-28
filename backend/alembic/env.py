"""Alembic environment — async-aware, reads Settings.database_url."""

import asyncio
import re
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import backend.app.db.models as _models  # noqa: F401
from backend.app.config import get_settings
from backend.app.db.base import Base

# Alembic Config object — gives access to the .ini file values.
config = context.config

# Set up Python logging from the alembic.ini [loggers] section.
# disable_existing_loggers=False keeps the backend.app.* loggers alive after
# alembic configures itself — otherwise fileConfig's default behavior wipes
# them and every lifespan log line after migrations vanishes silently.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _async_url_to_sync(url: str) -> str:
    """Convert an async driver URL to its synchronous equivalent.

    e.g. sqlite+aiosqlite:///... → sqlite:///...
    """
    return re.sub(r"\+aiosqlite", "", url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection).

    Emits the SQL to stdout instead of executing it.
    """
    settings = get_settings()
    # Offline mode uses the sync URL so Alembic can render the DDL.
    url = _async_url_to_sync(settings.database_url)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Execute migrations against an open connection."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode against the configured async engine."""
    settings = get_settings()
    connectable = create_async_engine(
        settings.database_url,
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
