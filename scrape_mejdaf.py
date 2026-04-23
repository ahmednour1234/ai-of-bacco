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
_CHARSET_FIXED = False  # run utf8mb4 ALTER TABLE only once


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
    """Write products via SQLAlchemy ORM — supports both SQLite and MySQL."""
    from scraper.models.source import ScraperSource
    from scraper.models.category import ScraperCategory
    from scraper.models.brand import ScraperBrand
    from scraper.models.product import ScraperProduct
    from scraper.core.database import ScraperBase
    from sqlalchemy import create_engine, select, text
    from sqlalchemy.orm import Session

    db_url = os.environ.get("SCRAPER_DATABASE_URL_SYNC", f"sqlite:///{_DB_FILE}")
    if "mysql" in db_url and "charset=" not in db_url:
        db_url += ("&" if "?" in db_url else "?") + "charset=utf8mb4"
    engine = create_engine(db_url, echo=False)
    ScraperBase.metadata.create_all(engine)
    global _CHARSET_FIXED
    if "mysql" in db_url and not _CHARSET_FIXED:
        for _t in ["scraper_sources", "scraper_categories", "scraper_brands", "scraper_sync_logs"]:
            try:
                with engine.connect() as _conn:
                    _conn.execute(text(f"ALTER TABLE `{_t}` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
                    _conn.commit()
            except Exception:
                pass
        for _stmt in [
            "ALTER TABLE `scraper_products` MODIFY COLUMN `name` VARCHAR(1000) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL",
            "ALTER TABLE `scraper_products` MODIFY COLUMN `description` TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
            "ALTER TABLE `scraper_products` MODIFY COLUMN `specifications` TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
            "ALTER TABLE `scraper_products` MODIFY COLUMN `raw_data` TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
            "ALTER TABLE `scraper_products` MODIFY COLUMN `external_id` VARCHAR(191) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
            "ALTER TABLE `scraper_products` MODIFY COLUMN `sku` VARCHAR(191) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
            "ALTER TABLE `scraper_products` MODIFY COLUMN `hash` VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
            "DROP INDEX `ix_scraper_products_source_url` ON `scraper_products`",
            "ALTER TABLE `scraper_products` MODIFY COLUMN `source_url` VARCHAR(2048) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL",
            "CREATE INDEX `ix_scraper_products_source_url` ON `scraper_products` (`source_id`, `source_url`(191))",
        ]:
            try:
                with engine.connect() as _conn:
                    _conn.execute(text(_stmt))
                    _conn.commit()
            except Exception:
                pass
        _CHARSET_FIXED = True

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
        cat_cache:   dict[str, ScraperCategory] = {}

        def get_brand(name: str) -> ScraperBrand:
            if name not in brand_cache:
                b = session.execute(
                    select(ScraperBrand).where(
                        ScraperBrand.source_id == source.id,
                        ScraperBrand.name == name,
                    )
                ).scalar_one_or_none()
                if not b:
                    b = ScraperBrand(source_id=source.id, name=name,
                                     external_id=re.sub(r"[^\w]", "_", name.lower())[:80])
                    session.add(b)
                    session.flush()
                brand_cache[name] = b
            return brand_cache[name]

        def get_category(name: str) -> ScraperCategory:
            if name not in cat_cache:
                c = session.execute(
                    select(ScraperCategory).where(
                        ScraperCategory.source_id == source.id,
                        ScraperCategory.name == name,
                    )
                ).scalar_one_or_none()
                if not c:
                    c = ScraperCategory(source_id=source.id, name=name,
                                        external_id=re.sub(r"[^\w]", "_", name.lower())[:80],
                                        url="")
                    session.add(c)
                    session.flush()
                cat_cache[name] = c
            return cat_cache[name]

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

            category = get_category(cat_name)
            brand    = get_brand(brand_name)
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
                try:
                    ins, upd, skp = save_to_sqlite(batch)
                    total_inserted += ins
                    total_updated  += upd
                    total_skipped  += skp
                except Exception as db_err:
                    print(f"  [save error] {db_err}")
                batch = []
            if done % 50 == 0 or done == total:
                print(f"  [{done}/{total}] inserted={total_inserted} updated={total_updated}")

        if batch:
            try:
                ins, upd, skp = save_to_sqlite(batch)
                total_inserted += ins
                total_updated  += upd
                total_skipped  += skp
            except Exception as db_err:
                print(f"  [save error] {db_err}")

    print(f"\n[3/3] DONE — inserted={total_inserted}, updated={total_updated}, skipped={total_skipped}")


if __name__ == "__main__":
    asyncio.run(main())
