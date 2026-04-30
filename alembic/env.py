"""
alembic/env.py — async-capable migration environment.

Reads DATABASE_URL from the environment (never from alembic.ini hard-coded
credentials).  Imports all SQLAlchemy models so Alembic can autogenerate
accurate diffs.  Replace the existing env.py with this file.
"""
import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# ── Alembic Config object ─────────────────────────────────────────────────
config = context.config

# Override sqlalchemy.url from environment so no credentials live in alembic.ini
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set. "
        "Export it before running alembic commands."
    )
# Alembic's async runner requires the +asyncpg driver
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

config.set_main_option("sqlalchemy.url", database_url)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Import ALL models so autogenerate can diff them ───────────────────────
# Add every new models module here as the project grows.
from app.api.models.base import Base  # noqa: E402  (imports Base.metadata)
import app.api.models.consent         # noqa: F401
import app.api.models.learner         # noqa: F401  (import existing models)
import app.api.models.audit           # noqa: F401

target_metadata = Base.metadata


# ── Offline migration (generates SQL script, no DB connection) ────────────
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online migration (connects to DB, runs migrations) ───────────────────
def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
