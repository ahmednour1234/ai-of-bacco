from typing import Optional
"""
scrape_all_elburoj.py
----------------------
Scrapes ALL categories from elburoj.com (Salla store) and saves to scraper_data.db.
No Playwright required — uses httpx + BeautifulSoup.

Strategies (tried in order per category page):
  1. Salla storefront JSON API  (/api/products?category_id=X&page=N)
  2. Embedded JSON in <script> tags (window.__products / JSON-LD)
  3. Product-card HTML links → individual product page fetch

Usage:
    python scrape_all_elburoj.py
"""
import asyncio
import json
import re
import sys
import os
import random
from collections import Counter
from datetime import datetime, timezone
_NOW = lambda: datetime.now(timezone.utc)

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

BASE_URL      = "https://elburoj.com"
SALLA_ALT_URL = "https://elburoj.salla.sa"   # Salla merchant subdomain (always works)
SOURCE_NAME   = "El Buroj"

CONCURRENCY = 6
_SEM: Optional[asyncio.Semaphore] = None
_BATCH_SAVE = 30

KNOWN_CATEGORIES = [
    {"id": "539403396", "name": "إنارة",   "url": "https://elburoj.salla.sa/categories/539403396/products"},
    {"id": "413920175", "name": "كابلات",  "url": "https://elburoj.salla.sa/categories/413920175/products"},
]

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]
_ua_idx = 0

def _next_ua() -> str:
    global _ua_idx
    ua = _USER_AGENTS[_ua_idx % len(_USER_AGENTS)]
    _ua_idx += 1
    return ua

def _html_headers() -> dict:
    return {
        "User-Agent": _next_ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    }

def _json_headers() -> dict:
    return {
        "User-Agent": _next_ua(),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": BASE_URL + "/ar",
    }


_BOT_UAS = [
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Googlebot/2.1; +http://www.google.com/bot.html) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
]


# ─── HTTP helper ──────────────────────────────────────────────────────────────

async def _fetch_once(url: str, headers: dict, timeout: int = 25) -> Optional[httpx.Response]:
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as c:
            return await c.get(url, headers=headers)
    except Exception:
        return None


async def _get(url: str, headers: Optional[dict] = None,
               timeout: int = 25) -> Optional[httpx.Response]:
    """GET with multi-UA fallback: browser UA → Googlebot → BingBot.
       Also retries on the Salla merchant subdomain if main domain 403s."""
    attempts = [
        {**( headers or _html_headers()), "User-Agent": _next_ua()},
        {**_html_headers(), "User-Agent": _BOT_UAS[0]},
        {**_html_headers(), "User-Agent": _BOT_UAS[1]},
        {**_html_headers(), "User-Agent": _BOT_UAS[2]},
    ]
    last: Optional[httpx.Response] = None
    for h in attempts:
        r = await _fetch_once(url, h, timeout)
        if r is not None:
            last = r
            if r.status_code == 200:
                return r
            if r.status_code not in (403, 429, 503):
                return r   # e.g. 404 — no point retrying
            await asyncio.sleep(random.uniform(0.5, 1.5))

    # If still blocked, try rewriting the URL to the Salla merchant subdomain
    if BASE_URL in url:
        alt_url = url.replace(BASE_URL, SALLA_ALT_URL)
        # also strip the /ar prefix since salla.sa doesn't use it
        alt_url = re.sub(r'/ar/', '/', alt_url)
        if alt_url != url:
            for h in attempts[:2]:
                r = await _fetch_once(alt_url, h, timeout)
                if r is not None and r.status_code == 200:
                    return r

    if last is not None:
        print(f"  [http {last.status_code}] {url[-70:]}")
    else:
        print(f"  [http error] {url[-70:]}")
    return last


# ─── Salla API: try to hit the store's product endpoint directly ──────────────

async def _salla_api_products(category_id: str, page: int = 1) -> tuple[list[dict], int]:
    """
    Try Salla storefront API endpoints. Returns (products, total_pages).
    Tries both main domain and merchant subdomain.
    """
    candidates = [
        # Salla merchant subdomain REST API (most reliable)
        f"{SALLA_ALT_URL}/api/products?category_id={category_id}&page={page}&per_page=30",
        f"{SALLA_ALT_URL}/categories/{category_id}/products?page={page}&per_page=30",
        # Main domain
        f"{BASE_URL}/api/product/list?category_id={category_id}&page={page}&per_page=30",
        f"{BASE_URL}/api/products?category_id={category_id}&page={page}&per_page=30",
        f"{BASE_URL}/ar/api/products?category_id={category_id}&page={page}&per_page=30",
    ]
    for url in candidates:
        r = await _get(url, headers=_json_headers())
        if r is None or r.status_code != 200:
            continue
        try:
            body = r.json()
        except Exception:
            continue
        products = []
        total_pages = 1
        if isinstance(body, dict):
            data = body.get("data", body.get("products", []))
            if isinstance(data, list):
                products = data
            pag = body.get("pagination", body.get("meta", {}))
            if isinstance(pag, dict):
                total_pages = int(pag.get("totalPages", pag.get("last_page", 1)))
        elif isinstance(body, list):
            products = body
        if products:
            return products, total_pages
    return [], 1


# ─── HTML parsing ─────────────────────────────────────────────────────────────

def _extract_from_scripts(html: str) -> list[dict]:
    """Pull product lists embedded in <script> tags."""
    products = []
    patterns = [
        r'window\.__products\s*=\s*(\[.+?\])\s*;',
        r'"products"\s*:\s*(\[.+?\])',
        r'salla\.product\.list\s*=\s*(\[.+?\])',
        r'productsData\s*=\s*(\[.+?\])',
    ]
    for pat in patterns:
        for m in re.finditer(pat, html, re.DOTALL):
            try:
                data = json.loads(m.group(1))
                if isinstance(data, list) and data:
                    products.extend(data)
                    break
            except Exception:
                pass
    return products


def _extract_jsonld(html: str) -> list[dict]:
    """Pull products from JSON-LD blocks."""
    products = []
    for m in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                         html, re.DOTALL | re.IGNORECASE):
        try:
            data = json.loads(m.group(1))
            if isinstance(data, dict):
                if data.get("@type") == "Product":
                    products.append(data)
                elif data.get("@type") == "ItemList":
                    for item in data.get("itemListElement", []):
                        if isinstance(item, dict) and item.get("item"):
                            products.append(item["item"])
        except Exception:
            pass
    return products


def _extract_product_urls(html: str, base: str) -> list[str]:
    """Pull product page URLs from HTML (anchors and data-product-url attrs)."""
    urls: list[str] = []
    seen: set[str] = set()

    def _add(href: str) -> None:
        if not href:
            return
        full = href if href.startswith("http") else base + href
        if full not in seen and re.search(r'/p\d+', full):
            seen.add(full)
            urls.append(full)

    if _HAS_BS4:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.select("a[href]"):
            _add(a.get("href", ""))
        for el in soup.select("[data-product-url]"):
            _add(el.get("data-product-url", ""))
        for el in soup.select("[data-url]"):
            _add(el.get("data-url", ""))
    else:
        for m in re.finditer(r'href=["\']([^"\']+/p\d+[^"\']*)["\']', html):
            _add(m.group(1))

    return urls


def _parse_total_pages(html: str) -> int:
    """Find the total number of pages from HTML."""
    total = 1
    if _HAS_BS4:
        soup = BeautifulSoup(html, "html.parser")
        for el in soup.select("[data-last-page],[data-total-pages],[data-pages]"):
            for attr in ("data-last-page", "data-total-pages", "data-pages"):
                v = el.get(attr, "")
                if v and str(v).isdigit():
                    total = max(total, int(v))
        for a in soup.select("a[href*='page=']"):
            m = re.search(r'page=(\d+)', a.get("href", ""))
            if m:
                total = max(total, int(m.group(1)))
    else:
        for m in re.finditer(r'page=(\d+)', html):
            total = max(total, int(m.group(1)))
    # also try JSON in html
    for pattern in [r'"totalPages"\s*:\s*(\d+)', r'"last_page"\s*:\s*(\d+)',
                    r'"total_pages"\s*:\s*(\d+)']:
        m = re.search(pattern, html)
        if m:
            total = max(total, int(m.group(1)))
    return total


def _parse_product_page(html: str, url: str) -> Optional[dict]:
    """Extract product data from a single product page."""
    # Try JSON-LD first
    prods = _extract_jsonld(html)
    if prods:
        p = prods[0]
        name = p.get("name", "")
        if name:
            return {
                "id": re.search(r'/p(\d+)', url).group(1) if re.search(r'/p(\d+)', url) else "",
                "name": name,
                "sku": p.get("sku", ""),
                "url": url,
                "price": {"amount": p.get("offers", {}).get("price") if isinstance(p.get("offers"), dict) else None},
                "description": p.get("description", ""),
                "brand": p.get("brand", {}).get("name", "") if isinstance(p.get("brand"), dict) else "",
            }

    if not _HAS_BS4:
        return None

    soup = BeautifulSoup(html, "html.parser")

    # Name
    name = None
    for sel in ["h1.product-title", "h1[itemprop='name']", ".product-name h1", "h1"]:
        el = soup.select_one(sel)
        if el:
            name = el.get_text(strip=True)
            break
    if not name:
        return None

    # SKU
    sku = ""
    for sel in ["[itemprop='sku']", ".sku", ".product-sku"]:
        el = soup.select_one(sel)
        if el:
            candidate = el.get_text(strip=True)
            if candidate and len(candidate) <= 100:
                sku = candidate
                break

    # Price
    price_val = None
    for sel in ["[itemprop='price']", ".price", ".product-price"]:
        el = soup.select_one(sel)
        if el:
            txt = el.get("content") or el.get_text(strip=True)
            m = re.search(r'[\d,]+(?:\.\d+)?', txt.replace(",", ""))
            if m:
                try:
                    price_val = float(m.group().replace(",", ""))
                    break
                except ValueError:
                    pass

    # Brand
    brand = ""
    for sel in ["[itemprop='brand']", ".product-brand", ".brand"]:
        el = soup.select_one(sel)
        if el:
            brand = el.get_text(strip=True)
            break

    pid_m = re.search(r'/p(\d+)', url)
    pid = pid_m.group(1) if pid_m else ""

    return {
        "id": pid,
        "name": name,
        "sku": sku,
        "url": url,
        "price": {"amount": price_val},
        "brand": brand,
    }


# ─── STEP 1: Discover categories ─────────────────────────────────────────────

async def discover_categories() -> list[dict]:
    # Try Salla merchant subdomain first (less likely to be blocked)
    for base in [SALLA_ALT_URL, f"{BASE_URL}/ar"]:
        print(f"  Loading: {base}")
        r = await _get(base, timeout=25)
        if r is None or r.status_code != 200:
            print(f"  [warn] {base} → status={r.status_code if r else 'None'}")
            continue

        seen: set[str] = set()
        cats: list[dict] = []

        if _HAS_BS4:
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                if not isinstance(href, str):
                    continue
                m = re.search(r'/c(\d{6,})', href)
                if not m:
                    # also match salla.sa pattern /categories/ID
                    m = re.search(r'/categories/(\d{6,})', href)
                if not m:
                    continue
                cid = m.group(1)
                if cid in seen:
                    continue
                seen.add(cid)
                name = a.get_text(strip=True).split("\n")[0].strip() or f"cat_{cid}"
                full = href if href.startswith("http") else base.rstrip("/ar").rstrip("/") + href
                cats.append({"id": cid, "name": name, "url": full})
        else:
            for m in re.finditer(r'href=["\']([^"\']+(?:/c(\d{6,})|/categories/(\d{6,})))["\']', r.text):
                cid = m.group(2) or m.group(3)
                if not cid or cid in seen:
                    continue
                seen.add(cid)
                full = m.group(1) if m.group(1).startswith("http") else base + m.group(1)
                cats.append({"id": cid, "name": f"cat_{cid}", "url": full})

        if cats:
            return cats

    return []


# ─── STEP 2: Scrape one category ─────────────────────────────────────────────

async def scrape_category(category: dict) -> list[dict]:
    cat_name = category.get("name", "?")
    cat_url  = category.get("url", "")
    cat_id   = category.get("id", "")
    all_products: list[dict] = []
    seen_ids: set[str] = set()

    def _add_products(prods: list[dict]) -> int:
        added = 0
        for p in prods:
            pid = str(p.get("id", "")) or str(p.get("url", ""))
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                p["_category_name"] = cat_name
                p["_category_url"]  = cat_url
                p["_category_id"]   = cat_id
                all_products.append(p)
                added += 1
        return added

    page = 1
    total_pages = 1

    while page <= total_pages:
        paged_url = cat_url + (f"&page={page}" if page > 1 else "")
        if "?" not in cat_url and page > 1:
            paged_url = cat_url + f"?page={page}"

        print(f"  [{cat_name}] Page {page}/{total_pages}: {paged_url[-80:]}")

        # Strategy 1: Salla JSON API
        api_prods, api_pages = await _salla_api_products(cat_id, page)
        if api_prods:
            total_pages = max(total_pages, api_pages)
            n = _add_products(api_prods)
            print(f"    → {n} products via API (total: {len(all_products)})")
            page += 1
            await asyncio.sleep(random.uniform(0.5, 1.2))
            continue

        # Strategy 2: fetch HTML → embedded JSON + product URLs
        r = await _get(paged_url, timeout=25)
        if r is None or r.status_code != 200:
            print(f"    → HTTP {r.status_code if r else 'error'}, stopping.")
            break

        html = r.text
        total_pages = max(total_pages, _parse_total_pages(html))

        # Try embedded script/JSON-LD
        embedded = _extract_from_scripts(html) + _extract_jsonld(html)
        if embedded:
            n = _add_products(embedded)
            print(f"    → {n} products via embedded JSON (total: {len(all_products)})")
            page += 1
            await asyncio.sleep(random.uniform(0.5, 1.2))
            continue

        # Strategy 3: extract product URLs and fetch each
        prod_urls = _extract_product_urls(html, BASE_URL)
        if not prod_urls:
            print(f"    → No products found, stopping.")
            break

        print(f"    → Found {len(prod_urls)} product links, fetching each...")
        async def fetch_one(url: str) -> Optional[dict]:
            async with _SEM:
                await asyncio.sleep(random.uniform(0.2, 0.6))
                resp = await _get(url)
                if resp and resp.status_code == 200:
                    return _parse_product_page(resp.text, url)
                return None

        results = await asyncio.gather(*[fetch_one(u) for u in prod_urls])
        fetched = [p for p in results if p]
        n = _add_products(fetched)
        print(f"    → {n} products via page fetch (total: {len(all_products)})")

        if not fetched:
            break
        page += 1
        await asyncio.sleep(random.uniform(0.5, 1.2))

    print(f"  [{cat_name}] Done — {len(all_products)} products")
    return all_products


# ─── STEP 3: Save to SQLite ───────────────────────────────────────────────────

def _parse_price(price_data) -> Optional[float]:
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
    try:
        v = float(price_data)
        return v if v > 0 else None
    except (ValueError, TypeError):
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
    from sqlalchemy import create_engine, select, text
    from sqlalchemy.orm import Session

    db_url = os.environ.get("SCRAPER_DATABASE_URL_SYNC", f"sqlite:///{_DB_FILE}")
    if "mysql" in db_url and "charset=" not in db_url:
        db_url += ("&" if "?" in db_url else "?") + "charset=utf8mb4"
    engine = create_engine(db_url, echo=False)
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

        cat_cache: dict[str, ScraperCategory] = {}
        brand_cache: dict[str, ScraperBrand] = {}

        with session.no_autoflush:
            for raw in all_products:
                name = _extract_name(raw)
                if not name:
                    skipped += 1
                    continue

                external_id = str(raw.get("id", ""))
                sku         = (raw.get("sku") or raw.get("product_number") or "")[:191]
                price       = _parse_price(raw.get("price"))
                source_url  = raw.get("url") or ""
                if source_url and not source_url.startswith("http"):
                    source_url = BASE_URL + source_url

                # Category
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

                # Brand
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

                # Upsert
                existing = None
                if external_id:
                    existing = session.execute(
                        select(ScraperProduct).where(
                            ScraperProduct.source_id == source.id,
                            ScraperProduct.external_id == external_id,
                        )
                    ).scalar_one_or_none()

                raw_json = json.dumps(raw, ensure_ascii=False, default=str)

                if existing:
                    existing.name                = name
                    existing.sku                 = sku
                    existing.price               = price
                    existing.source_url          = source_url
                    existing.scraper_category_id = category.id
                    existing.scraper_brand_id    = brand.id if brand else None
                    existing.raw_data            = raw_json
                    existing.last_scraped_at     = _NOW()
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
                        raw_data=raw_json,
                        last_scraped_at=_NOW(),
                        is_synced=False,
                    ))
                    inserted += 1

        session.commit()

    print(f"  DB → inserted={inserted}, updated={updated}, skipped={skipped}")
    return inserted, updated, skipped


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    global _SEM
    _SEM = asyncio.Semaphore(CONCURRENCY)

    if not _HAS_BS4:
        print("[setup] beautifulsoup4 not installed — pip install beautifulsoup4")

    print("=" * 60)
    print("  EL BUROJ — FULL SITE SCRAPER (httpx, no Playwright)")
    print("=" * 60)

    # STEP 1: Discover categories
    print("\n[STEP 1] Discovering categories from homepage...")
    categories = await discover_categories()

    if not categories:
        print("  Homepage discovery found nothing — using fallback list.")
        categories = KNOWN_CATEGORIES
    else:
        known_ids = {c["id"] for c in categories}
        for kc in KNOWN_CATEGORIES:
            if kc["id"] not in known_ids:
                categories.append(kc)

    print(f"\n  {len(categories)} categories to scrape:")
    for c in categories:
        print(f"    [{c['id']}] {c['name']}")

    # STEP 2: Scrape each category
    print(f"\n[STEP 2] Scraping {len(categories)} categories...\n")
    all_products: list[dict] = []
    seen_ids: set[str] = set()
    total_ins = total_upd = total_skip = 0

    for i, cat in enumerate(categories, 1):
        print(f"── [{i}/{len(categories)}] {cat['name']} ──────────────────────")
        try:
            products = await scrape_category(cat)
        except Exception as e:
            print(f"  [ERROR] {cat['name']}: {e}")
            continue

        new_products = [
            p for p in products
            if (str(p.get("id", "")) or str(p.get("url", ""))) not in seen_ids
        ]
        for p in new_products:
            seen_ids.add(str(p.get("id", "")) or str(p.get("url", "")))

        if new_products:
            all_products.extend(new_products)
            print(f"  Saving {len(new_products)} products to DB...")
            ins, upd, sk = save_to_sqlite(new_products)
            total_ins += ins; total_upd += upd; total_skip += sk
        else:
            print(f"  No new products.")

    print(f"\nTotal unique products scraped: {len(all_products)}")
    print(f"DB totals: inserted={total_ins}, updated={total_upd}, skipped={total_skip}")
    for cat_name, count in Counter(
            p.get("_category_name", "?") for p in all_products).most_common():
        print(f"  {cat_name}: {count}")

    output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "scraped_all_products.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_products, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nRaw JSON saved → {output_file}")

    print("\n" + "=" * 60)
    print(f"  DONE — {len(all_products)} products")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

