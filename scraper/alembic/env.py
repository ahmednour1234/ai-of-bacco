"""
scraper/alembic/env.py
-----------------------
Alembic environment configuration for the SCRAPER database.

Uses SCRAPER_DATABASE_URL_SYNC (psycopg2) because Alembic's
run_migrations_online() is synchronous.

Run from project root:
    alembic -c scraper/alembic.ini upgrade head
    alembic -c scraper/alembic.ini downgrade base
    alembic -c scraper/alembic.ini revision --autogenerate -m "describe_change"
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# ── Project imports ────────────────────────────────────────────────────────────
# Import ScraperBase so its metadata is populated, then import all scraper
# models so their tables are registered before autogenerate runs.
from app.core.config import get_settings
from scraper.core.database import ScraperBase
import scraper.models  # noqa: F401 — registers all scraper ORM models

# ── Alembic Config ─────────────────────────────────────────────────────────────
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = ScraperBase.metadata

settings = get_settings()

# Override the placeholder URL in scraper/alembic.ini with the real value
# from .env so credentials are never committed to the repository.
_scraper_url = settings.SCRAPER_DATABASE_URL_SYNC
# Ensure utf8mb4 charset for MySQL connections (prevents Arabic collation errors)
if "mysql" in _scraper_url and "charset=" not in _scraper_url:
    _scraper_url += ("&" if "?" in _scraper_url else "?") + "charset=utf8mb4"
config.set_main_option("sqlalchemy.url", _scraper_url)


# ── Offline migrations ─────────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    """Generate SQL without connecting to the DB (useful for review/CI)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        version_table="alembic_version_scraper",
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online migrations (sync engine) ────────────────────────────────────────────
def run_migrations_online() -> None:
    """Run migrations against the live scraper database."""
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
            version_table="alembic_version_scraper",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
