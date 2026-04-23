from typing import Optional
"""
scrape_janoubco.py
-------------------
Scrapes ALL products from janoubco.com (OpenCart / Journal3, AR).
https://janoubco.com

Strategy:
  - Parses the XML sitemaps (server-rendered, no Playwright needed)
  - Fetches all 11 product sitemaps to collect every product URL (5 480+)
  - Concurrently fetches product pages with httpx + BeautifulSoup
  - Extracts: name, SKU, price, brand, category, image, URL
  - Saves incrementally to scraper_data.db after every batch

Usage:
    python scrape_janoubco.py
    python scrape_janoubco.py --resume
"""
import asyncio
import json
import re
import sys
import os
import argparse
import random
import xml.etree.ElementTree as ET
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
from playwright.async_api import async_playwright
try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False

from _proxy_pool import next_playwright_proxy, next_httpx_proxy, has_proxies, count as proxy_count

BASE_URL    = "https://janoubco.com"
SOURCE_NAME = "Janoubco"

# Sitemap index: 11 product sitemaps + category + brand
SITEMAP_INDEX = "https://janoubco.com/sitemap.xml"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ar,en;q=0.5",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Concurrency: how many product pages to fetch simultaneously
CONCURRENCY = 12
_SEM = asyncio.Semaphore(CONCURRENCY)
_BATCH_SAVE = 50   # save to DB every N products


# ─── helpers ──────────────────────────────────────────────────────────────────

def _parse_price(text: str) ->Optional[ float]:
    if not text:
        return None
    # Use regex to find first decimal/integer number — avoids ر.س trailing dot bug
    m = re.search(r'\d[\d,]*(?:\.\d+)?', text.replace('\u060c', ''))
    if m:
        try:
            v = float(m.group().replace(',', ''))
            return v if v > 0 else None
        except ValueError:
            return None
    return None


def _slug_from_url(url: str) -> str:
    return url.rstrip("/").split("/")[-1].split("?")[0]


# ─── STEP 1: parse sitemaps ────────────────────────────────────────────────────

async def fetch_all_product_urls(client: httpx.AsyncClient) -> list[str]:
    """Fetch the sitemap index, then all product sub-sitemaps. Returns list of product URLs."""
    # Get index
    try:
        r = await client.get(SITEMAP_INDEX, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print(f"  [sitemap error] {e}")
        return []

    # Find product sitemap URLs from index
    product_sitemaps = []
    try:
        root = ET.fromstring(r.text)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        for loc in root.findall(".//sm:loc", ns):
            if loc.text and "sitemap-product" in loc.text:
                product_sitemaps.append(loc.text.strip())
    except ET.ParseError:
        # fallback: regex
        product_sitemaps = re.findall(r'https://janoubco\.com/sitemap-product-\d+\.xml', r.text)

    print(f"  Found {len(product_sitemaps)} product sitemap files")

    # Fetch all product sitemaps concurrently
    async def fetch_sitemap(url: str) -> list[str]:
        try:
            resp = await client.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            urls = []
            for loc in root.findall(".//sm:loc", ns):
                u = (loc.text or "").strip()
                if u and "janoubco.com" in u:
                    urls.append(u)
            return urls
        except Exception as e:
            print(f"  [sitemap fetch error] {url}: {e}")
            return []

    tasks = [fetch_sitemap(u) for u in product_sitemaps]
    results = await asyncio.gather(*tasks)
    all_urls = [u for batch in results for u in batch]
    print(f"  Total product URLs from sitemaps: {len(all_urls)}")
    return all_urls


async def fetch_category_urls(client: httpx.AsyncClient) -> list[dict]:
    """Fetch sitemap-category.xml and return list of {name, url}."""
    try:
        r = await client.get(f"{BASE_URL}/sitemap-category.xml", headers=HEADERS, timeout=20)
        r.raise_for_status()
        root = ET.fromstring(r.text)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        cats = []
        for loc in root.findall(".//sm:loc", ns):
            u = (loc.text or "").strip()
            if u:
                slug = _slug_from_url(u)
                name = slug.replace("-", " ").replace("_", " ").strip()
                cats.append({"name": name, "url": u})
        return cats
    except Exception as e:
        print(f"  [category sitemap error] {e}")
        return []


# ─── STEP 2: parse a single product page ─────────────────────────────────────

def _parse_product_html(html: str, url: str) ->Optional[ dict]:
    """Extract product data from an OpenCart/Journal3 product page."""
    if not html:
        return None

    name = sku = brand = category = image_url = None
    price = original_price = None

    if _HAS_BS4:
        soup = BeautifulSoup(html, "html.parser")

        # ── Name ──────────────────────────────────────────────────────────
        for sel in [
            "h1.product-title", "h1[itemprop='name']", "h1.title",
            ".product-title h1", "h1",
        ]:
            el = soup.select_one(sel)
            if el:
                name = el.get_text(" ", strip=True)
                break

        # ── SKU ───────────────────────────────────────────────────────────
        for sel in [
            "[itemprop='sku']", ".product-sku span", ".sku span",
            ".model span", "#product-sku",
        ]:
            el = soup.select_one(sel)
            if el:
                sku = el.get_text(strip=True)
                if sku:
                    break
        if not sku:
            m = re.search(r'رقم المنتج[:\s]*([A-Za-z0-9\-_]+)', html)
            if m:
                sku = m.group(1).strip()

        # ── Price ─────────────────────────────────────────────────────────
        # janoubco: sale items use .price-new, regular items use .price-normal
        for sel in [
            ".price-new",
            ".price-normal",
            ".product-price .price-new",
            ".product-price .price-normal",
            "[itemprop='price']",
            ".special-price .price",
            ".product-price",
        ]:
            el = soup.select_one(sel)
            if el:
                content = el.get("content") or el.get_text(strip=True)
                price = _parse_price(content)
                if price:
                    break

        # Also try original price
        for sel in [".price-old", ".old-price", ".product-price .price-old"]:
            el = soup.select_one(sel)
            if el:
                original_price = _parse_price(el.get_text(strip=True))
                break

        # ── Brand ─────────────────────────────────────────────────────────
        for sel in [
            ".product-manufacturer a", "[itemprop='brand'] [itemprop='name']",
            ".brand a", ".manufacturer a", ".product-brand a",
        ]:
            el = soup.select_one(sel)
            if el:
                brand = el.get_text(strip=True)
                break
        if not brand:
            m = re.search(r'"brand"\s*:\s*\{"@type"\s*:\s*"Brand"\s*,\s*"name"\s*:\s*"([^"]+)"', html)
            if m:
                brand = m.group(1)
        if not brand:
            m = re.search(r'العلامة التجارية[:\s]*([^\n<]+)', html)
            if m:
                brand = m.group(1).strip()

        # ── Category ──────────────────────────────────────────────────────
        # Try breadcrumb
        crumbs = soup.select(".breadcrumb a, [itemprop='breadcrumb'] a, .breadcrumb-item a")
        if len(crumbs) >= 2:
            category = crumbs[-1].get_text(strip=True)
        if not category:
            m = re.search(r'"category"\s*:\s*"([^"]+)"', html)
            if m:
                category = m.group(1)

        # ── Image ─────────────────────────────────────────────────────────
        for sel in [
            "img[itemprop='image']",
            ".product-image img",
            ".thumbnails img",
            ".image-additional img",
        ]:
            el = soup.select_one(sel)
            if el:
                src = el.get("src") or el.get("data-src") or ""
                if src and not src.endswith("placeholder"):
                    image_url = src if src.startswith("http") else BASE_URL + src
                    break

    else:
        # Fallback: regex-only (no bs4)
        m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        if m:
            name = m.group(1).strip()
        m = re.search(r'"price"\s*:\s*"([^"]+)"', html)
        if m:
            price = _parse_price(m.group(1))
        m = re.search(r'rqm[^<]*<[^>]+>([A-Za-z0-9\-_]+)', html)
        if m:
            sku = m.group(1)

    if not name:
        return None

    slug = _slug_from_url(url)
    external_id = re.sub(r"\.(html|php)$", "", slug)

    return {
        "external_id":    external_id,
        "sku":            sku or external_id,
        "name":           name,
        "price":          price,
        "original_price": original_price,
        "source_url":     url,
        "image_url":      image_url or "",
        "brand":          brand or "Janoubco",
        "category":       category or "General",
    }


# ─── STEP 3: fetch product page ───────────────────────────────────────────────

async def fetch_product(client: httpx.AsyncClient, url: str) ->Optional[ dict]:
    """Fetch a single product page with httpx and parse it."""
    async with _SEM:
        await asyncio.sleep(random.uniform(0.3, 1.5))
        try:
            r = await client.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return _parse_product_html(r.text, url)
        except Exception as e:
            print(f"  [fetch error] {url[-60:]}: {e}")
            return None


# ─── STEP 4: save batch to SQLite ────────────────────────────────────────────

def save_to_sqlite(products: list[dict]) -> tuple[int, int, int]:
    """Write products directly via stdlib sqlite3 — no ORM or pydantic needed."""
    import sqlite3
    now = datetime.now().isoformat(sep=" ", timespec="seconds")

    con = sqlite3.connect(_DB_FILE)
    con.execute("PRAGMA journal_mode=WAL")
    # Ensure tables exist (minimal DDL; full schema created by Alembic on first run)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS scraper_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(255) UNIQUE NOT NULL,
            base_url VARCHAR(2048),
            active BOOLEAN DEFAULT 1,
            created_at DATETIME,
            updated_at DATETIME
        );
        CREATE TABLE IF NOT EXISTS scraper_brands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            external_id VARCHAR(255),
            name VARCHAR(500) NOT NULL,
            created_at DATETIME,
            updated_at DATETIME,
            UNIQUE(source_id, name)
        );
        CREATE TABLE IF NOT EXISTS scraper_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            external_id VARCHAR(255),
            name VARCHAR(500) NOT NULL,
            url VARCHAR(2048),
            created_at DATETIME,
            updated_at DATETIME,
            UNIQUE(source_id, name)
        );
        CREATE TABLE IF NOT EXISTS scraper_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            scraper_category_id INTEGER,
            scraper_brand_id INTEGER,
            external_id VARCHAR(255),
            source_url VARCHAR(2048),
            sku VARCHAR(255),
            name VARCHAR(1000) NOT NULL,
            description TEXT,
            specifications TEXT,
            price NUMERIC(12,2),
            raw_data TEXT,
            hash VARCHAR(255),
            is_synced BOOLEAN DEFAULT 0,
            synced_at DATETIME,
            last_scraped_at DATETIME,
            created_at DATETIME,
            updated_at DATETIME
        );
    """)

    # Get or create source
    row = con.execute("SELECT id FROM scraper_sources WHERE name=?", (SOURCE_NAME,)).fetchone()
    if row:
        source_id = row[0]
    else:
        cur = con.execute(
            "INSERT INTO scraper_sources(name,base_url,active,created_at,updated_at) VALUES(?,?,1,?,?)",
            (SOURCE_NAME, BASE_URL, now, now),
        )
        source_id = cur.lastrowid
        con.commit()

    brand_cache: dict[str, int] = {}
    cat_cache:   dict[str, int] = {}

    def get_brand(name: str) -> int:
        if name not in brand_cache:
            r = con.execute(
                "SELECT id FROM scraper_brands WHERE source_id=? AND name=?",
                (source_id, name),
            ).fetchone()
            if r:
                brand_cache[name] = r[0]
            else:
                cur = con.execute(
                    "INSERT INTO scraper_brands(source_id,name,external_id,created_at,updated_at) VALUES(?,?,?,?,?)",
                    (source_id, name, re.sub(r"[^\w]", "_", name.lower())[:80], now, now),
                )
                brand_cache[name] = cur.lastrowid
        return brand_cache[name]

    def get_category(name: str) -> int:
        if name not in cat_cache:
            r = con.execute(
                "SELECT id FROM scraper_categories WHERE source_id=? AND name=?",
                (source_id, name),
            ).fetchone()
            if r:
                cat_cache[name] = r[0]
            else:
                ext_id = re.sub(r"[^\w]", "_", name.lower())[:80]
                cur = con.execute(
                    "INSERT INTO scraper_categories(source_id,name,external_id,url,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                    (source_id, name, ext_id, "", now, now),
                )
                cat_cache[name] = cur.lastrowid
        return cat_cache[name]

    inserted = updated = skipped = 0

    for raw in products:
        name = (raw.get("name") or "").strip()
        if not name:
            skipped += 1
            continue

        external_id = raw.get("external_id", "")
        sku         = raw.get("sku") or external_id
        price       = raw.get("price")
        source_url  = raw.get("source_url", "")
        brand_name  = (raw.get("brand") or "Janoubco").strip()
        cat_name    = (raw.get("category") or "General").strip()

        cat_id   = get_category(cat_name)
        brand_id = get_brand(brand_name)
        raw_json = json.dumps(raw, ensure_ascii=False, default=str)

        existing = None
        if external_id:
            existing = con.execute(
                "SELECT id FROM scraper_products WHERE source_id=? AND external_id=?",
                (source_id, external_id),
            ).fetchone()

        if existing:
            con.execute(
                """UPDATE scraper_products
                   SET name=?, sku=?, price=?, source_url=?,
                       scraper_category_id=?, scraper_brand_id=?,
                       raw_data=?, last_scraped_at=?, updated_at=?
                   WHERE id=?""",
                (name, sku, price, source_url, cat_id, brand_id, raw_json, now, now, existing[0]),
            )
            updated += 1
        else:
            con.execute(
                """INSERT INTO scraper_products
                   (source_id, scraper_category_id, scraper_brand_id,
                    external_id, source_url, sku, name, price, raw_data,
                    is_synced, last_scraped_at, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,0,?,?,?)""",
                (source_id, cat_id, brand_id, external_id, source_url,
                 sku, name, price, raw_json, now, now, now),
            )
            inserted += 1

    con.commit()
    con.close()
    return inserted, updated, skipped


# ─── main ─────────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Scrape janoubco.com")
    parser.add_argument("--resume", action="store_true",
                        help="Skip already-saved products")
    args = parser.parse_args()

    print("=" * 60)
    print("  JANOUBCO.COM — FULL SITE SCRAPER")
    print("=" * 60)
    if has_proxies():
        print(f"  Proxy pool: {proxy_count()} proxies — rotating")
    else:
        print("  No proxies — running from local IP")

    if not _HAS_BS4:
        print("  [WARN] beautifulsoup4 not installed — using regex fallback")
        print("         pip install beautifulsoup4  for better extraction")

    # ── Load already-scraped IDs ───────────────────────────────────────────
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

    # ── STEP 1: collect all product URLs from sitemaps via httpx ─────────
    print("\n[STEP 1] Fetching product URLs from sitemaps...")
    proxy_url = next_httpx_proxy()
    client_kwargs: dict = {"timeout": 25, "follow_redirects": True, "headers": HEADERS}
    if proxy_url:
        client_kwargs["proxy"] = proxy_url

    async with httpx.AsyncClient(**client_kwargs) as client:
        all_urls = await fetch_all_product_urls(client)

        if not all_urls:
            print("  No URLs found — aborting")
            return

        # Filter already-scraped
        if already_scraped:
            filtered = [u for u in all_urls if _slug_from_url(u) not in already_scraped]
            print(f"  After resume filter: {len(filtered)} remaining")
        else:
            filtered = all_urls

        # Shuffle to avoid sequential patterns
        random.shuffle(filtered)
        n = len(filtered)

        # ── STEP 2: fetch + parse product pages concurrently ───────────────
        print(f"\n[STEP 2] Fetching {n} product pages "
              f"(concurrency={CONCURRENCY})...\n")

        total_ins = total_upd = total_skip = 0
        batch: list[dict] = []
        done = 0

        async def process(url: str):
            nonlocal done
            result = await fetch_product(client, url)
            done += 1
            return result

        tasks = [process(u) for u in filtered]

        for coro in asyncio.as_completed(tasks):
            result = await coro
            if result:
                batch.append(result)

            if len(batch) >= _BATCH_SAVE or (done == n and batch):
                ins, upd, sk = save_to_sqlite(batch)
                total_ins  += ins
                total_upd  += upd
                total_skip += sk
                print(f"  [{done}/{n}] Saved batch: +{ins} new, ~{upd} updated, "
                      f"{sk} skipped (total new: {total_ins})")
                batch = []

    print(f"\n{'=' * 60}")
    print(f"  DONE — inserted={total_ins}, updated={total_upd}, skipped={total_skip}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    # Install bs4 if missing
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        import subprocess
        print("[setup] Installing beautifulsoup4...")
        subprocess.run([sys.executable, "-m", "pip", "install", "beautifulsoup4", "-q"], check=False)

    asyncio.run(main())
