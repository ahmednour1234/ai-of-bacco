"""
scrape_all_elburoj.py
----------------------
Scrapes ALL categories from elburoj.com and saves to scraper_data.db.

Steps:
  1. Load homepage → discover every category link
  2. For each category, load every page (pagination) → intercept Salla API responses
  3. Deduplicate products across categories
  4. Save to SQLite + regenerate HTML viewer

Usage:
    .\.venv\Scripts\python scrape_all_elburoj.py
"""
import asyncio
import json
import re
import sys
import os
from collections import Counter
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scraper_data.db")

os.environ.setdefault("SCRAPER_DATABASE_URL", f"sqlite+aiosqlite:///{_DB_FILE}")
os.environ.setdefault("SCRAPER_DATABASE_URL_SYNC", f"sqlite:///{_DB_FILE}")
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_DB_FILE}")
os.environ.setdefault("DATABASE_URL_SYNC", f"sqlite:///{_DB_FILE}")
os.environ.setdefault("SCRAPER_SYNC_API_URL", "https://api.example.com")
os.environ.setdefault("SCRAPER_SYNC_API_KEY", "")
os.environ.setdefault("SECRET_KEY", "dev-only-secret")
os.environ.setdefault("OPENAI_API_KEY", "sk-placeholder")

from playwright.async_api import async_playwright

BASE_URL = "https://elburoj.com/ar"

# Fallback list in case homepage discovery fails
KNOWN_CATEGORIES = [
    {"id": "539403396",  "name": "إنارة",       "url": "https://elburoj.com/ar/%D8%A5%D9%86%D8%A7%D8%B1%D8%A9/c539403396"},
    {"id": "413920175",  "name": "كابلات",       "url": "https://elburoj.com/ar/%D9%83%D8%A7%D8%A8%D9%84%D8%A7%D8%AA/c413920175"},
]


# ─── Browser context factory ─────────────────────────────────────────────────

async def _make_context(pw):
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        locale="ar",
        extra_http_headers={"Accept-Language": "ar,en;q=0.5"},
    )
    return browser, context


# ─── STEP 1: Discover all category URLs from homepage ────────────────────────

async def discover_categories() -> list[dict]:
    """Load the homepage and extract every category link from the DOM."""
    api_cats: list[dict] = []
    dom_cats: list[dict] = []

    async with async_playwright() as pw:
        browser, context = await _make_context(pw)
        page = await context.new_page()

        # Intercept API responses — Salla sometimes serves category list via API
        async def on_response(response):
            try:
                if "api.salla.dev" in response.url and "json" in response.headers.get("content-type", ""):
                    body = await response.json()
                    if isinstance(body, dict) and isinstance(body.get("data"), list):
                        for item in body["data"]:
                            if (
                                isinstance(item, dict)
                                and item.get("name")
                                and item.get("url")
                                and re.search(r"/c\d{6,}", item.get("url", ""))
                            ):
                                api_cats.append({
                                    "id": str(item.get("id", "")),
                                    "name": str(item["name"]).strip(),
                                    "url": item["url"],
                                })
            except Exception:
                pass

        page.on("response", on_response)

        print(f"  Loading: {BASE_URL}")
        try:
            await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"  [WARN] goto: {e}")

        await page.wait_for_timeout(7000)

        # Extract <a href> links that look like Salla category URLs (/c + digits)
        raw_links: list[dict] = await page.evaluate("""
            () => {
                const seen = new Set();
                const results = [];
                document.querySelectorAll('a[href]').forEach(a => {
                    const href = a.href;
                    if (/\\/c\\d{6,}/.test(href) && !seen.has(href)) {
                        seen.add(href);
                        results.push({ url: href, name: a.innerText.trim() || a.title || '' });
                    }
                });
                return results;
            }
        """)

        for lnk in raw_links:
            m = re.search(r"/c(\d+)", lnk["url"])
            cid = m.group(1) if m else ""
            name = lnk["name"].split("\n")[0].strip() or f"cat_{cid}"
            dom_cats.append({"id": cid, "name": name, "url": lnk["url"]})

        await browser.close()

    print(f"  API categories: {len(api_cats)}, DOM links: {len(dom_cats)}")

    # Merge: prefer API names, supplement with DOM links
    merged: dict[str, dict] = {}
    for c in api_cats:
        merged[c["id"]] = c
    for c in dom_cats:
        if c["id"] and c["id"] not in merged:
            merged[c["id"]] = c

    categories = list(merged.values())

    # Filter out obviously wrong entries (empty names, IDs too short)
    categories = [c for c in categories if c["id"] and c["name"] and len(c["id"]) >= 6]

    return categories


# ─── STEP 2: Scrape one category (all pages) ─────────────────────────────────

async def scrape_category(category: dict, page_wait_ms: int = 9000) -> list[dict]:
    """Scrape all pages of a single category and return product list."""
    cat_name = category.get("name", "?")
    cat_url  = category.get("url", "")
    cat_id   = category.get("id", "")
    all_products: list[dict] = []

    async with async_playwright() as pw:
        browser, context = await _make_context(pw)
        page = await context.new_page()

        page_products: list[dict] = []
        pagination: dict = {}

        async def on_response(response):
            try:
                if "api.salla.dev" in response.url and "json" in response.headers.get("content-type", ""):
                    body = await response.json()
                    if isinstance(body, dict):
                        data = body.get("data", [])
                        if isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict) and ("name" in item or "id" in item):
                                    page_products.append(item)
                        pag = body.get("pagination")
                        if pag and isinstance(pag, dict):
                            pagination.update(pag)
            except Exception:
                pass

        page.on("response", on_response)

        async def load_page(url: str):
            page_products.clear()
            pagination.clear()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                print(f"    [WARN] {e}")
            await page.wait_for_timeout(page_wait_ms)
            # Scroll to bottom to trigger lazy loads
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(3000)

        # Page 1
        print(f"  Page 1: {cat_url}")
        await load_page(cat_url)
        all_products.extend(page_products)
        total_pages = int(pagination.get("totalPages", 1))
        print(f"    → {len(page_products)} products | total pages: {total_pages}")

        # Remaining pages
        for pg in range(2, total_pages + 1):
            sep = "&" if "?" in cat_url else "?"
            next_url = f"{cat_url}{sep}page={pg}"
            print(f"  Page {pg}/{total_pages}: {next_url}")
            await load_page(next_url)
            if not page_products:
                print(f"    → Empty, stopping.")
                break
            all_products.extend(page_products)
            # Update total pages in case it changed
            total_pages = int(pagination.get("totalPages", total_pages))
            print(f"    → {len(page_products)} products (running total: {len(all_products)})")

        await browser.close()

    # Tag each product with its category
    for p in all_products:
        p["_category_name"] = cat_name
        p["_category_url"] = cat_url
        p["_category_id"] = cat_id

    print(f"  [{cat_name}] Done — {len(all_products)} products")
    return all_products


# ─── STEP 3: Save to SQLite ───────────────────────────────────────────────────

def _parse_price(price_data) -> float | None:
    if price_data is None:
        return None
    if isinstance(price_data, (int, float)):
        return float(price_data) if price_data > 0 else None
    if isinstance(price_data, dict):
        amt = price_data.get("amount")
        try:
            v = float(amt)
            return v if v > 0 else None
        except (ValueError, TypeError):
            return None
    return None


def _extract_name(product: dict) -> str:
    name = product.get("name")
    if isinstance(name, dict):
        return name.get("ar") or name.get("en") or ""
    return str(name).strip() if name else ""


def save_to_sqlite(all_products: list[dict]) -> tuple[int, int, int]:
    from scraper.models.source import ScraperSource
    from scraper.models.category import ScraperCategory
    from scraper.models.brand import ScraperBrand
    from scraper.models.product import ScraperProduct
    from scraper.core.database import ScraperBase
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    engine = create_engine(f"sqlite:///{_DB_FILE}", echo=False)
    ScraperBase.metadata.create_all(engine)

    inserted = updated = skipped = 0

    with Session(engine) as session:
        # Ensure source exists
        source = session.execute(
            select(ScraperSource).where(ScraperSource.name == "El Buroj")
        ).scalar_one_or_none()
        if not source:
            source = ScraperSource(name="El Buroj", base_url="https://elburoj.com", active=True)
            session.add(source)
            session.flush()

        cat_cache: dict[str, ScraperCategory] = {}
        brand_cache: dict[str, ScraperBrand] = {}

        for raw in all_products:
            name = _extract_name(raw)
            if not name:
                skipped += 1
                continue

            external_id = str(raw.get("id", ""))
            sku         = raw.get("sku") or raw.get("product_number") or ""
            price       = _parse_price(raw.get("price"))
            source_url  = raw.get("url") or ""
            if source_url and not source_url.startswith("http"):
                source_url = "https://elburoj.com" + source_url

            # ── Category ──────────────────────────────────────────────
            cat_name = raw.get("_category_name") or "عام"
            if cat_name not in cat_cache:
                cat = session.execute(
                    select(ScraperCategory).where(
                        ScraperCategory.source_id == source.id,
                        ScraperCategory.name == cat_name,
                    )
                ).scalar_one_or_none()
                if not cat:
                    cat = ScraperCategory(
                        source_id=source.id,
                        name=cat_name,
                        external_id=raw.get("_category_id", ""),
                        url=raw.get("_category_url", ""),
                    )
                    session.add(cat)
                    session.flush()
                cat_cache[cat_name] = cat
            category = cat_cache[cat_name]

            # ── Brand ─────────────────────────────────────────────────
            brand_data = raw.get("brand")
            brand_name = None
            if isinstance(brand_data, dict):
                brand_name = brand_data.get("name")
            elif isinstance(brand_data, str) and brand_data:
                brand_name = brand_data

            brand = None
            if brand_name:
                if brand_name not in brand_cache:
                    b = session.execute(
                        select(ScraperBrand).where(
                            ScraperBrand.source_id == source.id,
                            ScraperBrand.name == brand_name,
                        )
                    ).scalar_one_or_none()
                    if not b:
                        b = ScraperBrand(source_id=source.id, name=brand_name)
                        session.add(b)
                        session.flush()
                    brand_cache[brand_name] = b
                brand = brand_cache[brand_name]

            # ── Upsert product ────────────────────────────────────────
            existing = None
            if external_id:
                existing = session.execute(
                    select(ScraperProduct).where(
                        ScraperProduct.source_id == source.id,
                        ScraperProduct.external_id == external_id,
                    )
                ).scalar_one_or_none()

            if existing:
                existing.name               = name
                existing.sku                = sku
                existing.price              = price
                existing.source_url         = source_url
                existing.scraper_category_id = category.id
                existing.scraper_brand_id    = brand.id if brand else None
                existing.raw_data            = json.dumps(raw, ensure_ascii=False, default=str)
                existing.last_scraped_at     = datetime.utcnow()
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
                    scraper_brand_id=brand.id if brand else None,
                    raw_data=json.dumps(raw, ensure_ascii=False, default=str),
                    last_scraped_at=datetime.utcnow(),
                    is_synced=False,
                ))
                inserted += 1

        session.commit()

    print(f"  DB → inserted={inserted}, updated={updated}, skipped={skipped}")
    return inserted, updated, skipped


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("  EL BUROJ — FULL SITE SCRAPER")
    print("=" * 60)

    # ── STEP 1: Discover categories ───────────────────────────────────
    print("\n[STEP 1] Discovering categories from homepage...")
    categories = await discover_categories()

    if not categories:
        print("  Homepage discovery found nothing — using fallback list.")
        categories = KNOWN_CATEGORIES
    else:
        # Always include known categories in case they were missed
        known_ids = {c["id"] for c in categories}
        for kc in KNOWN_CATEGORIES:
            if kc["id"] not in known_ids:
                categories.append(kc)

    print(f"\n  {len(categories)} categories to scrape:")
    for c in categories:
        print(f"    [{c['id']}] {c['name']}")

    # ── STEP 2: Scrape each category ──────────────────────────────────
    print(f"\n[STEP 2] Scraping {len(categories)} categories (saving after each)...\n")
    all_products: list[dict] = []
    seen_ids: set[str] = set()

    for i, cat in enumerate(categories, 1):
        print(f"── [{i}/{len(categories)}] {cat['name']} ──────────────────────")
        try:
            products = await scrape_category(cat)
        except Exception as e:
            print(f"  [ERROR] {cat['name']}: {e}")
            continue

        # Deduplicate against already-seen products
        new_products = []
        for p in products:
            pid = str(p.get("id", "")) or str(p.get("url", ""))
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                new_products.append(p)

        if new_products:
            all_products.extend(new_products)
            # ── Save immediately to DB after each category ────────────
            print(f"  Saving {len(new_products)} new products to DB...")
            save_to_sqlite(new_products)
        else:
            print(f"  No new unique products in this category.")

    print(f"\nTotal unique products scraped: {len(all_products)}")
    print("Breakdown by category:")
    for cat_name, count in Counter(p.get("_category_name", "?") for p in all_products).most_common():
        print(f"  {cat_name}: {count}")

    # ── Save raw JSON ─────────────────────────────────────────────────
    output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scraped_all_products.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_products, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nRaw JSON saved → {output_file}")

    # ── STEP 3: Regenerate HTML viewer ───────────────────────────────
    print("\n[STEP 3] Regenerating HTML viewer...")
    import subprocess
    subprocess.run([sys.executable, "view_db.py"], check=False)

    print("\n" + "=" * 60)
    print(f"  DONE — {len(all_products)} products in scraper_data.db")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
