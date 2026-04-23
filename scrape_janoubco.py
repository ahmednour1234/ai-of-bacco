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
try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False

from _proxy_pool import next_httpx_proxy, has_proxies, count as proxy_count

BASE_URL    = "https://janoubco.com"
SOURCE_NAME = "Janoubco"

# Sitemap index: 11 product sitemaps + category + brand
SITEMAP_INDEX = "https://janoubco.com/sitemap.xml"

# Rotate User-Agents to reduce fingerprinting
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
]
_ua_idx = 0
_ua_lock = __import__('threading').Lock()


def _next_ua() -> str:
    global _ua_idx
    with _ua_lock:
        ua = _USER_AGENTS[_ua_idx % len(_USER_AGENTS)]
        _ua_idx += 1
    return ua


def _build_headers() -> dict:
    return {**HEADERS, "User-Agent": _next_ua()}


HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

# Known product sitemap pattern — used as fallback when sitemap index is blocked
_PRODUCT_SITEMAP_PATTERN = [
    f"{BASE_URL}/sitemap-product-{i}.xml" for i in range(1, 15)
]

# Concurrency: how many product pages to fetch simultaneously
CONCURRENCY = 12
_SEM: Optional[asyncio.Semaphore] = None
_BATCH_SAVE = 50   # save to DB every N products
_CHARSET_FIXED = False  # run utf8mb4 ALTER TABLE only once


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

def _make_client(timeout: int = 20, force_direct: bool = False) -> httpx.AsyncClient:
    """Create a fresh httpx client, optionally with a rotating proxy."""
    proxy_url = None if force_direct else next_httpx_proxy()
    kwargs: dict = {"timeout": timeout, "follow_redirects": True}
    if proxy_url:
        kwargs["proxy"] = proxy_url
    return httpx.AsyncClient(**kwargs)


# Special UAs that sites tend to whitelist (search bots / crawlers)
_BOT_USER_AGENTS = [
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Googlebot/2.1; +http://www.google.com/bot.html) Chrome/124.0.0.0 Safari/537.36",
]


async def _fetch_with_ua(url: str, ua: str, timeout: int = 20,
                          proxy: Optional[str] = None) -> Optional[httpx.Response]:
    """Single attempt: one UA, one optional proxy."""
    h = {**HEADERS, "User-Agent": ua}
    kw: dict = {"timeout": timeout, "follow_redirects": True}
    if proxy:
        kw["proxy"] = proxy
    try:
        async with httpx.AsyncClient(**kw) as c:
            r = await c.get(url, headers=h)
            return r
    except Exception:
        return None


async def _get_url(url: str, timeout: int = 20) -> Optional[httpx.Response]:
    """
    GET a URL trying multiple strategies until one succeeds with HTTP 200:
      1. Rotating browser UA + proxy (if available)
      2. Rotating browser UA + direct
      3. Googlebot UA + direct
      4. BingBot UA + direct
    Returns the first 200 response, or the last non-None response, or None.
    """
    proxy_url = next_httpx_proxy()
    last: Optional[httpx.Response] = None

    strategies = []
    # Strategy 1: browser UA + proxy
    if proxy_url:
        strategies.append((_next_ua(), proxy_url))
    # Strategy 2: browser UA + direct
    strategies.append((_next_ua(), None))
    # Strategy 3 & 4: bot UAs + direct
    for bot_ua in _BOT_USER_AGENTS:
        strategies.append((bot_ua, None))

    for ua, proxy in strategies:
        r = await _fetch_with_ua(url, ua, timeout=timeout, proxy=proxy)
        if r is not None:
            last = r
            if r.status_code == 200:
                return r
            if r.status_code in (301, 302, 307, 308):
                # follow already handled by follow_redirects=True, shouldn't land here
                return r
            # 403/429 — try next strategy
            await asyncio.sleep(random.uniform(0.5, 1.5))
        # connection error / timeout — try next strategy immediately

    # Return best available response (even if 403) so caller can inspect
    if last is not None:
        return last
    print(f"  [request error] all strategies failed: {url[-70:]}")
    return None


async def _crawl_category_product_urls() -> list[str]:
    """
    Last-resort: fetch all category pages and scrape product links from HTML.
    Works even when all sitemaps are blocked.
    """
    if not _HAS_BS4:
        return []

    print("  [fallback] Crawling category pages for product URLs...")
    # Fetch homepage to get category links
    r = await _get_url(BASE_URL, timeout=20)
    if r is None or r.status_code != 200:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    cat_links: list[str] = []
    for a in soup.select("a[href]"):
        href = a["href"]
        if not isinstance(href, str):
            continue
        if "route=product/category" in href or "/category/" in href:
            full = href if href.startswith("http") else BASE_URL + href
            if full not in cat_links:
                cat_links.append(full)

    print(f"  [fallback] Found {len(cat_links)} category links")

    product_urls: set[str] = set()

    async def scrape_category(cat_url: str) -> None:
        page = 0
        while True:
            paged = cat_url + (f"&page={page}" if page > 0 else "")
            resp = await _get_url(paged, timeout=20)
            if resp is None or resp.status_code != 200:
                break
            s = BeautifulSoup(resp.text, "html.parser")
            found = 0
            for a in s.select("a[href]"):
                href = a.get("href", "")
                if not isinstance(href, str):
                    continue
                if "route=product/product" in href or "/product/" in href:
                    full = href if href.startswith("http") else BASE_URL + href
                    if full not in product_urls:
                        product_urls.add(full)
                        found += 1
            if found == 0:
                break
            page += 1
            await asyncio.sleep(random.uniform(0.3, 0.8))

    sem = asyncio.Semaphore(4)

    async def bounded(cat_url: str) -> None:
        async with sem:
            await scrape_category(cat_url)

    await asyncio.gather(*[bounded(u) for u in cat_links])
    print(f"  [fallback] Collected {len(product_urls)} product URLs from categories")
    return list(product_urls)


async def fetch_all_product_urls() -> list[str]:
    """
    Collect all product URLs using multiple strategies:
      1. Sitemap index
      2. Direct-probe of known sitemap-product-N.xml pattern
      3. Category page crawling (last resort)
    """
    product_sitemaps = []

    # ── Strategy 1: sitemap index ──────────────────────────────────────────
    r = await _get_url(SITEMAP_INDEX, timeout=20)
    if r is not None and r.status_code == 200:
        try:
            root = ET.fromstring(r.text)
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            for loc in root.findall(".//sm:loc", ns):
                if loc.text and "sitemap-product" in loc.text:
                    product_sitemaps.append(loc.text.strip())
        except ET.ParseError:
            product_sitemaps = re.findall(
                r'https://janoubco\.com/sitemap-product-\d+\.xml', r.text)
    else:
        status = r.status_code if r is not None else "no response"
        print(f"  [sitemap index] status={status} — trying individual sitemaps...")

    # ── Strategy 2: probe known pattern ───────────────────────────────────
    if not product_sitemaps:
        async def probe_sitemap(url: str) -> Optional[str]:
            resp = await _get_url(url, timeout=20)
            if resp is not None and resp.status_code == 200:
                return url
            return None

        probe_results = await asyncio.gather(
            *[probe_sitemap(u) for u in _PRODUCT_SITEMAP_PATTERN])
        product_sitemaps = [u for u in probe_results if u]

    print(f"  Found {len(product_sitemaps)} product sitemap files")

    # Fetch each sitemap
    if product_sitemaps:
        async def fetch_sitemap(url: str) -> list[str]:
            resp = await _get_url(url, timeout=30)
            if resp is None or resp.status_code != 200:
                return []
            try:
                root = ET.fromstring(resp.text)
                ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
                return [
                    (loc.text or "").strip()
                    for loc in root.findall(".//sm:loc", ns)
                    if (loc.text or "").strip() and "janoubco.com" in loc.text
                ]
            except ET.ParseError:
                return []

        results = await asyncio.gather(*[fetch_sitemap(u) for u in product_sitemaps])
        all_urls = [u for batch in results for u in batch]
        if all_urls:
            print(f"  Total product URLs from sitemaps: {len(all_urls)}")
            return all_urls

    # ── Strategy 3: crawl categories ──────────────────────────────────────
    print("  Sitemaps unavailable — falling back to category crawl...")
    return await _crawl_category_product_urls()


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
                candidate = el.get_text(strip=True)
                if candidate:
                    # Reject if the element captured a full sentence / product title
                    # (real SKUs are short codes without long runs of spaces)
                    if len(candidate) <= 100 and candidate.count(' ') <= 4:
                        sku = candidate
                        break
                    # Try to pull a compact code from the captured text
                    m = re.search(r'[A-Za-z][A-Za-z0-9/_\-.]{2,79}', candidate)
                    if m:
                        sku = m.group(0).strip()
                        break
        if not sku:
            m = re.search(r'رقم المنتج[:\s]*([A-Za-z0-9\-_]+)', html)
            if m:
                sku = m.group(1).strip()
        # Final safety: never store a SKU longer than the column allows
        if sku and len(sku) > 191:
            sku = sku[:191]

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

async def fetch_product(url: str) -> Optional[dict]:
    """Fetch a single product page — proxy first, direct fallback."""
    async with _SEM:
        await asyncio.sleep(random.uniform(0.2, 0.8))
        r = await _get_url(url, timeout=20)
        if r is None:
            return None
        if r.status_code == 404:
            return None
        if r.status_code != 200:
            return None
        return _parse_product_html(r.text, url)


# ─── STEP 4: save batch to SQLite ────────────────────────────────────────────

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

        with session.no_autoflush:
            for raw in products:
                name = (raw.get("name") or "").strip()
                if not name:
                    skipped += 1
                    continue

                external_id = raw.get("external_id", "")
                sku         = (raw.get("sku") or external_id or "")[:191]
                price       = raw.get("price")
                source_url  = raw.get("source_url", "")
                brand_name  = (raw.get("brand") or "Janoubco").strip()
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

async def main():
    global _SEM
    _SEM = asyncio.Semaphore(CONCURRENCY)
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

    # ── STEP 1: collect all product URLs from sitemaps ───────────────────
    print("\n[STEP 1] Fetching product URLs from sitemaps...")
    all_urls = await fetch_all_product_urls()

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

    # ── STEP 2: fetch + parse product pages concurrently ─────────────────
    print(f"\n[STEP 2] Fetching {n} product pages "
          f"(concurrency={CONCURRENCY})...\n")

    total_ins = total_upd = total_skip = 0
    batch: list[dict] = []
    done = 0

    async def process(url: str):
        nonlocal done
        result = await fetch_product(url)
        done += 1
        return result

    tasks = [process(u) for u in filtered]

    for coro in asyncio.as_completed(tasks):
        result = await coro
        if result:
            batch.append(result)

        if len(batch) >= _BATCH_SAVE or (done == n and batch):
            try:
                ins, upd, sk = save_to_sqlite(batch)
                total_ins  += ins
                total_upd  += upd
                total_skip += sk
                print(f"  [{done}/{n}] Saved batch: +{ins} new, ~{upd} updated, "
                      f"{sk} skipped (total new: {total_ins})")
            except Exception as db_err:
                print(f"  [save error] {db_err}")
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
