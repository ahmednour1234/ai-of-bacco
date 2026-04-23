from typing import Optional
"""
scrape_zorinstechnologies.py
-----------------------------
Scrapes ALL products from zorinstechnologies.sa (Zoho Commerce).
Strategy:
  - Discovers all category pages from the site navigation
  - Fetches each category listing with httpx + BeautifulSoup
  - Extracts: name, price, URL, image, in-stock status, product ID
  - Saves to scraper_data.db

Usage:
    python scrape_zorinstechnologies.py
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
os.environ.setdefault("SCRAPER_DATABASE_URL",      f"sqlite+aiosqlite:///{_DB_FILE}")
os.environ.setdefault("SCRAPER_DATABASE_URL_SYNC", f"sqlite:///{_DB_FILE}")
os.environ.setdefault("DATABASE_URL",              f"sqlite+aiosqlite:///{_DB_FILE}")
os.environ.setdefault("DATABASE_URL_SYNC",         f"sqlite:///{_DB_FILE}")
os.environ.setdefault("SCRAPER_SYNC_API_URL",      "https://api.example.com")
os.environ.setdefault("SCRAPER_SYNC_API_KEY",      "")
os.environ.setdefault("SECRET_KEY",                "dev-only-secret")
os.environ.setdefault("OPENAI_API_KEY",            "sk-placeholder")

import httpx
from bs4 import BeautifulSoup

BASE_URL    = "https://www.zorinstechnologies.sa"
SOURCE_NAME = "Zorins Technologies"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en,ar;q=0.5",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.zorinstechnologies.sa/",
}

# Seed categories — the user-provided URL plus other known categories
# discovered from the site navigation.
SEED_CATEGORIES = [
    {
        "name": "Cyber Security",
        "slug": "cyber-security",
        "id":   "1038473000010836065",
    },
]

CONCURRENCY = 5
_SEM: Optional[asyncio.Semaphore] = None


# ─── helpers ─────────────────────────────────────────────────────────────────

def _parse_price(text: str) ->Optional[ float]:
    """Parse SAR price like '6,200.00﷼' or '95.00SAR'."""
    if not text:
        return None
    # strip SAR symbol (﷼ = U+FDFC), commas
    clean = text.replace("\ufdfc", "").replace("SAR", "").replace(",", "").strip()
    m = re.search(r'\d+(?:\.\d+)?', clean)
    if m:
        try:
            v = float(m.group())
            return v if v > 0 else None
        except ValueError:
            return None
    return None


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _extract_product_id(url: str) -> str:
    """Extract the numeric Zoho product ID from a product URL."""
    m = re.search(r'/(\d{10,})(?:/|$|\?)', url)
    return m.group(1) if m else url


# ─── STEP 1: discover categories ─────────────────────────────────────────────

async def discover_categories(client: httpx.AsyncClient) -> list[dict]:
    """
    Try to discover all category URLs from the homepage navigation.
    Falls back to SEED_CATEGORIES if the homepage doesn't expose them.
    """
    cats: dict[str, dict] = {}

    # Seed with known categories first
    for c in SEED_CATEGORIES:
        cats[c["id"]] = {
            "name": c["name"],
            "slug": c["slug"],
            "id":   c["id"],
            "url":  f"{BASE_URL}/categories/{c['slug']}/{c['id']}",
        }

    try:
        r = await client.get(BASE_URL, headers=HEADERS, follow_redirects=True, timeout=30)
        soup = _soup(r.text)

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not href.startswith("http"):
                href = BASE_URL + href if href.startswith("/") else href
            m = re.search(r'/categories/([^/?#]+)/(\d{10,})', href)
            if m:
                slug = m.group(1)
                cat_id = m.group(2)
                if cat_id not in cats:
                    name = a.get_text(strip=True) or slug.replace("-", " ").title()
                    cats[cat_id] = {
                        "name": name,
                        "slug": slug,
                        "id":   cat_id,
                        "url":  f"{BASE_URL}/categories/{slug}/{cat_id}",
                    }

        print(f"  Homepage discovery → {len(cats)} categories total")
    except Exception as e:
        print(f"  [WARN] Homepage discovery failed: {e}")

    return list(cats.values())


# ─── STEP 2: scrape one category page ────────────────────────────────────────

def _parse_category_page(html: str, category: dict) -> list[dict]:
    """
    Parse a Zoho Commerce category listing page.
    Returns a list of raw product dicts.
    """
    soup = _soup(html)
    products: list[dict] = []
    seen_ids: set[str] = set()

    # ── Strategy A: Zoho Commerce product cards ───────────────────────────────
    # Typical structure (may vary by theme):
    #   <div class="product-card"> or <li class="product-item">
    #     <a href="/products/slug/id">
    #       <img src="..."/>
    #     </a>
    #     <a href="/products/slug/id">Product Name</a>
    #     <span class="price">6,200.00﷼</span>
    #     <span class="out-of-stock">Out of stock</span>   (optional)
    #   </div>

    # Collect all product-page links first
    product_links = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("http"):
            href = BASE_URL.rstrip("/") + href
        m = re.search(r'/products/([^/?#]+)/(\d{10,})', href)
        if m:
            product_id = m.group(2)
            if product_id not in product_links:
                product_links[product_id] = href

    # Now walk the document to associate name/price/image with each link
    # Build a lookup from URL → parent container element
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("http"):
            href = BASE_URL.rstrip("/") + href
        m = re.search(r'/products/([^/?#]+)/(\d{10,})', href)
        if not m:
            continue

        slug = m.group(1)
        product_id = m.group(2)

        if product_id in seen_ids:
            continue

        name_text = a.get_text(strip=True)

        # Skip image-only links (empty text or very short)
        if not name_text or len(name_text) < 2:
            # Maybe the sibling <a> has the name
            continue

        # ── name ──
        name = name_text

        # ── price: walk siblings / parent to find price text ──
        price = None
        in_stock = True

        # Walk up to find the product container
        container = a.parent
        for _ in range(5):  # walk up max 5 levels
            if container is None:
                break
            # Try to find price within container
            price_el = (
                container.select_one(".price")
                or container.select_one(".product-price")
                or container.select_one("[class*='price']")
            )
            if price_el:
                price = _parse_price(price_el.get_text(strip=True))
                break
            container = container.parent

        # If no price element, try text sibling / adjacent text nodes
        if price is None:
            # Find price in the text following this link
            parent = a.parent
            if parent:
                full_text = parent.get_text(" ", strip=True)
                # Look for currency pattern after the product name
                price_m = re.search(
                    re.escape(name) + r'.*?(\d[\d,]*\.?\d*)\s*(?:﷼|SAR)',
                    full_text,
                )
                if price_m:
                    price = _parse_price(price_m.group(1))

        # ── out-of-stock ──
        container2 = a.parent
        for _ in range(5):
            if container2 is None:
                break
            oos_el = (
                container2.find(string=re.compile(r'out\s+of\s+stock', re.I))
                or container2.select_one(".out-of-stock, .sold-out, [class*='stock']")
            )
            if oos_el:
                in_stock = False
                break
            container2 = container2.parent

        # ── image ──
        img_url = ""
        container3 = a.parent
        for _ in range(5):
            if container3 is None:
                break
            img_el = container3.find("img")
            if img_el:
                img_url = img_el.get("src") or img_el.get("data-src") or ""
                break
            container3 = container3.parent

        seen_ids.add(product_id)
        products.append({
            "external_id":     product_id,
            "sku":             slug.upper().replace("-", "_"),
            "name":            name,
            "price":           price,
            "in_stock":        in_stock,
            "source_url":      href,
            "image_url":       img_url,
            "_category_name":  category["name"],
            "_category_slug":  category["slug"],
            "_category_url":   category["url"],
        })

    return products


async def scrape_category(client: httpx.AsyncClient, category: dict) -> list[dict]:
    """Fetch and parse a category page (all products on one page for Zoho Commerce)."""
    url = category["url"]
    print(f"  Fetching: {url}")

    async with _SEM:
        try:
            r = await client.get(url, headers=HEADERS, follow_redirects=True, timeout=30)
            if r.status_code != 200:
                print(f"    [HTTP {r.status_code}] {url}")
                return []
        except Exception as e:
            print(f"    [ERROR] {url}: {e}")
            return []

    products = _parse_category_page(r.text, category)
    print(f"    → {len(products)} products in [{category['name']}]")
    return products


# ─── STEP 3: enrich product details ──────────────────────────────────────────

async def enrich_product(client: httpx.AsyncClient, product: dict) -> dict:
    """
    Visit the product detail page to get price (if missing), brand, and tags.
    Only used when category page parsing didn't capture the price.
    """
    if product.get("price") is not None:
        return product   # already have price, skip enrichment

    url = product.get("source_url", "")
    if not url:
        return product

    async with _SEM:
        try:
            r = await client.get(url, headers=HEADERS, follow_redirects=True, timeout=25)
        except Exception:
            return product

    soup = _soup(r.text)

    # Price
    price_el = (
        soup.select_one("[class*='price']")
        or soup.select_one(".amount")
    )
    if price_el:
        product["price"] = _parse_price(price_el.get_text(strip=True))

    # SAR price appearing in text "6,200.00SAR"
    if product.get("price") is None:
        m = re.search(r'(\d[\d,]*\.?\d*)\s*(?:SAR|﷼)', soup.get_text())
        if m:
            product["price"] = _parse_price(m.group(1))

    # Tags → brand inference
    tags_text = ""
    for a in soup.find_all("a", href=True):
        if "search_type=tag" in a["href"]:
            tags_text += a.get_text(strip=True) + " "
    if tags_text:
        product["_tags"] = tags_text.strip()
        # Use first tag as brand if looks like a brand (short, no spaces)
        first_tag = tags_text.strip().split()[0]
        if len(first_tag) <= 20:
            product["brand"] = first_tag

    return product


# ─── STEP 4: save to SQLite ──────────────────────────────────────────────────

def save_to_sqlite(products: list[dict]) -> tuple[int, int, int]:
    from scraper.models.source import ScraperSource
    from scraper.models.category import ScraperCategory
    from scraper.models.brand import ScraperBrand
    from scraper.models.product import ScraperProduct
    from scraper.core.database import ScraperBase
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    engine = create_engine(
        os.environ.get("SCRAPER_DATABASE_URL_SYNC", f"sqlite:///{_DB_FILE}"),
        echo=False,
    )
    ScraperBase.metadata.create_all(engine)

    inserted = updated = skipped = 0

    with Session(engine) as session:
        # ── source ────────────────────────────────────────────────────────────
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

        def get_category(name: str, slug: str, url: str) -> ScraperCategory:
            key = slug or name
            if key not in cat_cache:
                c = session.execute(
                    select(ScraperCategory).where(
                        ScraperCategory.source_id == source.id,
                        ScraperCategory.name == name,
                    )
                ).scalar_one_or_none()
                if not c:
                    c = ScraperCategory(
                        source_id=source.id,
                        name=name,
                        external_id=slug,
                        url=url,
                    )
                    session.add(c)
                    session.flush()
                cat_cache[key] = c
            return cat_cache[key]

        for raw in products:
            name = raw.get("name", "").strip()
            if not name:
                skipped += 1
                continue

            external_id = raw.get("external_id", "")
            sku         = raw.get("sku", "") or external_id
            price       = raw.get("price")
            source_url  = raw.get("source_url", "")
            image_url   = raw.get("image_url", "")
            brand_name  = raw.get("brand", SOURCE_NAME)

            cat_name = raw.get("_category_name", "General")
            cat_slug = raw.get("_category_slug", "")
            cat_url  = raw.get("_category_url", "")

            category = get_category(cat_name, cat_slug, cat_url)
            brand    = get_brand(brand_name)

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

    return inserted, updated, skipped


# ─── main ────────────────────────────────────────────────────────────────────

async def main():
    global _SEM
    _SEM = asyncio.Semaphore(CONCURRENCY)
    print("=" * 60)
    print("  ZORINS TECHNOLOGIES — FULL SITE SCRAPER")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:

        # ── STEP 1: discover categories ───────────────────────────────────────
        print("\n[STEP 1] Discovering categories...")
        categories = await discover_categories(client)
        print(f"  Categories to scrape: {len(categories)}")
        for c in categories:
            print(f"    [{c['slug']}] {c['name']}  ->  {c['url']}")

        # ── STEP 2: scrape each category ──────────────────────────────────────
        print(f"\n[STEP 2] Scraping {len(categories)} categories...\n")
        all_products: list[dict] = []
        seen_ids: set[str] = set()

        tasks = [scrape_category(client, cat) for cat in categories]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for cat, result in zip(categories, results):
            if isinstance(result, Exception):
                print(f"  [ERROR] {cat['name']}: {result}")
                continue
            for p in result:
                pid = p.get("external_id") or p.get("source_url")
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    all_products.append(p)

        print(f"\n  Total unique products found: {len(all_products)}")

        # ── STEP 3: enrich products missing prices ────────────────────────────
        missing_price = [p for p in all_products if p.get("price") is None]
        if missing_price:
            print(f"\n[STEP 3] Enriching {len(missing_price)} products missing price...")
            enrich_tasks = [enrich_product(client, p) for p in missing_price]
            await asyncio.gather(*enrich_tasks, return_exceptions=True)

        # ── STEP 4: save to DB ────────────────────────────────────────────────
        print(f"\n[STEP 4] Saving {len(all_products)} products to DB...")
        inserted, updated, skipped = save_to_sqlite(all_products)
        print(f"  DB → inserted={inserted}, updated={updated}, skipped={skipped}")

    # ── summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  Total unique products: {len(all_products)}")
    print("  Breakdown by category:")
    for name, count in Counter(
        p.get("_category_name", "?") for p in all_products
    ).most_common():
        print(f"    {name}: {count}")

    # Save raw JSON
    output_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "scraped_zorinstechnologies.json"
    )
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_products, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n  Raw JSON → {output_file}")

    # Regenerate HTML viewer
    print("\n[STEP 5] Regenerating HTML viewer...")
    import subprocess
    subprocess.run([sys.executable, "view_db.py"], check=False)

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
