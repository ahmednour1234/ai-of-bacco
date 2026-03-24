"""
alembic/env.py
---------------
Async-compatible Alembic environment configuration.

Uses the SYNC database URL from Settings (asyncpg → psycopg2) because
Alembic's run_migrations_online() is synchronous by default.
For fully async migrations, swap to alembic_utils async runner.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

# ── Project imports ────────────────────────────────────────────────────────────
# Ensure all models are imported so their metadata is populated before
# autogenerate inspects Base.metadata.
from app.core.config import get_settings
from app.core.database import Base
import app.models  # noqa: F401 — registers all ORM models on Base.metadata

# ── Alembic Config ─────────────────────────────────────────────────────────────
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

settings = get_settings()

# Override alembic.ini sqlalchemy.url with the value from .env so we never
# commit credentials to the repository.
# Use DATABASE_URL_SYNC (psycopg2) for synchronous migrations.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL_SYNC)


# ── Offline migrations ─────────────────────────────────────────────────────────

def run_migrations_offline() -> None:
    """Generate SQL without connecting to the DB (useful for review)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online migrations (sync engine) ────────────────────────────────────────────

def run_migrations_online() -> None:
    """Run migrations against a live database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
