from typing import Optional
"""
scrape_electric_house.py
--------------------------
Scrapes ALL products from electric-house.com (Magento 2 React, EN).
https://electric-house.com/en/

Strategy:
  - Playwright renders the React/Tailwind storefront
  - Uses hardcoded top-level category list (reliable) with optional nav discovery
  - Paginates via &page=N with product_list_limit=48
  - Extracts name, URL, price (excl. VAT), image via DOM JS evaluate
  - Uses [class*="galleryItem-root"] product card selector
  - Enriches with SKU from product pages via concurrent httpx requests
  - Extracts brand from product name prefix ("BRAND - Description")
  - Saves to scraper_data.db after every category (live visibility)
  - --resume flag: skips already-saved external_ids

Usage:
    .venv\\Scripts\\python scrape_electric_house.py
    .venv\\Scripts\\python scrape_electric_house.py --resume
"""
import asyncio
import json
import re
import sys
import os
import argparse
from datetime import datetime

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

try:
    from playwright.async_api import async_playwright, Page, BrowserContext
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
import httpx

BASE_URL    = "https://electric-house.com/en"
HOME_URL    = "https://electric-house.com/en/"
SOURCE_NAME = "ElectricHouse"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en,ar;q=0.5",
}

# Fallback category list (verified from homepage footer/nav)
TOP_CATEGORIES = [
    {"name": "Load Centers & Circuit Breakers",
     "url":  "https://electric-house.com/en/load-centers-circuit-breakers.html"},
    {"name": "Electrical Switches & Sockets",
     "url":  "https://electric-house.com/en/electrical-switches-sockets.html"},
    {"name": "Cables & Wires",
     "url":  "https://electric-house.com/en/cables-wires.html"},
    {"name": "Conduits & Boxes",
     "url":  "https://electric-house.com/en/new-conduits-boxes.html"},
    {"name": "Lighting",
     "url":  "https://electric-house.com/en/lighting.html"},
    {"name": "Safety & Isolator Switches",
     "url":  "https://electric-house.com/en/new-protection.html"},
    {"name": "Earthing & Lightning Equipment",
     "url":  "https://electric-house.com/en/earthing-lighting-equipment.html"},
    {"name": "Fire Alarm Systems",
     "url":  "https://electric-house.com/en/fire-alarm-system.html"},
    {"name": "CCTV Systems",
     "url":  "https://electric-house.com/en/cctv-systems.html"},
    {"name": "Control",
     "url":  "https://electric-house.com/en/new-control.html"},
    {"name": "Busbars",
     "url":  "https://electric-house.com/en/busbars.html"},
    {"name": "Enclosures",
     "url":  "https://electric-house.com/en/enclosures.html"},
    {"name": "Transformers",
     "url":  "https://electric-house.com/en/transformers.html"},
    {"name": "E-Mobility",
     "url":  "https://electric-house.com/en/e-mobility.html"},
    {"name": "Solar Products",
     "url":  "https://electric-house.com/en/solar-products.html"},
    {"name": "Tools & Equipment",
     "url":  "https://electric-house.com/en/tools-equipments.html"},
    {"name": "Clearance & Discontinued",
     "url":  "https://electric-house.com/en/clearance-discontinued-products.html"},
]

# Semaphore for concurrent httpx product-page enrichment
_ENRICH_SEM = asyncio.Semaphore(8)


# ─── helpers ──────────────────────────────────────────────────────────────────

def _parse_price(text: str) ->Optional[ float]:
    """'1,234.56' or 'SAR 1,234.56' → 1234.56"""
    if not text:
        return None
    clean = re.sub(r"[^\d.]", "", text.replace(",", ""))
    try:
        v = float(clean)
        return v if v > 0 else None
    except ValueError:
        return None


def _brand_from_name(name: str) -> str:
    """'SCHNEIDER - MCB Easy9 ...' → 'Schneider'"""
    if " - " in name:
        raw = name.split(" - ", 1)[0].strip()
        # Title-case multi-word brands
        return raw.title()
    return "Electric House"


# ─── browser context factory ──────────────────────────────────────────────────

async def _make_context(pw):
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        locale="en",
        extra_http_headers={"Accept-Language": "en,ar;q=0.5"},
    )
    return browser, context


# ─── STEP 1: discover categories from homepage nav ────────────────────────────

# Known slugs for top-level categories (used to filter product links out)
_CAT_SLUGS = {
    "load-centers-circuit-breakers", "electrical-switches-sockets",
    "cables-wires", "new-conduits-boxes", "lighting", "new-protection",
    "earthing-lighting-equipment", "fire-alarm-system", "cctv-systems",
    "new-control", "busbars", "enclosures", "transformers", "e-mobility",
    "solar-products", "tools-equipments", "clearance-discontinued-products",
}


async def discover_categories(ctx: BrowserContext) -> list[dict]:
    """
    Load the homepage and extract top-level category links from footer links.
    Falls back gracefully — caller always merges with TOP_CATEGORIES.
    """
    page = await ctx.new_page()
    try:
        await page.goto(HOME_URL, wait_until="networkidle", timeout=45_000)
        await page.wait_for_timeout(2_000)

        links = await page.evaluate("""(catSlugs) => {
            const BASE = 'https://electric-house.com';
            const cats = {};
            document.querySelectorAll('a[href]').forEach(a => {
                let href = a.getAttribute('href') || '';
                if (!href.startsWith('http')) href = BASE + href;
                // Match /en/<known-slug>.html only
                const m = href.match(/\\/en\\/([^/]+)\\.html$/);
                if (m && catSlugs.includes(m[1])) {
                    const text = a.textContent.trim();
                    if (!cats[href]) cats[href] = text || m[1];
                }
            });
            return Object.entries(cats).map(([url, name]) => ({name, url}));
        }""", list(_CAT_SLUGS))
        return links or []
    except Exception as e:
        print(f"  [discover error] {e}")
        return []
    finally:
        await page.close()


# ─── STEP 2: scrape one listing page ─────────────────────────────────────────

async def scrape_page(
    page: Page,
    url: str,
    cat_name: str,
    cat_url: str,
) ->Optional[ tuple[list[dict], str]]:
    """Load one category page and extract all product cards. Returns (products, next_url)."""
    try:
        await page.goto(url, wait_until="networkidle", timeout=45_000)
    except Exception as e:
        print(f"    [goto error] {e}")
        return [], None

    # Wait for the React product grid
    try:
        await page.wait_for_selector('[class*="galleryItem-root"]', timeout=20_000)
    except Exception:
        await page.wait_for_timeout(5_000)

    products_raw = await page.evaluate("""() => {
        const BASE = 'https://electric-house.com';
        const items = [];

        document.querySelectorAll('[class*="galleryItem-root"]').forEach(card => {
            // ── Name + URL ──────────────────────────────────────────────────
            const nameLink = card.querySelector('a[class*="item-name"]');
            const name = nameLink ? nameLink.textContent.trim() : '';
            let href = nameLink ? (nameLink.getAttribute('href') || '') : '';
            if (href && !href.startsWith('http')) href = BASE + href;
            if (!name || !href) return;

            // ── Image (lazy-loaded actual image) ────────────────────────────
            const imgEl = card.querySelector('a[class*="item-images"] img[loading="lazy"]')
                       || card.querySelector('img[loading="lazy"]')
                       || card.querySelector('img');
            let img = imgEl ? (imgEl.getAttribute('src') || '') : '';
            if (img && !img.startsWith('http')) img = BASE + img;

            // ── Prices: first [class*="productPrice-root"] = Excl. VAT ──────
            let price = null, orig = null;
            const priceRoots = card.querySelectorAll('[class*="productPrice-root"]');
            if (priceRoots.length > 0) {
                const tags = priceRoots[0].querySelectorAll('[class*="productPrice-priceTag"]');
                if (tags.length >= 1) {
                    const v = parseFloat(tags[0].textContent.replace(/[^0-9.]/g, ''));
                    if (v > 0) price = v;
                }
                if (tags.length >= 2) {
                    const v = parseFloat(tags[1].textContent.replace(/[^0-9.]/g, ''));
                    if (v > 0 && v !== price) orig = v;
                }
                // Fallback: parse numbers from full priceRoot text
                if (!price) {
                    const nums = priceRoots[0].textContent
                        .replace(/,/g, '')
                        .match(/[0-9]+(?:\\.[0-9]+)?/g);
                    if (nums && nums.length > 0) price = parseFloat(nums[0]) || null;
                    if (nums && nums.length > 1) orig = parseFloat(nums[1]) || null;
                }
            }

            // ── Badges ──────────────────────────────────────────────────────
            const stockBadge = card.querySelector('[class*="rightTopBadge"]');
            const in_stock   = stockBadge ? stockBadge.textContent.trim() : '';
            const discBadge  = card.querySelector('[class*="leftTopBadge"]');
            const discount   = discBadge  ? discBadge.textContent.trim()  : '';

            items.push({ name, href, img, price, orig, in_stock, discount });
        });

        return items;
    }""")

    products = []
    seen_on_page: set[str] = set()
    for raw in products_raw:
        name = (raw.get("name") or "").strip()
        product_url = (raw.get("href") or "").strip()
        if not product_url or not name:
            continue

        slug = product_url.rstrip("/").split("/")[-1]
        external_id = re.sub(r"\.html$", "", slug)

        # Deduplicate within page (site renders mobile + desktop grids)
        if external_id in seen_on_page:
            continue
        seen_on_page.add(external_id)

        products.append({
            "external_id":    external_id,
            "sku":            "",
            "name":           name,
            "price":          raw.get("price"),
            "original_price": raw.get("orig"),
            "source_url":     product_url,
            "image_url":      raw.get("img", ""),
            "in_stock":       raw.get("in_stock", ""),
            "discount":       raw.get("discount", ""),
            "_category_name": cat_name,
            "_category_url":  cat_url,
        })

    # ── Next-page link ──────────────────────────────────────────────────────
    # The site uses React buttons (not <a> tags) for pagination.
    # Strategy: check if "move to the next page" button is enabled, then
    # build the next URL by incrementing the &page= parameter.
    next_url = await page.evaluate("""() => {
        // Find the "next page" nav button
        const nextBtn =
            document.querySelector('button[aria-label="move to the next page"]') ||
            document.querySelector('button[aria-label="Next page"]');
        if (nextBtn && nextBtn.disabled) return null;
        if (!nextBtn) return null;   // no next button = last page

        // Extract current page from URL and build next-page URL
        const curUrl  = window.location.href;
        const pageM   = curUrl.match(/([?&])page=(\\d+)/);
        if (!pageM) return null;
        const nextPage = parseInt(pageM[2]) + 1;
        return curUrl.replace(/([?&])page=\\d+/, pageM[1] + 'page=' + nextPage);
    }""")

    return products, next_url


# ─── STEP 3: enrich products with SKU via Magento 2 GraphQL ─────────────────

_GQL_URL = "https://electric-house.com/graphql"
_GQL_HEADERS = {
    **HEADERS,
    "Content-Type": "application/json",
    "Store": "en",
}


def _url_key_from_url(url: str) -> str:
    """Extract the Magento url_key from a product URL.

    https://electric-house.com/en/schneider-mcb.html  ->  schneider-mcb
    """
    m = re.search(r'/en/([^/?#]+?)(?:\.html)?(?:[/?#]|$)', url)
    return m.group(1) if m else ""


async def enrich_products_batch(
    client: httpx.AsyncClient,
    products: list[dict],
    batch_size: int = 50,
) -> list[dict]:
    """Fetch SKUs for a batch of products via the Magento 2 GraphQL API."""
    # Build url_key -> product map
    key_map: dict[str, dict] = {}
    for p in products:
        key = _url_key_from_url(p.get("source_url", ""))
        if key:
            key_map[key] = p

    if not key_map:
        return products

    keys = list(key_map.keys())
    # Fetch in batches
    for i in range(0, len(keys), batch_size):
        chunk = keys[i : i + batch_size]
        keys_gql = ", ".join(f'"{k}"' for k in chunk)
        query = """
        {
          products(filter: {url_key: {in: [%s]}}) {
            items { sku url_key }
          }
        }
        """ % keys_gql
        try:
            async with _ENRICH_SEM:
                r = await client.post(
                    _GQL_URL,
                    json={"query": query},
                    headers=_GQL_HEADERS,
                    timeout=20,
                )
            if r.status_code == 200:
                data = r.json()
                for item in (data.get("data", {}).get("products", {}).get("items") or []):
                    uk = item.get("url_key", "")
                    sku = item.get("sku", "")
                    if uk and sku and uk in key_map:
                        key_map[uk]["sku"] = sku
        except Exception:
            pass

    return products


# ─── STEP 4: save batch to SQLite ────────────────────────────────────────────

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
        # ── Source ────────────────────────────────────────────────────────
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
                    ext_id = re.sub(r"[^\w]", "_", name.lower())
                    c = ScraperCategory(
                        source_id=source.id,
                        name=name,
                        external_id=ext_id,
                        url=url,
                    )
                    session.add(c)
                    session.flush()
                cat_cache[name] = c
            return cat_cache[name]

        for raw in all_products:
            name = (raw.get("name") or "").strip()
            if not name:
                skipped += 1
                continue

            external_id = raw.get("external_id", "")
            sku         = raw.get("sku") or external_id
            price       = raw.get("price")
            source_url  = raw.get("source_url", "")
            brand_name  = _brand_from_name(name)
            cat_name    = raw.get("_category_name", "General")
            cat_url     = raw.get("_category_url", "")

            category = get_category(cat_name, cat_url)
            brand    = get_brand(brand_name)

            # Upsert by external_id
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
                existing.raw_data            = json.dumps(raw, ensure_ascii=False, default=str)
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
                    raw_data=json.dumps(raw, ensure_ascii=False, default=str),
                    last_scraped_at=datetime.now(),
                    is_synced=False,
                ))
                inserted += 1

        session.commit()

    print(f"  DB → inserted={inserted}, updated={updated}, skipped={skipped}")
    return inserted, updated, skipped


# ─── scrape full category (all pages) ────────────────────────────────────────

async def scrape_category(
    ctx: BrowserContext,
    client: httpx.AsyncClient,
    category: dict,
    already_scraped: set[str],
) -> int:
    cat_name = category["name"]
    cat_url  = category["url"]
    # Start with max items per page (site uses &page=N for pagination)
    page_url = cat_url + "?product_list_limit=48&page=1"
    page_num = 1
    cat_total = 0

    page = await ctx.new_page()
    try:
        while page_url:
            print(f"    Page {page_num}: {page_url}")
            products, next_url = await scrape_page(page, page_url, cat_name, cat_url)

            new = [p for p in products if p["external_id"] not in already_scraped]
            for p in new:
                already_scraped.add(p["external_id"])

            print(f"      → {len(products)} found, {len(new)} new")

            if new:
                # Enrich with SKU via Magento 2 GraphQL (one batch request)
                print(f"      Enriching {len(new)} products (SKU via GraphQL)...")
                new = await enrich_products_batch(client, new)

                save_to_sqlite(new)
                cat_total += len(new)

            if not next_url:
                break
            page_url = next_url
            page_num += 1

    finally:
        await page.close()

    print(f"  [{cat_name}] Done — {cat_total} new products")
    return cat_total


# ─── main ─────────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Scrape electric-house.com")
    parser.add_argument(
        "--resume", action="store_true",
        help="Skip already-saved external_ids (incremental run)"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  ELECTRIC-HOUSE.COM — FULL SITE SCRAPER")
    print("=" * 60)

    # ── Load already-scraped IDs for --resume ──────────────────────────────
    already_scraped: set[str] = set()
    if args.resume:
        try:
            from scraper.models.source import ScraperSource
            from scraper.models.product import ScraperProduct
            from scraper.core.database import ScraperBase
            from sqlalchemy import create_engine, select
            from sqlalchemy.orm import Session

            engine = create_engine(f"sqlite:///{_DB_FILE}", echo=False)
            with Session(engine) as s:
                src = s.execute(
                    select(ScraperSource).where(ScraperSource.name == SOURCE_NAME)
                ).scalar_one_or_none()
                if src:
                    rows = s.execute(
                        select(ScraperProduct.external_id).where(
                            ScraperProduct.source_id == src.id
                        )
                    ).scalars().all()
                    already_scraped = set(r for r in rows if r)
            print(f"  Resume mode: {len(already_scraped)} already scraped")
        except Exception as e:
            print(f"  [resume load error] {e}")

    async with async_playwright() as pw:
        browser, ctx = await _make_context(pw)

        # ── STEP 1: discover categories ────────────────────────────────────
        print("\n[STEP 1] Discovering categories from homepage nav...")
        discovered = await discover_categories(ctx)
        print(f"  Discovered {len(discovered)} nav links")

        # Merge discovered with fallback (fallback fills any gaps)
        cat_map: dict[str, str] = {c["url"]: c["name"] for c in discovered}
        for fb in TOP_CATEGORIES:
            cat_map.setdefault(fb["url"], fb["name"])

        categories = [{"name": name, "url": url} for url, name in cat_map.items()]

        print(f"  Total: {len(categories)} categories")
        for c in categories:
            print(f"    {c['name']}")

        # ── STEP 2-4: scrape, enrich, save each category ──────────────────
        print(f"\n[STEP 2] Scraping categories...\n")
        total = 0

        async with httpx.AsyncClient(
            timeout=20,
            follow_redirects=True,
            headers=HEADERS,
        ) as client:
            for i, cat in enumerate(categories, 1):
                print(f"── [{i}/{len(categories)}] {cat['name']} ─────────────────")
                try:
                    n = await scrape_category(ctx, client, cat, already_scraped)
                    total += n
                except Exception as e:
                    print(f"  [ERROR] {cat['name']}: {e}")

        await browser.close()

    print(f"\n{'=' * 60}")
    print(f"  DONE — {total} total new products saved")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    if not HAS_PLAYWRIGHT:
        print("ERROR: Playwright is not installed. This scraper requires a browser environment.")
        print("Run locally with: pip install playwright && playwright install chromium")
        sys.exit(1)
    asyncio.run(main())
