from typing import Optional
"""
scrape_mejdaf.py
-----------------
Scrapes ALL products from mejdaf.com (OpenCart, KSA test/measurement & IT tools).
Strategy:
  - Parses the single sitemap.xml for product URLs
  - Deduplicates by product_id (sitemap has both route=product/product and
    route=themecontrol/product duplicates — only keep the canonical form)
  - Concurrently fetches product pages with httpx + BeautifulSoup
  - Extracts: name, SKU/product code, price, brand, category, image, URL
  - Saves incrementally to scraper_data.db

Usage:
    python scrape_mejdaf.py
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
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False

from _proxy_pool import next_httpx_proxy

BASE_URL    = "https://www.mejdaf.com"
SOURCE_NAME = "Mejdaf"
SITEMAP_URL = "https://www.mejdaf.com/sitemap.xml"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ar,en;q=0.5",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

CONCURRENCY = 10
_SEM: Optional[asyncio.Semaphore] = None
_BATCH_SAVE = 50


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


# ─── STEP 1: parse sitemap ────────────────────────────────────────────────────

async def fetch_all_product_urls(client: httpx.AsyncClient) -> list[str]:
    """Parse sitemap.xml, return canonical product URLs deduplicated by product_id."""
    try:
        r = await client.get(SITEMAP_URL, headers=HEADERS, timeout=60)
        r.raise_for_status()
    except Exception as e:
        print(f"  [sitemap error] {e}")
        return []

    raw_urls: list[str] = []
    try:
        root = ET.fromstring(r.text)
        for loc in root.iter():
            if loc.tag.endswith("}loc") or loc.tag == "loc":
                u = (loc.text or "").strip()
                if u and "route=product/product" in u and "product_id=" in u:
                    raw_urls.append(u)
    except ET.ParseError:
        raw_urls = re.findall(
            r'https://www\.mejdaf\.com/index\.php\?route=product/product[^<\s"]+product_id=\d+',
            r.text,
        )

    # Deduplicate by product_id — use canonical URL without path=X
    seen: set[str] = set()
    deduped: list[str] = []
    for u in raw_urls:
        m = re.search(r'product_id=(\d+)', u)
        if m:
            pid = m.group(1)
            if pid not in seen:
                seen.add(pid)
                deduped.append(f"{BASE_URL}/index.php?route=product/product&product_id={pid}")

    print(f"  Found {len(deduped)} unique product URLs")
    return deduped


# ─── STEP 2: parse a single product page ─────────────────────────────────────

def _parse_product_html(html: str, url: str) ->Optional[ dict]:
    if not html:
        return None

    name = sku = brand = category = image_url = None
    price = None

    m = re.search(r'product_id=(\d+)', url)
    product_id = m.group(1) if m else ""

    if _HAS_BS4:
        soup = BeautifulSoup(html, "html.parser")

        # ── Name ──────────────────────────────────────────────────────────
        for sel in [
            "h1.product-title", "#product-name", "h1[itemprop='name']",
            ".product-title h1", "h1",
        ]:
            el = soup.select_one(sel)
            if el:
                name = el.get_text(" ", strip=True)
                break

        # ── Price ─────────────────────────────────────────────────────────
        # OpenCart shows "32.20SAR" or "1,745.70SAR" — grab the first numeric segment
        for sel in [
            ".product-price", "[itemprop='price']",
            ".price", "#product_price", ".price-new",
        ]:
            el = soup.select_one(sel)
            if el:
                content = el.get("content") or el.get_text(strip=True)
                # Skip "ASK FOR PRICE" / "اطلب السعر"
                if re.search(r'[Aa][Ss][Kk]|اطلب|بالسعر', content):
                    break
                price = _parse_price(content)
                if price:
                    break

        if not price:
            # Regex: "32.20SAR" or "1,745.70SAR" or "SAR 32.20"
            m_price = re.search(r'([\d,]+(?:\.\d+)?)\s*SAR', html)
            if m_price:
                price = _parse_price(m_price.group(1))

        # ── Brand ─────────────────────────────────────────────────────────
        for sel in [".product-manufacturer a", "[itemprop='brand']", ".manufacturer a"]:
            el = soup.select_one(sel)
            if el:
                brand = el.get_text(strip=True)
                if brand:
                    break
        if not brand:
            m_brand = re.search(r'Brand:\s*([^\n<]+)', html)
            if m_brand:
                brand = m_brand.group(1).strip()

        # ── SKU / Product Code ─────────────────────────────────────────────
        for sel in [".product-model", "[itemprop='sku']", ".sku"]:
            el = soup.select_one(sel)
            if el:
                t = el.get_text(strip=True)
                sku = re.sub(r'^(Product Code:|Model:|SKU:)\s*', '', t, flags=re.I).strip()
                if sku:
                    break
        if not sku:
            m_sku = re.search(r'Product Code:\s*([A-Za-z0-9\-_\.]+)', html)
            if m_sku:
                sku = m_sku.group(1).strip()

        # ── Category from breadcrumb ───────────────────────────────────────
        crumbs = soup.select("#breadcrumb a, .breadcrumb a, li.breadcrumb-item a")
        if len(crumbs) >= 2:
            # Take last breadcrumb link (category, not product name)
            category = crumbs[-1].get_text(strip=True)

        # ── Image ─────────────────────────────────────────────────────────
        for sel in ["img[itemprop='image']", ".product-image img", "#image img"]:
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
        m2 = re.search(r'([\d,]+(?:\.\d+)?)\s*SAR', html)
        if m2:
            price = _parse_price(m2.group(1))

    if not name:
        return None

    external_id = f"mejdaf-{product_id}" if product_id else sku or name[:50]

    return {
        "external_id": external_id,
        "sku":         sku or product_id,
        "name":        name,
        "price":       price,
        "source_url":  url,
        "image_url":   image_url or "",
        "brand":       brand or "Mejdaf",
        "category":    category or "General",
    }


# ─── STEP 3: fetch product page ───────────────────────────────────────────────

async def fetch_product(client: httpx.AsyncClient, url: str) ->Optional[ dict]:
    async with _SEM:
        await asyncio.sleep(random.uniform(0.3, 1.5))
        try:
            r = await client.get(url, headers=HEADERS, timeout=25)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return _parse_product_html(r.text, url)
        except Exception as e:
            print(f"  [fetch error] {url[-60:]}: {e}")
            return None


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
        brand_name  = (raw.get("brand") or "Mejdaf").strip()
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
    global _SEM
    _SEM = asyncio.Semaphore(CONCURRENCY)
    print("=" * 60)
    print("  MEJDAF SCRAPER")
    print("=" * 60)

    proxy = next_httpx_proxy()
    client_kwargs: dict = {"follow_redirects": True, "timeout": 30}
    if proxy:
        client_kwargs["proxy"] = proxy
        print(f"  Using proxy: {proxy[:40]}...")
    else:
        print("  No proxy — direct connection")

    async with httpx.AsyncClient(**client_kwargs) as client:
        print("\n[1/3] Collecting product URLs from sitemap...")
        product_urls = await fetch_all_product_urls(client)
        if not product_urls:
            print("  No product URLs found — exiting")
            return

        total = len(product_urls)
        print(f"\n[2/3] Fetching {total} product pages (concurrency={CONCURRENCY})...")
        done = 0
        batch: list[dict] = []
        total_inserted = total_updated = total_skipped = 0

        tasks = [fetch_product(client, u) for u in product_urls]
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
            if done % 50 == 0 or done == total:
                print(f"  [{done}/{total}] inserted={total_inserted} updated={total_updated}")

        if batch:
            ins, upd, skp = save_to_sqlite(batch)
            total_inserted += ins
            total_updated  += upd
            total_skipped  += skp

    print(f"\n[3/3] DONE — inserted={total_inserted}, updated={total_updated}, skipped={total_skipped}")


if __name__ == "__main__":
    asyncio.run(main())
