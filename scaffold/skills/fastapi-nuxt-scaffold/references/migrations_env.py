"""Alembic async env.py.

Overwrite the file `alembic init -t async migrations` generates with this. It points at the
app's OWN engine (`lib.database.engine`) and metadata (`models.base.Base.metadata`) instead of
a URL/metadata hardcoded in `alembic.ini` -- one source of truth for the connection string.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import AsyncConnection

import models  # noqa: F401 -- import every model module so Base.metadata sees all tables
from lib.database import engine
from models.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL without a live DB connection."""
    # hide_password=False: offline mode's output is meant to be inspected/run manually, and
    # str(engine.url) masks the password by default -- that would silently break this.
    context.configure(
        url=engine.url.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: AsyncConnection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations using the app's own async engine."""
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
