from typing import Optional
"""
scrape_microless.py
--------------------
Scrapes ALL products from saudi.microless.com.
Strategy:
  - Fetches sitemaps via httpx (sitemap pages are not bot-protected)
  - Fetches product pages via Playwright (httpx gets 403 Cloudflare block)
  - Extracts: name, SKU, price, brand, category, image, URL
  - Saves incrementally to scraper_data.db

Usage:
    python scrape_microless.py
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
try:
    from playwright.async_api import async_playwright, Browser, BrowserContext
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False

from _proxy_pool import next_playwright_proxy, next_httpx_proxy

BASE_URL     = "https://saudi.microless.com"
SOURCE_NAME  = "Microless Saudi"

# Sitemap hierarchy: sitemap.xml → sitemaps/saudi.xml → sitemap-saudi-en-N.xml
SITEMAP_SAUDI = "https://saudi.microless.com/sitemaps/saudi.xml"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en,ar;q=0.5",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Lower concurrency: Playwright is RAM-heavy
CONCURRENCY = 5
_SEM        = asyncio.Semaphore(CONCURRENCY)
_BATCH_SAVE = 50
PAGE_TIMEOUT = 30_000  # ms


# ─── helpers ──────────────────────────────────────────────────────────────────

def _parse_price(text: str) ->Optional[ float]:
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
    return url.rstrip("/").split("/")[-1].split("?")[0]


# ─── STEP 1: parse sitemaps ───────────────────────────────────────────────────

async def fetch_all_product_urls(client: httpx.AsyncClient) -> list[str]:
    """Fetch saudi.xml (sitemap index) → sub-sitemaps → product URLs."""
    try:
        r = await client.get(SITEMAP_SAUDI, headers=HEADERS, timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f"  [sitemap error] {e}")
        return []

    sub_sitemaps: list[str] = []
    try:
        root = ET.fromstring(r.text)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        for loc in root.findall(".//sm:loc", ns):
            u = (loc.text or "").strip()
            if u and "sitemap-saudi-en" in u:
                sub_sitemaps.append(u)
    except ET.ParseError:
        sub_sitemaps = re.findall(
            r'https://saudi\.microless\.com/sitemaps/sitemap-saudi-en-\d+\.xml',
            r.text,
        )

    if not sub_sitemaps:
        # Fallback: parse any loc entries as product URLs directly
        try:
            root = ET.fromstring(r.text)
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            urls = []
            for loc in root.findall(".//sm:loc", ns):
                u = (loc.text or "").strip()
                if u and "/product/" in u:
                    urls.append(u)
            if urls:
                print(f"  Found {len(urls)} product URLs directly in saudi.xml")
                return list(dict.fromkeys(urls))
        except Exception:
            pass

    print(f"  Found {len(sub_sitemaps)} product sitemap files")

    async def fetch_sub_sitemap(url: str) -> list[str]:
        try:
            resp = await client.get(url, headers=HEADERS, timeout=60)
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            return [
                (loc.text or "").strip()
                for loc in root.findall(".//sm:loc", ns)
                if loc.text and "/product/" in loc.text
            ]
        except Exception as e:
            print(f"  [sub-sitemap error] {url}: {e}")
            return []

    results = await asyncio.gather(*[fetch_sub_sitemap(u) for u in sub_sitemaps])
    all_urls = list(dict.fromkeys(u for batch in results for u in batch if u))
    print(f"  Total product URLs: {len(all_urls)}")
    return all_urls


# ─── STEP 2: parse a single product page ─────────────────────────────────────

def _parse_product_html(html: str, url: str) ->Optional[ dict]:
    if not html:
        return None

    name = sku = brand = category = image_url = None
    price = original_price = None

    if _HAS_BS4:
        soup = BeautifulSoup(html, "html.parser")

        # ── Name ──────────────────────────────────────────────────────────
        for sel in ["h1.product-title", "h1[itemprop='name']", "h1.title", "h1"]:
            el = soup.select_one(sel)
            if el:
                name = el.get_text(" ", strip=True)
                break

        # ── JSON-LD (price, SKU, brand, image) ────────────────────────────
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.string or "")
                if not isinstance(data, dict):
                    continue
                # Handle @graph wrapper
                items = data.get("@graph", [data])
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
                            image_url = img[0]
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

        # ── SKU fallback: "Microless SKU 186049" in spec table ────────────
        if not sku:
            for el in soup.select("td, th, li, span"):
                t = el.get_text(strip=True)
                if t.startswith("Microless SKU"):
                    m = re.search(r'Microless SKU\s+(\S+)', t)
                    if m:
                        sku = m.group(1)
                        break
        # Also try manufacturer part number from product name after "|"
        if not sku and name and "|" in name:
            sku = name.split("|")[-1].strip()

        # ── Price: meta tags (OG / product namespace) ─────────────────────
        if not price:
            for attr in [
                ("property", "product:price:amount"),
                ("property", "og:price:amount"),
                ("name",     "price"),
                ("itemprop", "price"),
            ]:
                el = soup.find("meta", {attr[0]: attr[1]})
                if el:
                    price = _parse_price(el.get("content", ""))
                    if price:
                        break

        # ── Price: data-* attributes on any element ────────────────────────
        if not price:
            for attr in ["data-price", "data-current-price", "data-sale-price",
                         "data-final-price", "data-product-price"]:
                el = soup.find(attrs={attr: True})
                if el:
                    price = _parse_price(el[attr])
                    if price:
                        break

        # ── Price: CSS selectors (Microless-specific → generic) ────────────
        if not price:
            for sel in [
                # Microless DOM: div.product-main-price.priceFormat > span.price-amount
                ".product-main-price .price-amount",
                ".priceFormat .price-amount",
                ".product-price-wrapper .price-amount",
                ".prices .price-amount",
                "span.price-amount",
                # Generic e-commerce selectors
                "[itemprop='price']",
                ".current-price", ".sale-price", ".selling-price",
                ".product-price", ".price-tag", ".final-price",
                ".special-price .price", ".price ins .amount",
                ".price .amount", ".price",
            ]:
                el = soup.select_one(sel)
                if el:
                    content = el.get("content") or el.get("data-price") or el.get_text(strip=True)
                    price = _parse_price(content)
                    if price:
                        break

        # ── Price: inline JS variables ─────────────────────────────────────
        if not price:
            for script in soup.find_all("script"):
                js = script.string or ""
                # e.g. "price":162.49  or  currentPrice = 162.49
                m = re.search(
                    r'(?:"price"|currentPrice|salePrice|finalPrice|productPrice)'
                    r'\s*[=:]\s*([\d]+(?:\.\d+)?)',
                    js,
                )
                if m:
                    price = _parse_price(m.group(1))
                    if price:
                        break

        # ── Price: regex on full HTML (last resort) ────────────────────────
        if not price:
            # "SAR 162.49"  or  "162.49SAR"  or  "SAR&nbsp;162.49"
            for pattern in [
                r'SAR[\s\xa0]*([\d,]+(?:\.\d+)?)',
                r'([\d,]+(?:\.\d+)?)\s*SAR',
            ]:
                m = re.search(pattern, html)
                if m:
                    price = _parse_price(m.group(1))
                    if price:
                        break

        # ── Original / was-price ───────────────────────────────────────────
        for sel in [
            ".original-price", ".was-price", ".old-price", ".price-old",
            ".price-was", "del .price-amount", "del span", "s .amount",
            ".discounts .price-was",
        ]:
            el = soup.select_one(sel)
            if el:
                original_price = _parse_price(el.get_text(strip=True))
                if original_price:
                    break
        if not original_price:
            for pattern in [
                r'Was\s+SAR\s*([\d,]+(?:\.\d+)?)',
                r'SAR\s*([\d,]+(?:\.\d+)?)\s*<[^>]+>\s*(?:was|before)',
            ]:
                m = re.search(pattern, html, re.IGNORECASE)
                if m:
                    original_price = _parse_price(m.group(1))
                    if original_price:
                        break

        # ── Brand fallback: link to /b/<brand-name>/ ───────────────────────
        if not brand:
            for a in soup.select("a[href*='/b/']"):
                href = a.get("href", "")
                # Must end with brand slug + "/"
                if re.search(r'/b/[^/]+/$', href):
                    brand = a.get_text(strip=True)
                    if brand:
                        break

        # ── Category from breadcrumb ───────────────────────────────────────
        crumbs = soup.select(".breadcrumb a, [itemtype*='BreadcrumbList'] a, nav.breadcrumb a")
        # Skip first (Home) and last (product itself); take second-to-last
        for crumb in reversed(crumbs[:-1] if crumbs else []):
            t = crumb.get_text(strip=True)
            if t and t.lower() not in ("home", "الرئيسية", ""):
                category = t
                break

        # ── Image fallback ─────────────────────────────────────────────────
        if not image_url:
            for sel in [
                ".product-image img[src]", "img[itemprop='image']",
                ".gallery img[src]", "#main-image img[src]",
            ]:
                el = soup.select_one(sel)
                if el:
                    src = el.get("src") or el.get("data-src") or ""
                    if src and "placeholder" not in src:
                        image_url = src if src.startswith("http") else BASE_URL + src
                        break

    else:
        # No BeautifulSoup — regex fallback
        m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        if m:
            name = m.group(1).strip()
        m = re.search(r'SAR\s*([\d,]+(?:\.\d+)?)', html)
        if m:
            price = _parse_price(m.group(1))

    if not name:
        return None

    slug        = _slug_from_url(url)
    external_id = slug

    return {
        "external_id":    external_id,
        "sku":            sku or external_id,
        "name":           name,
        "price":          price,
        "original_price": original_price,
        "source_url":     url,
        "image_url":      image_url or "",
        "brand":          brand or "Microless",
        "category":       category or "General",
    }


# ─── STEP 3: fetch product page via Playwright ──────────────────────────────

async def fetch_product(context: BrowserContext, url: str) ->Optional[ dict]:
    async with _SEM:
        await asyncio.sleep(random.uniform(0.3, 1.5))
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
            await page.wait_for_timeout(1000)
            html = await page.content()
            return _parse_product_html(html, url)
        except Exception as e:
            print(f"  [playwright error] {url[-60:]}: {e}")
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
        brand_name  = (raw.get("brand") or "Microless").strip()
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
    print("  MICROLESS SAUDI SCRAPER  (Playwright)")
    print("=" * 60)

    # Step 1: collect URLs via httpx (sitemaps are not bot-protected)
    httpx_proxy = next_httpx_proxy()
    client_kwargs: dict = {"follow_redirects": True, "timeout": 30}
    if httpx_proxy:
        client_kwargs["proxy"] = httpx_proxy

    print("\n[1/3] Collecting product URLs from sitemaps...")
    async with httpx.AsyncClient(**client_kwargs) as client:
        product_urls = await fetch_all_product_urls(client)
    if not product_urls:
        print("  No product URLs found — exiting")
        return

    total = len(product_urls)
    print(f"\n[2/3] Fetching {total} product pages via Playwright (concurrency={CONCURRENCY})...")

    playwright_proxy = next_playwright_proxy()
    launch_kwargs: dict = {"headless": True}
    if playwright_proxy:
        launch_kwargs["proxy"] = playwright_proxy
        print(f"  Using proxy: {playwright_proxy.get('server', '')[:40]}...")
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
            locale="en",
        )

        tasks = [fetch_product(context, u) for u in product_urls]
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
            if done % 100 == 0 or done == total:
                print(f"  [{done}/{total}] inserted={total_inserted} updated={total_updated}")

        if batch:
            ins, upd, skp = save_to_sqlite(batch)
            total_inserted += ins
            total_updated  += upd
            total_skipped  += skp

        await browser.close()

    print(f"\n[3/3] DONE — inserted={total_inserted}, updated={total_updated}, skipped={total_skipped}")


if __name__ == "__main__":
    if not HAS_PLAYWRIGHT:
        print("ERROR: Playwright is not installed. This scraper requires a browser environment.")
        print("Run locally with: pip install playwright && playwright install chromium")
        sys.exit(1)
    asyncio.run(main())
