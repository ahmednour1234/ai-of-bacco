"""
scrape_schneider.py  (Playwright version)
------------------------------------------
Scrapes ALL products from Schneider Electric Saudi Arabia e-shop.
https://eshop.se.com/sa/  — Magento 2 (JS-rendered, requires Playwright).

Strategy:
  • Playwright intercepts /rest/V1/products/serviceability/ → gets SKU + prices
  • DOM extraction → gets product name, URL, category
  • Paginates via ?p=N until no more pages
  • Saves to scraper_data.db after every page (live visibility)
  • --resume flag: skips already-saved SKUs

Usage:
    .\.venv\Scripts\python scrape_schneider.py
    .\.venv\Scripts\python scrape_schneider.py --resume
"""
import asyncio
import json
import re
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scraper_data.db")
os.environ.setdefault("SCRAPER_DATABASE_URL",      f"sqlite+aiosqlite:///{_DB_FILE}")
os.environ.setdefault("SCRAPER_DATABASE_URL_SYNC", f"sqlite:///{_DB_FILE}")
os.environ.setdefault("DATABASE_URL",              f"sqlite+aiosqlite:///{_DB_FILE}")
os.environ.setdefault("DATABASE_URL_SYNC",         f"sqlite:///{_DB_FILE}")
os.environ.setdefault("SCRAPER_SYNC_API_URL",      "https://api.example.com")
os.environ.setdefault("SCRAPER_SYNC_API_KEY",      "")
os.environ.setdefault("SECRET_KEY",                "dev-only-secret")
os.environ.setdefault("OPENAI_API_KEY",            "sk-placeholder")

from playwright.async_api import async_playwright, Page, BrowserContext

BASE_URL    = "https://eshop.se.com/sa"
SOURCE_NAME = "SchneiderElectric"
BRAND_NAME  = "Schneider Electric"

# Top-level categories (JS-rendered nav, verified from page content)
TOP_CATEGORIES = [
    {"name": "Industrial Automation and Control",
     "url":  "https://eshop.se.com/sa/all-products/industrial-automation-and-control.html"},
    {"name": "Low Voltage Products and Systems",
     "url":  "https://eshop.se.com/sa/all-products/low-voltage-products-and-systems.html"},
    {"name": "Residential and Small Business",
     "url":  "https://eshop.se.com/sa/all-products/residential-and-small-business.html"},
    {"name": "APC By Schneider Electric",
     "url":  "https://eshop.se.com/sa/all-products/apc.html"},
    {"name": "EV Chargers",
     "url":  "https://eshop.se.com/sa/all-products/ev-chargers.html"},
    {"name": "KNX",
     "url":  "https://eshop.se.com/sa/all-products/knx-products.html"},
    {"name": "Services",
     "url":  "https://eshop.se.com/sa/all-products/services.html"},
    {"name": "New Products and Offers",
     "url":  "https://eshop.se.com/sa/all-products/new-products-and-offers.html"},
    {"name": "Bundles",
     "url":  "https://eshop.se.com/sa/all-products/bundle-categories.html"},
]


# ─── helpers ──────────────────────────────────────────────────────────────────

def parse_sar(text: str) -> float | None:
    """'SAR 1,234.56' or '1,234.56' → 1234.56"""
    if not text:
        return None
    clean = re.sub(r"[^\d.]", "", text.replace(",", ""))
    try:
        v = float(clean)
        return v if v > 0 else None
    except ValueError:
        return None


# ─── intercept serviceability API ────────────────────────────────────────────

def attach_price_interceptor(page: Page, price_map: dict):
    """Populate price_map from /rest/V1/products/serviceability/ responses."""
    async def handle_response(response):
        if "serviceability" in response.url and response.status == 200:
            try:
                data = await response.json()
                for item in data:
                    sku = (item.get("sku") or "").upper()
                    if sku:
                        price_map[sku] = {
                            "orig_price":    item.get("orig_price"),
                            "special_price": item.get("special_price"),
                        }
            except Exception:
                pass
    page.on("response", handle_response)


# ─── scrape one listing page ──────────────────────────────────────────────────

async def scrape_page(
    page: Page,
    url: str,
    cat_name: str,
    cat_url: str,
    price_map: dict,
) -> tuple[list[dict], str | None]:
    price_map.clear()

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except Exception as e:
        print(f"    [goto error] {e}")
        return [], None

    # Wait for product cards to render (form.product_addtocart_form)
    try:
        await page.wait_for_selector("form.product_addtocart_form", timeout=15000)
    except Exception:
        await page.wait_for_timeout(6000)

    # Scroll to trigger lazy-loaded prices
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await page.wait_for_timeout(2000)

    # Extract from DOM via JS
    # Card selector: form.product_addtocart_form (Magento 2 Tailwind theme)
    products_raw = await page.evaluate("""() => {
        const items = [];
        document.querySelectorAll('form.product_addtocart_form').forEach(card => {
            // URL + Name: a.product-item-link
            const linkEl = card.querySelector('a.product-item-link');
            const name = linkEl ? linkEl.textContent.trim() : '';
            const url  = linkEl ? linkEl.getAttribute('href') : '';

            // SKU: .product-card-num div
            const skuEl = card.querySelector('.product-card-num') ||
                          card.querySelector('[class*=card-num]') ||
                          card.querySelector('[class*=serial]');
            const sku = skuEl ? skuEl.textContent.trim() : '';

            // Price: data-price-amount on finalPrice span (most accurate)
            const finalPriceEl = card.querySelector('[data-price-type="finalPrice"]');
            const finalPrice = finalPriceEl
                ? parseFloat(finalPriceEl.getAttribute('data-price-amount') || '0')
                : 0;
            const oldPriceEl = card.querySelector('[data-price-type="oldPrice"]');
            const oldPrice = oldPriceEl
                ? parseFloat(oldPriceEl.getAttribute('data-price-amount') || '0')
                : 0;

            // Image
            const imgEl = card.querySelector('img.product-image-photo') || card.querySelector('img');
            const img = imgEl ? (imgEl.getAttribute('src') || '') : '';

            if (url) items.push({ name, url, sku,
                price: finalPrice > 0 ? finalPrice : null,
                original_price: oldPrice > 0 && oldPrice !== finalPrice ? oldPrice : null,
                img });
        });
        return items;
    }""")

    products = []
    for raw in products_raw:
        name = raw.get("name", "").strip()
        product_url = raw.get("url", "").strip()
        if not product_url:
            continue

        # SKU from card, fallback to URL slug
        sku = raw.get("sku", "").strip()
        if not sku:
            slug = product_url.rstrip("/").split("/")[-1]
            sku = re.sub(r"\.html$", "", slug).upper()
        external_id = sku

        # Prices come directly from data-price-amount attributes
        price = raw.get("price")
        original_price = raw.get("original_price")

        # Override with intercepted API prices if available (more reliable)
        api = price_map.get(sku.upper())
        if api:
            sp = api.get("special_price")
            op = api.get("orig_price")
            if sp:
                price = sp
                original_price = op
            elif op:
                price = op

        products.append({
            "external_id":    external_id,
            "sku":            sku,
            "name":           name,
            "price":          price,
            "original_price": original_price,
            "source_url":     product_url,
            "image_url":      raw.get("img", ""),
            "_category_name": cat_name,
            "_category_url":  cat_url,
        })

    # Next page link
    next_url = await page.evaluate("""() => {
        const el = document.querySelector('a.next') ||
                   document.querySelector('a[rel="next"]') ||
                   document.querySelector('.action.next') ||
                   document.querySelector('li.pages-item-next a') ||
                   document.querySelector('a[aria-label="Next"]') ||
                   Array.from(document.querySelectorAll('a')).find(a =>
                       a.textContent.trim() === 'Next' || a.getAttribute('aria-label') === 'Next'
                   );
        return el ? el.getAttribute('href') : null;
    }""")

    return products, next_url


# ─── scrape full category ─────────────────────────────────────────────────────

async def scrape_category(
    ctx: BrowserContext,
    category: dict,
    already_scraped: set[str],
    save_fn,
) -> int:
    cat_name = category["name"]
    cat_url  = category["url"]
    page_url = cat_url + "?product_list_limit=48"
    page_num = 1
    cat_total = 0
    price_map: dict = {}

    page = await ctx.new_page()
    attach_price_interceptor(page, price_map)

    try:
        while page_url:
            print(f"    Page {page_num}: {page_url}")
            products, next_url = await scrape_page(page, page_url, cat_name, cat_url, price_map)

            new = [p for p in products if p["external_id"] not in already_scraped]
            for p in new:
                already_scraped.add(p["external_id"])

            print(f"      → {len(products)} found, {len(new)} new")

            if new:
                ins, upd, skip = save_fn(new)
                print(f"      DB → inserted={ins}, updated={upd}")
                cat_total += ins + upd

            if not next_url or next_url == page_url:
                break

            if "product_list_limit" not in next_url:
                sep = "&" if "?" in next_url else "?"
                next_url = f"{next_url}{sep}product_list_limit=48"
            page_url = next_url
            page_num += 1

    finally:
        await page.close()

    print(f"    [{cat_name}] total saved this run: {cat_total}")
    return cat_total


# ─── save to SQLite ───────────────────────────────────────────────────────────

def save_to_sqlite(all_products: list[dict]) -> tuple[int, int, int]:
    from scraper.models.source import ScraperSource
    from scraper.models.category import ScraperCategory
    from scraper.models.brand import ScraperBrand
    from scraper.models.product import ScraperProduct
    from scraper.core.database import ScraperBase
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from datetime import datetime

    engine = create_engine(f"sqlite:///{_DB_FILE}", echo=False)
    ScraperBase.metadata.create_all(engine)

    inserted = updated = skipped = 0

    with Session(engine) as session:
        source = session.execute(
            select(ScraperSource).where(ScraperSource.name == SOURCE_NAME)
        ).scalar_one_or_none()
        if not source:
            source = ScraperSource(name=SOURCE_NAME, base_url=BASE_URL, active=True)
            session.add(source)
            session.flush()

        brand_cache: dict[str, ScraperBrand] = {}
        cat_cache: dict[str, ScraperCategory] = {}

        def get_brand(name: str) -> ScraperBrand:
            if name not in brand_cache:
                b = session.execute(
                    select(ScraperBrand).where(
                        ScraperBrand.source_id == source.id,
                        ScraperBrand.name == name,
                    )
                ).scalar_one_or_none()
                if not b:
                    b = ScraperBrand(source_id=source.id, name=name)
                    session.add(b)
                    session.flush()
                brand_cache[name] = b
            return brand_cache[name]

        def get_category(name: str, url: str) -> ScraperCategory:
            if name not in cat_cache:
                c = session.execute(
                    select(ScraperCategory).where(
                        ScraperCategory.source_id == source.id,
                        ScraperCategory.name == name,
                    )
                ).scalar_one_or_none()
                if not c:
                    slug = re.sub(r"https?://[^/]+", "", url).strip("/")
                    c = ScraperCategory(source_id=source.id, name=name,
                                        external_id=slug, url=url)
                    session.add(c)
                    session.flush()
                cat_cache[name] = c
            return cat_cache[name]

        for raw in all_products:
            name = raw.get("name", "").strip()
            if not name:
                skipped += 1
                continue

            external_id = raw.get("external_id", "")
            sku         = raw.get("sku", "") or external_id
            price       = raw.get("price")
            source_url  = raw.get("source_url", "")
            cat_name    = raw.get("_category_name", "General")
            cat_url_v   = raw.get("_category_url", "")

            category = get_category(cat_name, cat_url_v)
            brand    = get_brand(BRAND_NAME)
            raw_json = json.dumps(raw, ensure_ascii=False, default=str)

            existing = None
            if external_id:
                existing = session.execute(
                    select(ScraperProduct).where(
                        ScraperProduct.source_id == source.id,
                        ScraperProduct.external_id == external_id,
                    )
                ).scalar_one_or_none()

            if existing:
                existing.name                = name
                existing.sku                 = sku
                existing.price               = price
                existing.source_url          = source_url
                existing.scraper_category_id = category.id
                existing.scraper_brand_id    = brand.id
                existing.raw_data            = raw_json
                existing.last_scraped_at     = datetime.now()
                updated += 1
            else:
                session.add(ScraperProduct(
                    source_id=source.id,
                    external_id=external_id,
                    sku=sku,
                    name=name,
                    price=price,
                    source_url=source_url,
                    scraper_category_id=category.id,
                    scraper_brand_id=brand.id,
                    raw_data=raw_json,
                    last_scraped_at=datetime.now(),
                    is_synced=False,
                ))
                inserted += 1

        session.commit()

    return inserted, updated, skipped


def load_already_scraped() -> set[str]:
    import sqlite3
    if not os.path.exists(_DB_FILE):
        return set()
    try:
        con = sqlite3.connect(_DB_FILE)
        cur = con.cursor()
        cur.execute("""
            SELECT sp.external_id FROM scraper_products sp
            JOIN scraper_sources ss ON sp.source_id = ss.id
            WHERE ss.name = ?
        """, (SOURCE_NAME,))
        ids = {r[0] for r in cur.fetchall() if r[0]}
        con.close()
        return ids
    except Exception:
        return set()


# ─── main ─────────────────────────────────────────────────────────────────────

async def main(resume: bool = False):
    print("=" * 65)
    print("  SCHNEIDER ELECTRIC SA — FULL SITE SCRAPER")
    print("  (Playwright — JS-rendered Magento 2)")
    print("=" * 65)

    already_scraped: set[str] = set()
    if resume:
        already_scraped = load_already_scraped()
        print(f"\n  [RESUME] {len(already_scraped)} products already in DB")

    grand_total = 0

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )

        for i, cat in enumerate(TOP_CATEGORIES, 1):
            print(f"\n── [{i}/{len(TOP_CATEGORIES)}] {cat['name']} {'─'*35}")
            try:
                saved = await scrape_category(ctx, cat, already_scraped, save_to_sqlite)
                grand_total += saved
            except Exception as e:
                print(f"  [ERROR] {cat['name']}: {e}")
                import traceback; traceback.print_exc()

        await browser.close()

    print(f"\n{'='*65}")
    print(f"  Grand total saved this run: {grand_total}")
    print(f"\n[FINAL] Regenerating HTML viewer...")
    import subprocess
    subprocess.run([sys.executable, "view_db.py"], check=False)
    print(f"\n{'='*65}")
    print(f"  DONE — check http://localhost:8765")
    print(f"{'='*65}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Schneider Electric SA scraper")
    parser.add_argument("--resume", action="store_true",
                        help="Skip products already in DB")
    args = parser.parse_args()
    asyncio.run(main(resume=args.resume))
