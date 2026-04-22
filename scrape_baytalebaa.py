"""
scrape_baytalebaa.py
---------------------
Scrapes ALL products from baytalebaa.com (Prestashop, AR — building materials,
swimming pool mosaics, artificial grass, etc.).

The site redirects plain HTTP requests to a tracking pixel — Playwright (headless
Chromium) is required to render the page properly.

Strategy:
  - Fetches sitemap.xml (accessible via HTTP) → sitemap-products-N.xml files
  - Filters to Arabic-locale URLs only  (/ar/ prefix)
  - Uses Playwright to visit each product page and extract data
  - Saves incrementally to scraper_data.db

Usage:
    python scrape_baytalebaa.py
"""
import asyncio
import json
import re
import sys
import os
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
from playwright.async_api import async_playwright, Browser, BrowserContext

try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False

from _proxy_pool import next_playwright_proxy, next_httpx_proxy

BASE_URL    = "https://baytalebaa.com"
SOURCE_NAME = "Baytalebaa"
SITEMAP_INDEX = "https://baytalebaa.com/sitemap.xml"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ar,en;q=0.5",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Lower concurrency: Playwright is RAM-heavy
CONCURRENCY = 4
_SEM        = asyncio.Semaphore(CONCURRENCY)
_BATCH_SAVE = 20
PAGE_TIMEOUT = 30_000   # ms


# ─── helpers ──────────────────────────────────────────────────────────────────

def _parse_price(text: str) -> float | None:
    if not text:
        return None
    m = re.search(r'\d[\d,]*(?:\.\d+)?', text.replace('\u060c', ''))
    if m:
        try:
            v = float(m.group().replace(',', ''))
            return v if v > 0 else None
        except ValueError:
            return None
    return None


def _slug_from_url(url: str) -> str:
    return url.rstrip("/").split("/")[-1].split("?")[0].replace(".html", "")


# ─── STEP 1: parse sitemaps via plain HTTP ─────────────────────────────────────

async def fetch_all_product_urls() -> list[str]:
    """Fetch sitemap index → product sitemaps → all Arabic product URLs."""
    proxy = next_httpx_proxy()
    client_kwargs: dict = {"follow_redirects": True, "timeout": 30}
    if proxy:
        client_kwargs["proxy"] = proxy

    async with httpx.AsyncClient(**client_kwargs) as client:
        # Fetch the sitemap index
        try:
            r = await client.get(SITEMAP_INDEX, headers=HEADERS, timeout=30)
            r.raise_for_status()
        except Exception as e:
            print(f"  [sitemap index error] {e}")
            return []

        # Find product sitemap URLs
        product_sitemaps: list[str] = []
        try:
            root = ET.fromstring(r.text)
            for loc in root.iter():
                if loc.tag.endswith("}loc") or loc.tag == "loc":
                    u = (loc.text or "").strip()
                    if u and "sitemap-products" in u:
                        product_sitemaps.append(u)
        except ET.ParseError:
            product_sitemaps = re.findall(
                r'https://baytalebaa\.com/sitemap-products[^<\s"]+\.xml',
                r.text,
            )

        print(f"  Found {len(product_sitemaps)} product sitemap files")

        all_urls: list[str] = []
        for sitemap_url in product_sitemaps:
            try:
                resp = await client.get(sitemap_url, headers=HEADERS, timeout=60)
                resp.raise_for_status()
                root = ET.fromstring(resp.text)
                for loc in root.iter():
                    if loc.tag.endswith("}loc") or loc.tag == "loc":
                        u = (loc.text or "").strip()
                        # Keep only Arabic-locale product pages
                        if u and "/ar/" in u and u.endswith(".html"):
                            all_urls.append(u)
            except Exception as e:
                print(f"  [sitemap fetch error] {sitemap_url}: {e}")

    # Deduplicate
    all_urls = list(dict.fromkeys(all_urls))
    print(f"  Total Arabic product URLs: {len(all_urls)}")
    return all_urls


# ─── STEP 2: parse HTML from a loaded Playwright page ─────────────────────────

def _parse_product_html(html: str, url: str) -> dict | None:
    """Extract fields from Prestashop product page HTML."""
    if not html:
        return None

    name = sku = brand = category = image_url = None
    price = original_price = None

    if _HAS_BS4:
        soup = BeautifulSoup(html, "html.parser")

        # ── Name ──────────────────────────────────────────────────────────
        for sel in [
            "h1.product-detail-name", "h1[itemprop='name']",
            ".product-name h1", "h1.product-name", "h1",
        ]:
            el = soup.select_one(sel)
            if el:
                name = el.get_text(" ", strip=True)
                break

        # ── JSON-LD ────────────────────────────────────────────────────────
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.string or "")
                items = [data] if isinstance(data, dict) else (data if isinstance(data, list) else [])
                for item in items:
                    if item.get("@type") != "Product":
                        continue
                    if not name:
                        name = item.get("name")
                    if not sku:
                        sku = item.get("sku") or item.get("mpn")
                    if not brand:
                        b = item.get("brand")
                        if isinstance(b, dict):
                            brand = b.get("name")
                        elif isinstance(b, str):
                            brand = b
                    if not image_url:
                        img = item.get("image")
                        if isinstance(img, list) and img:
                            image_url = img[0] if isinstance(img[0], str) else img[0].get("url", "")
                        elif isinstance(img, str):
                            image_url = img
                    if not price:
                        offers = item.get("offers", {})
                        if isinstance(offers, dict):
                            p = offers.get("price")
                            if p:
                                price = _parse_price(str(p))
                    break
            except Exception:
                pass

        # ── Price CSS ──────────────────────────────────────────────────────
        if not price:
            for sel in [
                ".product-prices .price", "[itemprop='price']",
                ".current-price .price", ".current-price",
                ".product-price", ".price",
            ]:
                el = soup.select_one(sel)
                if el:
                    content = el.get("content") or el.get_text(strip=True)
                    price = _parse_price(content)
                    if price:
                        break

        # ── Original price ─────────────────────────────────────────────────
        for sel in [".regular-price", ".old-price", ".product-discount .price"]:
            el = soup.select_one(sel)
            if el:
                original_price = _parse_price(el.get_text(strip=True))
                break

        # ── SKU / Reference ────────────────────────────────────────────────
        if not sku:
            for sel in [
                ".product-reference .value", "[itemprop='sku']",
                ".sku .value", ".reference .value",
            ]:
                el = soup.select_one(sel)
                if el:
                    sku = el.get_text(strip=True)
                    if sku:
                        break

        # ── Brand ─────────────────────────────────────────────────────────
        if not brand:
            for sel in [
                ".product-manufacturer a", "[itemprop='brand'] [itemprop='name']",
                ".brand a", ".manufacturer a",
            ]:
                el = soup.select_one(sel)
                if el:
                    brand = el.get_text(strip=True)
                    if brand:
                        break

        # ── Category from breadcrumb ───────────────────────────────────────
        crumbs = soup.select(
            ".breadcrumb li a, [itemtype*='BreadcrumbList'] a, "
            "nav.breadcrumb a, ol.breadcrumb li a"
        )
        # Skip first (Home) and last (product name)
        for crumb in reversed(crumbs[:-1] if crumbs else []):
            t = crumb.get_text(strip=True)
            if t and t.lower() not in ("home", "الرئيسية", "accueil", ""):
                category = t
                break

        # ── Image ─────────────────────────────────────────────────────────
        if not image_url:
            for sel in [
                ".product-cover img[src]", "img[itemprop='image']",
                ".images-container img[src]", ".product-images img[src]",
                "#product-images-large img[src]",
            ]:
                el = soup.select_one(sel)
                if el:
                    src = el.get("src") or el.get("data-src") or ""
                    if src and "placeholder" not in src.lower():
                        image_url = src if src.startswith("http") else BASE_URL + src
                        break

    else:
        m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        if m:
            name = m.group(1).strip()
        m2 = re.search(r'"price"\s*:\s*"?([\d.]+)"?', html)
        if m2:
            price = _parse_price(m2.group(1))

    if not name:
        return None

    slug        = _slug_from_url(url)
    external_id = slug

    return {
        "external_id":    external_id,
        "sku":            sku or slug,
        "name":           name,
        "price":          price,
        "original_price": original_price,
        "source_url":     url,
        "image_url":      image_url or "",
        "brand":          brand or "Baytalebaa",
        "category":       category or "General",
    }


# ─── STEP 3: fetch product page via Playwright ────────────────────────────────

async def fetch_product_playwright(context: BrowserContext, url: str) -> dict | None:
    async with _SEM:
        await asyncio.sleep(random.uniform(0.5, 2.0))
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
            # Wait briefly for any price JS to render
            await page.wait_for_timeout(1500)
            html = await page.content()
            return _parse_product_html(html, url)
        except Exception as e:
            print(f"  [playwright error] {url[-70:]}: {e}")
            return None
        finally:
            await page.close()


# ─── STEP 4: save batch to SQLite ─────────────────────────────────────────────

def save_to_sqlite(products: list[dict]) -> tuple[int, int, int]:
    import sqlite3
    now = datetime.now().isoformat(sep=" ", timespec="seconds")

    con = sqlite3.connect(_DB_FILE)
    con.execute("PRAGMA journal_mode=WAL")
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

    def get_brand(n: str) -> int:
        if n not in brand_cache:
            r = con.execute(
                "SELECT id FROM scraper_brands WHERE source_id=? AND name=?", (source_id, n)
            ).fetchone()
            if r:
                brand_cache[n] = r[0]
            else:
                cur = con.execute(
                    "INSERT INTO scraper_brands(source_id,name,external_id,created_at,updated_at) VALUES(?,?,?,?,?)",
                    (source_id, n, re.sub(r"[^\w]", "_", n.lower())[:80], now, now),
                )
                brand_cache[n] = cur.lastrowid
        return brand_cache[n]

    def get_category(n: str) -> int:
        if n not in cat_cache:
            r = con.execute(
                "SELECT id FROM scraper_categories WHERE source_id=? AND name=?", (source_id, n)
            ).fetchone()
            if r:
                cat_cache[n] = r[0]
            else:
                cur = con.execute(
                    "INSERT INTO scraper_categories(source_id,name,external_id,url,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                    (source_id, n, re.sub(r"[^\w]", "_", n.lower())[:80], "", now, now),
                )
                cat_cache[n] = cur.lastrowid
        return cat_cache[n]

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
        brand_name  = (raw.get("brand") or "Baytalebaa").strip()
        cat_name    = (raw.get("category") or "General").strip()
        cat_id      = get_category(cat_name)
        brand_id    = get_brand(brand_name)
        raw_json    = json.dumps(raw, ensure_ascii=False, default=str)

        existing = None
        if external_id:
            existing = con.execute(
                "SELECT id FROM scraper_products WHERE source_id=? AND external_id=?",
                (source_id, external_id),
            ).fetchone()

        if existing:
            con.execute("""
                UPDATE scraper_products SET
                    name=?, sku=?, price=?, source_url=?,
                    scraper_category_id=?, scraper_brand_id=?,
                    raw_data=?, last_scraped_at=?, updated_at=?
                WHERE id=?
            """, (name, sku, price, source_url, cat_id, brand_id, raw_json, now, now, existing[0]))
            updated += 1
        else:
            con.execute("""
                INSERT INTO scraper_products
                    (source_id, scraper_category_id, scraper_brand_id, external_id,
                     source_url, sku, name, price, raw_data,
                     is_synced, last_scraped_at, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,0,?,?,?)
            """, (source_id, cat_id, brand_id, external_id,
                  source_url, sku, name, price, raw_json, now, now, now))
            inserted += 1

    con.commit()
    con.close()
    return inserted, updated, skipped


# ─── main ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    print("=" * 60)
    print("  BAYTALEBAA SCRAPER  (Playwright)")
    print("=" * 60)

    print("\n[1/3] Collecting product URLs from sitemaps...")
    product_urls = await fetch_all_product_urls()
    if not product_urls:
        print("  No product URLs found — exiting")
        return

    total = len(product_urls)
    print(f"\n[2/3] Fetching {total} product pages via Playwright (concurrency={CONCURRENCY})...")

    proxy = next_playwright_proxy()
    launch_kwargs: dict = {"headless": True}
    if proxy:
        launch_kwargs["proxy"] = proxy
        print(f"  Using proxy: {proxy.get('server', '')[:40]}...")
    else:
        print("  No proxy — direct connection")

    done = 0
    batch: list[dict] = []
    total_inserted = total_updated = total_skipped = 0

    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(**launch_kwargs)
        context: BrowserContext = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="ar",
            extra_http_headers={"Accept-Language": "ar,en;q=0.5"},
        )

        tasks = [fetch_product_playwright(context, u) for u in product_urls]
        for coro in asyncio.as_completed(tasks):
            result = await coro
            done += 1
            if result:
                batch.append(result)
            if len(batch) >= _BATCH_SAVE:
                ins, upd, skp = save_to_sqlite(batch)
                total_inserted += ins
                total_updated  += upd
                total_skipped  += skp
                batch = []
            if done % 20 == 0 or done == total:
                print(f"  [{done}/{total}] inserted={total_inserted} updated={total_updated}")

        if batch:
            ins, upd, skp = save_to_sqlite(batch)
            total_inserted += ins
            total_updated  += upd
            total_skipped  += skp

        await browser.close()

    print(f"\n[3/3] DONE — inserted={total_inserted}, updated={total_updated}, skipped={total_skipped}")


if __name__ == "__main__":
    asyncio.run(main())
