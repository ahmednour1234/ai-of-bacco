"""
run_scraper.py
---------------
Standalone runner for the El Buroj scraper.
Uses SQLite so NO PostgreSQL / .env configuration is required.

Usage (from project root):
    .\.venv\Scripts\python run_scraper.py

What it does:
    1. Creates a local SQLite file: scraper_data.db
    2. Creates all scraper tables
    3. Runs the El Buroj lighting-category scraper
    4. Prints a summary table of scraped products

The SQLite file is created in the project root and can be opened with
any SQLite viewer (DB Browser for SQLite, DBeaver, TablePlus, etc.).
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

# ── Add project root to sys.path so "scraper.*" and "app.*" are importable ────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Override database URLs BEFORE importing any app/scraper module ─────────────
# This bypasses the .env and any PostgreSQL requirement.
_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scraper_data.db")
_SQLITE_URL = f"sqlite+aiosqlite:///{_DB_FILE}"
_SQLITE_URL_SYNC = f"sqlite:///{_DB_FILE}"

os.environ.setdefault("SCRAPER_DATABASE_URL", _SQLITE_URL)
os.environ.setdefault("SCRAPER_DATABASE_URL_SYNC", _SQLITE_URL_SYNC)
# These are required by pydantic-settings but not used by the scraper
os.environ.setdefault("DATABASE_URL", _SQLITE_URL)
os.environ.setdefault("DATABASE_URL_SYNC", _SQLITE_URL_SYNC)
os.environ.setdefault("SCRAPER_SYNC_API_URL", "https://api.example.com/v1/products/import")
os.environ.setdefault("SCRAPER_SYNC_API_KEY", "")
os.environ.setdefault("SECRET_KEY", "dev-only-secret")
os.environ.setdefault("OPENAI_API_KEY", "sk-placeholder")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_scraper")


async def create_tables() -> None:
    """Create all scraper tables via SQLAlchemy (no Alembic needed for SQLite)."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from scraper.core.database import ScraperBase
    import scraper.models  # noqa: F401 — register all models

    engine = create_async_engine(_SQLITE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(ScraperBase.metadata.create_all)
    await engine.dispose()
    logger.info("Tables created in %s", _DB_FILE)


async def run_scraper() -> dict:
    """Run the El Buroj scraper and return stats."""
    # Monkey-patch the scraper engine to use SQLite
    import scraper.core.database as _db_module
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

    engine = create_async_engine(_SQLITE_URL, echo=False)
    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    from scraper.scrapers.elburoj_scraper import ElBurojScraper

    async with Session() as db:
        scraper_instance = ElBurojScraper(db)
        stats = await scraper_instance.run()

    await engine.dispose()
    return stats


async def show_results() -> None:
    """Query the database and print the results as a formatted table."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import select, func, text
    from scraper.models.product import ScraperProduct
    from scraper.models.source import ScraperSource
    from scraper.models.category import ScraperCategory
    from scraper.models.brand import ScraperBrand

    engine = create_async_engine(_SQLITE_URL, echo=False)
    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        # ── Counts ─────────────────────────────────────────────────────────────
        total_products = (await db.execute(select(func.count()).select_from(ScraperProduct))).scalar_one()
        total_sources = (await db.execute(select(func.count()).select_from(ScraperSource))).scalar_one()
        total_categories = (await db.execute(select(func.count()).select_from(ScraperCategory))).scalar_one()
        total_brands = (await db.execute(select(func.count()).select_from(ScraperBrand))).scalar_one()
        with_price = (await db.execute(
            select(func.count()).select_from(ScraperProduct).where(ScraperProduct.price.isnot(None))
        )).scalar_one()

        print("\n" + "═" * 70)
        print("  SCRAPER DATABASE SUMMARY")
        print("═" * 70)
        print(f"  Sources      : {total_sources}")
        print(f"  Categories   : {total_categories}")
        print(f"  Brands       : {total_brands}")
        print(f"  Products     : {total_products}")
        print(f"  With price   : {with_price}")
        print(f"  DB file      : {_DB_FILE}")
        print("═" * 70)

        # ── Latest 20 products ──────────────────────────────────────────────────
        result = await db.execute(
            select(ScraperProduct).order_by(ScraperProduct.id.desc()).limit(20)
        )
        products = result.scalars().all()

        if not products:
            print("\n  No products scraped yet.\n")
            return

        print(f"\n  LATEST {len(products)} PRODUCTS\n")
        print(f"  {'ID':<10} {'PRICE':>8}  {'SKU':<18}  NAME")
        print("  " + "-" * 66)
        for p in products:
            price_str = f"{p.price:.2f}" if p.price else "—"
            sku_str = (p.sku or "—")[:17]
            name_str = p.name[:45] if p.name else "—"
            print(f"  {str(p.id):<10} {price_str:>8}  {sku_str:<18}  {name_str}")

        # ── Brands found ────────────────────────────────────────────────────────
        brands_result = await db.execute(select(ScraperBrand).order_by(ScraperBrand.name))
        brands = brands_result.scalars().all()
        if brands:
            print(f"\n  BRANDS FOUND ({len(brands)})")
            print("  " + "-" * 30)
            for b in brands:
                print(f"  {b.id:<5} {b.name}")

    await engine.dispose()
    print("\n" + "═" * 70)
    print(f"  Open with SQLite viewer: {_DB_FILE}")
    print("═" * 70 + "\n")


async def main() -> None:
    print("\n" + "═" * 70)
    print("  EL BUROJ SCRAPER — elburoj.com/ar/إنارة/c539403396")
    print("═" * 70)
    print(f"  Database : SQLite  →  {_DB_FILE}")
    print("═" * 70 + "\n")

    await create_tables()

    logger.info("Starting scraper …")
    stats = await run_scraper()

    print("\n" + "═" * 70)
    print("  SCRAPE COMPLETE")
    print("═" * 70)
    print(f"  Scraped  : {stats.get('scraped', 0)}")
    print(f"  Inserted : {stats.get('inserted', 0)}")
    print(f"  Updated  : {stats.get('updated', 0)}")
    print(f"  Errors   : {stats.get('errors', 0)}")

    await show_results()


if __name__ == "__main__":
    asyncio.run(main())
