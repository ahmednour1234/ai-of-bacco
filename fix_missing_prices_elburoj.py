"""
fix_missing_prices_elburoj.py
------------------------------
Re-fetches prices for all El Buroj products that have NULL or 0 price.

Strategy (per product):
  1. Salla merchant subdomain API:  GET elburoj.salla.sa/api/products/{id}
  2. Individual product page:       GET elburoj.com/ar/.../{slug}   (HTML → JSON-LD)

Usage:
    python fix_missing_prices_elburoj.py
    python fix_missing_prices_elburoj.py --limit 200   # only first N products
    python fix_missing_prices_elburoj.py --all          # also refresh products that already have a price
"""
import asyncio
import json
import os
import re
import random
import sqlite3
import sys
from typing import Optional

import httpx
try:
    from bs4 import BeautifulSoup
    _BS4 = True
except ImportError:
    _BS4 = False

_DB_FILE   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scraper_data.db")
SOURCE_NAME = "El Buroj"
SALLA_ALT  = "https://elburoj.salla.sa"
BASE_URL   = "https://elburoj.com"
CONCURRENCY = 6
_SEM        = asyncio.Semaphore(CONCURRENCY)

_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
]
_BOT_UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"

def _next_ua() -> str:
    return random.choice(_UA_POOL)

def _headers(json_accept: bool = False) -> dict:
    h = {
        "User-Agent": _next_ua(),
        "Accept-Language": "ar,en;q=0.5",
    }
    if json_accept:
        h["Accept"] = "application/json, text/plain, */*"
    else:
        h["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    return h


# ─── Price parsing ────────────────────────────────────────────────────────────

def _parse_price(v) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v) if v > 0 else None
    if isinstance(v, dict):
        for key in ("amount", "price", "value"):
            sub = v.get(key)
            if sub is not None:
                return _parse_price(sub)
        return None
    if isinstance(v, str):
        m = re.search(r"[\d,]+(?:\.\d+)?", v.replace(",", ""))
        if m:
            try:
                f = float(m.group().replace(",", ""))
                return f if f > 0 else None
            except ValueError:
                pass
    return None


# ─── Fetch helpers ────────────────────────────────────────────────────────────

async def _get(url: str, json_accept: bool = False, timeout: int = 20) -> Optional[httpx.Response]:
    attempts = [
        _headers(json_accept),
        {**_headers(json_accept), "User-Agent": _BOT_UA},
    ]
    for h in attempts:
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as c:
                r = await c.get(url, headers=h)
                if r.status_code == 200:
                    return r
                if r.status_code not in (403, 429, 503):
                    return r
        except Exception:
            pass
        await asyncio.sleep(random.uniform(0.3, 0.8))
    return None


async def _fetch_price_from_api(product_id: str) -> Optional[float]:
    """Try Salla API for a single product by ID."""
    urls = [
        f"{SALLA_ALT}/api/products/{product_id}",
        f"{BASE_URL}/api/products/{product_id}",
    ]
    for url in urls:
        r = await _get(url, json_accept=True)
        if r is None or r.status_code != 200:
            continue
        try:
            body = r.json()
            # Salla API wraps in {"data": {...}}
            data = body.get("data", body) if isinstance(body, dict) else body
            price = _parse_price(data.get("price"))
            if price:
                return price
        except Exception:
            pass
    return None


async def _fetch_price_from_page(source_url: str) -> Optional[float]:
    """Fetch product page and extract price via JSON-LD or HTML selectors."""
    if not source_url:
        return None
    r = await _get(source_url)
    if r is None or r.status_code != 200:
        return None
    html = r.text

    # JSON-LD first
    for m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL | re.IGNORECASE,
    ):
        try:
            data = json.loads(m.group(1))
            if not isinstance(data, dict):
                continue
            items = data.get("@graph", [data])
            for item in items:
                if item.get("@type") == "Product":
                    offers = item.get("offers", {})
                    p = offers.get("price") if isinstance(offers, dict) else None
                    price = _parse_price(p)
                    if price:
                        return price
        except Exception:
            pass

    # Meta tags
    for m in re.finditer(r'<meta[^>]+(?:property|name)=["\'](?:product:price:amount|price)["\'][^>]+content=["\']([^"\']+)["\']', html):
        price = _parse_price(m.group(1))
        if price:
            return price

    # BeautifulSoup CSS selectors
    if _BS4:
        soup = BeautifulSoup(html, "html.parser")
        for sel in ["[itemprop='price']", ".price-amount", ".product-price", ".price"]:
            el = soup.select_one(sel)
            if el:
                txt = el.get("content") or el.get_text(strip=True)
                price = _parse_price(txt)
                if price:
                    return price

    # SAR pattern in HTML
    m2 = re.search(r'SAR[\s\xa0]*([\d,]+(?:\.\d+)?)', html)
    if m2:
        price = _parse_price(m2.group(1))
        if price:
            return price

    return None


async def fetch_price(product_id: str, source_url: str) -> Optional[float]:
    async with _SEM:
        await asyncio.sleep(random.uniform(0.2, 0.7))
        # Try API first (faster, more reliable)
        price = await _fetch_price_from_api(product_id)
        if price:
            return price
        # Fallback to product page
        price = await _fetch_price_from_page(source_url)
        return price


# ─── DB helpers ───────────────────────────────────────────────────────────────

def load_products_missing_price(fetch_all: bool = False) -> list[dict]:
    conn = sqlite3.connect(_DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        if fetch_all:
            # Re-fetch ALL El Buroj products
            rows = conn.execute("""
                SELECT p.id, p.external_id, p.price, p.source_url
                FROM scraper_products p
                JOIN scraper_sources s ON p.source_id = s.id
                WHERE s.name = ?
                ORDER BY p.id
            """, (SOURCE_NAME,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT p.id, p.external_id, p.price, p.source_url
                FROM scraper_products p
                JOIN scraper_sources s ON p.source_id = s.id
                WHERE s.name = ?
                  AND (p.price IS NULL OR p.price = 0)
                ORDER BY p.id
            """, (SOURCE_NAME,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def save_prices(updates: list[tuple[float, int]]) -> int:
    """Batch update prices. updates = list of (price, product_db_id)."""
    if not updates:
        return 0
    conn = sqlite3.connect(_DB_FILE)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        conn.executemany(
            "UPDATE scraper_products SET price=?, updated_at=datetime('now') WHERE id=?",
            updates,
        )
        conn.commit()
        return len(updates)
    finally:
        conn.close()


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    fetch_all = "--all" in sys.argv
    limit = None
    for arg in sys.argv[1:]:
        if arg.startswith("--limit="):
            limit = int(arg.split("=")[1])
        elif arg == "--limit" and sys.argv.index(arg) + 1 < len(sys.argv):
            limit = int(sys.argv[sys.argv.index(arg) + 1])

    print("=" * 60)
    print("  EL BUROJ — PRICE RE-FETCH")
    print("=" * 60)

    products = load_products_missing_price(fetch_all=fetch_all)
    if limit:
        products = products[:limit]

    mode = "ALL products" if fetch_all else "products with missing price"
    print(f"\n  {len(products)} {mode} to re-fetch")
    if not products:
        print("  Nothing to do!")
        return

    done = 0
    updated = 0
    batch: list[tuple[float, int]] = []

    async def process(prod: dict) -> tuple[Optional[float], int]:
        price = await fetch_price(prod["external_id"] or "", prod["source_url"] or "")
        return price, prod["id"]

    tasks = [asyncio.create_task(process(p)) for p in products]

    for coro in asyncio.as_completed(tasks):
        try:
            price, db_id = await coro
        except Exception:
            price, db_id = None, 0
        done += 1
        if price:
            batch.append((price, db_id))
            updated += 1

        if len(batch) >= 50 or (done == len(products) and batch):
            saved = save_prices(batch)
            batch = []
            print(f"  [{done}/{len(products)}] {updated} prices found (saved {saved})")
        elif done % 50 == 0 or done == len(products):
            print(f"  [{done}/{len(products)}] {updated} prices found")

    print(f"\n{'='*60}")
    print(f"  DONE — updated {updated} / {len(products)} products with a price")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
