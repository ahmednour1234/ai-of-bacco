"""
save_to_db.py  —  Read scraped_products_raw.json and save to scraper_data.db
"""
import asyncio, json, os, sys, decimal
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scraper_data.db")
_SQLITE_URL = f"sqlite+aiosqlite:///{_DB_FILE}"

os.environ.setdefault("SCRAPER_DATABASE_URL", _SQLITE_URL)
os.environ.setdefault("SCRAPER_DATABASE_URL_SYNC", f"sqlite:///{_DB_FILE}")
os.environ.setdefault("DATABASE_URL", _SQLITE_URL)
os.environ.setdefault("DATABASE_URL_SYNC", f"sqlite:///{_DB_FILE}")
os.environ.setdefault("SCRAPER_SYNC_API_URL", "https://api.example.com/v1/products/import")
os.environ.setdefault("SCRAPER_SYNC_API_KEY", "")
os.environ.setdefault("SECRET_KEY", "dev-only-secret")
os.environ.setdefault("OPENAI_API_KEY", "sk-placeholder")

_JSON_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scraped_products_raw.json")


def parse_price(price_data) -> decimal.Decimal | None:
    """Extract price from various Salla price formats."""
    if price_data is None:
        return None
    if isinstance(price_data, (int, float)):
        return decimal.Decimal(str(price_data))
    if isinstance(price_data, dict):
        # Salla format: {"amount": 16.1, "currency": "SAR", ...}
        amt = price_data.get("amount") or price_data.get("price") or price_data.get("regular")
        if amt is not None:
            try:
                return decimal.Decimal(str(amt))
            except Exception:
                return None
    if isinstance(price_data, str):
        try:
            return decimal.Decimal(price_data.replace(",", "").strip())
        except Exception:
            return None
    return None


def extract_name(product: dict) -> str:
    """Extract Arabic/English name from Salla product dict."""
    name = product.get("name") or product.get("title") or ""
    if isinstance(name, dict):
        return name.get("ar") or name.get("en") or str(name)
    return str(name)


def extract_url(product: dict) -> str:
    """Build product URL."""
    url = product.get("url") or product.get("share_link") or ""
    if isinstance(url, dict):
        url = url.get("slug") or url.get("link") or ""
    if url and not url.startswith("http"):
        url = f"https://elburoj.com{url}"
    return str(url)


async def create_tables():
    from sqlalchemy.ext.asyncio import create_async_engine
    from scraper.core.database import ScraperBase
    import scraper.models  # noqa

    engine = create_async_engine(_SQLITE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(ScraperBase.metadata.create_all)
    await engine.dispose()


async def save_products():
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import select
    from scraper.models.source import ScraperSource
    from scraper.models.category import ScraperCategory
    from scraper.models.brand import ScraperBrand
    from scraper.models.product import ScraperProduct

    engine = create_async_engine(_SQLITE_URL, echo=False)
    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    with open(_JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_products = data.get("products", [])
    print(f"Read {len(raw_products)} products from JSON")

    # Remove items with no ID or name
    raw_products = [
        p for p in raw_products
        if p.get("id") and extract_name(p).strip() and extract_name(p) != "—"
    ]
    print(f"After filtering: {len(raw_products)} valid products")

    async with Session() as db:
        # Get or create the El Buroj source
        result = await db.execute(select(ScraperSource).where(ScraperSource.name == "El Buroj"))
        source = result.scalar_one_or_none()
        if not source:
            source = ScraperSource(name="El Buroj", base_url="https://elburoj.com")
            db.add(source)
            await db.flush()

        # Get or create إنارة category
        result = await db.execute(
            select(ScraperCategory).where(
                ScraperCategory.source_id == source.id,
                ScraperCategory.name == "إنارة"
            )
        )
        lighting_cat = result.scalar_one_or_none()
        if not lighting_cat:
            lighting_cat = ScraperCategory(
                source_id=source.id,
                name="إنارة",
                external_id="539403396",
                url="https://elburoj.com/ar/إنارة/c539403396"
            )
            db.add(lighting_cat)
            await db.flush()

        # Brand cache: name → ScraperBrand
        brand_cache: dict[str, ScraperBrand] = {}

        inserted = 0
        updated = 0
        skipped = 0

        for raw in raw_products:
            name = extract_name(raw)
            if not name or name == "—":
                skipped += 1
                continue

            external_id = str(raw.get("id", ""))
            price = parse_price(raw.get("price"))
            sku = str(raw.get("sku") or raw.get("product_number") or "")
            source_url = extract_url(raw)

            # Brand — Salla returns brand as {"id": "...", "name": "...", "url": null}
            brand_data = raw.get("brand")
            if isinstance(brand_data, dict):
                brand_name = (brand_data.get("name") or "").strip()
            else:
                brand_name = str(brand_data or "").strip()
            scraper_brand_id = None
            if brand_name:
                if brand_name not in brand_cache:
                    result = await db.execute(
                        select(ScraperBrand).where(
                            ScraperBrand.source_id == source.id,
                            ScraperBrand.name == brand_name
                        )
                    )
                    brand = result.scalar_one_or_none()
                    if not brand:
                        brand = ScraperBrand(source_id=source.id, name=brand_name)
                        db.add(brand)
                        await db.flush()
                    brand_cache[brand_name] = brand
                scraper_brand_id = brand_cache[brand_name].id

            # Upsert product
            existing = None
            if external_id:
                res = await db.execute(
                    select(ScraperProduct).where(
                        ScraperProduct.source_id == source.id,
                        ScraperProduct.external_id == external_id
                    )
                )
                existing = res.scalar_one_or_none()

            if existing:
                existing.name = name
                existing.price = price
                existing.sku = sku or existing.sku
                existing.source_url = source_url or existing.source_url
                existing.scraper_brand_id = scraper_brand_id or existing.scraper_brand_id
                existing.last_scraped_at = datetime.utcnow()
                updated += 1
            else:
                product = ScraperProduct(
                    source_id=source.id,
                    scraper_category_id=lighting_cat.id,
                    scraper_brand_id=scraper_brand_id,
                    external_id=external_id,
                    source_url=source_url,
                    sku=sku,
                    name=name,
                    price=price,
                    last_scraped_at=datetime.utcnow(),
                )
                db.add(product)
                inserted += 1

        await db.commit()
        print(f"\nSaved to DB: inserted={inserted}, updated={updated}, skipped={skipped}")

    await engine.dispose()


async def show_db():
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import select, func
    from scraper.models.product import ScraperProduct
    from scraper.models.source import ScraperSource
    from scraper.models.brand import ScraperBrand

    engine = create_async_engine(_SQLITE_URL, echo=False)
    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        total = (await db.execute(select(func.count()).select_from(ScraperProduct))).scalar_one()
        with_price = (await db.execute(
            select(func.count()).select_from(ScraperProduct).where(ScraperProduct.price.isnot(None))
        )).scalar_one()
        brands = (await db.execute(select(func.count()).select_from(ScraperBrand))).scalar_one()

        print("\n" + "=" * 70)
        print("  DATABASE CONTENTS — scraper_data.db")
        print("=" * 70)
        print(f"  Total products : {total}")
        print(f"  With price     : {with_price}")
        print(f"  Brands         : {brands}")
        print(f"  DB file        : {_DB_FILE}")
        print("=" * 70)

        # Show latest 30 products
        result = await db.execute(
            select(ScraperProduct).order_by(ScraperProduct.id).limit(50)
        )
        products = result.scalars().all()

        print(f"\n  {'#':<5} {'SKU':<15} {'PRICE (SAR)':>12}  NAME")
        print("  " + "-" * 65)
        for i, p in enumerate(products, 1):
            price_str = f"{p.price:.2f}" if p.price else "—"
            sku_str = (p.sku or "—")[:14]
            name_str = p.name[:45] if p.name else "—"
            print(f"  {i:<5} {sku_str:<15} {price_str:>12}  {name_str}")

        # Brand list
        brand_result = await db.execute(select(ScraperBrand).order_by(ScraperBrand.name))
        brand_list = brand_result.scalars().all()
        if brand_list:
            print(f"\n  BRANDS ({len(brand_list)})")
            print("  " + "-" * 30)
            for b in brand_list:
                print(f"  {b.id:<5} {b.name}")

    await engine.dispose()
    print("\n" + "=" * 70)
    print(f"  Open DB: {_DB_FILE}")
    print("=" * 70)


async def main():
    await create_tables()
    await save_products()
    await show_db()


if __name__ == "__main__":
    asyncio.run(main())
