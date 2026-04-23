"""
fix_missing_prices.py
----------------------
Re-fetches prices for all products (except El Buroj / Microless) that have NULL/0 price.
Fetches the product page URL and extracts price via JSON-LD, meta tags, and CSS selectors.

Usage:
    python fix_missing_prices.py                 # fix all sources
    python fix_missing_prices.py Janoubco        # fix one source
    python fix_missing_prices.py --limit=100     # cap number
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

_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scraper_data.db")
CONCURRENCY = 10
_SEM: asyncio.Semaphore

_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
]

def _parse_price(v) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v) if v > 0 else None
    if isinstance(v, dict):
        for key in ("amount", "price", "value", "current"):
            p = _parse_price(v.get(key))
            if p:
                return p
        return None
    if isinstance(v, str):
        m = re.search(r"[\d]+(?:[\d,]*\.\d+)?", v.replace(",", ""))
        if m:
            try:
                f = float(m.group().replace(",", ""))
                return f if f > 0 else None
            except ValueError:
                pass
    return None

async def _get(url: str, timeout: int = 20) -> Optional[httpx.Response]:
    for ua in (random.choice(_UAS[:3]), _UAS[3]):
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as c:
                r = await c.get(url, headers={
                    "User-Agent": ua,
                    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                    "Accept-Language": "ar,en;q=0.5",
                })
                if r.status_code == 200:
                    return r
                if r.status_code not in (403, 429, 503):
                    return r
        except Exception:
            pass
        await asyncio.sleep(random.uniform(0.2, 0.6))
    return None

def _extract_price(html: str) -> Optional[float]:
    # 1. JSON-LD
    for m in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE):
        try:
            data = json.loads(m.group(1))
            items = data.get("@graph", [data]) if isinstance(data, dict) else []
            for item in items:
                if not isinstance(item, dict) or item.get("@type") != "Product":
                    continue
                offers = item.get("offers", {})
                if isinstance(offers, list): offers = offers[0] if offers else {}
                p = _parse_price(offers.get("price") if isinstance(offers, dict) else None)
                if p: return p
        except Exception:
            pass
    # 2. Meta price tags
    for m in re.finditer(r'<meta[^>]+(?:property|name|itemprop)=["\'](?:product:price:amount|og:price:amount|price)["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE):
        p = _parse_price(m.group(1))
        if p: return p
    # 3. itemprop="price" in content attr
    for m in re.finditer(r'itemprop=["\']price["\'][^>]+content=["\']([^"\']+)["\']', html):
        p = _parse_price(m.group(1))
        if p: return p
    # 4. data-price attributes
    for m in re.finditer(r'data-(?:price|current-price|sale-price|final-price|product-price)=["\']([^"\']+)["\']', html):
        p = _parse_price(m.group(1))
        if p: return p
    # 5. BeautifulSoup
    if _BS4:
        soup = BeautifulSoup(html, "html.parser")
        for sel in ["[itemprop='price']", ".price-new", ".price-normal", ".price-amount",
                    ".current-price", ".product-price", ".sale-price", ".price"]:
            el = soup.select_one(sel)
            if el:
                txt = el.get("content") or el.get("data-price") or el.get_text(strip=True)
                p = _parse_price(txt)
                if p: return p
    # 6. SAR pattern
    for pat in [r"SAR[\s\xa0]*([\d,]+(?:\.\d+)?)", r"([\d,]+(?:\.\d+)?)\s*SAR"]:
        m = re.search(pat, html)
        if m:
            p = _parse_price(m.group(1))
            if p: return p
    # 7. Inline JS
    for m in re.finditer(r'(?:"price"|currentPrice|salePrice|finalPrice)\s*[=:]\s*([\d]+(?:\.\d+)?)', html):
        p = _parse_price(m.group(1))
        if p: return p
    return None

async def fetch_price(db_id: int, url: str) -> tuple[int, Optional[float]]:
    if not url:
        return db_id, None
    async with _SEM:
        await asyncio.sleep(random.uniform(0.1, 0.5))
        r = await _get(url)
        if not r or r.status_code != 200:
            return db_id, None
        return db_id, _extract_price(r.text)

def load_products(source_filter: Optional[str]) -> list[dict]:
    conn = sqlite3.connect(_DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        if source_filter:
            sql = "SELECT p.id, p.source_url, s.name as source FROM scraper_products p JOIN scraper_sources s ON p.source_id = s.id WHERE s.name LIKE ? AND (p.price IS NULL OR p.price = 0) AND p.source_url IS NOT NULL AND p.source_url != '' ORDER BY p.id"
            rows = conn.execute(sql, (f"%{source_filter}%",)).fetchall()
        else:
            sql = "SELECT p.id, p.source_url, s.name as source FROM scraper_products p JOIN scraper_sources s ON p.source_id = s.id WHERE (p.price IS NULL OR p.price = 0) AND p.source_url IS NOT NULL AND p.source_url != '' AND s.name NOT IN ('El Buroj', 'Microless Saudi') ORDER BY p.id"
            rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def save_prices(updates: list[tuple[float, int]]) -> int:
    if not updates:
        return 0
    conn = sqlite3.connect(_DB_FILE)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        conn.executemany("UPDATE scraper_products SET price=?, updated_at=datetime('now') WHERE id=?", updates)
        conn.commit()
        return len(updates)
    finally:
        conn.close()

async def main() -> None:
    global _SEM
    _SEM = asyncio.Semaphore(CONCURRENCY)
    source_filter = None
    limit = None
    for arg in sys.argv[1:]:
        if arg.startswith("--limit="):
            limit = int(arg.split("=")[1])
        elif not arg.startswith("-"):
            source_filter = arg

    print("=" * 60)
    print("  PRICE RE-FETCH (Janoubco / Zorins / Baytalebaa / etc.)")
    print("=" * 60)

    products = load_products(source_filter)
    if limit:
        products = products[:limit]

    from collections import Counter
    by_source = Counter(p["source"] for p in products)
    print(f"\n  {len(products)} products with missing prices:")
    for src, cnt in by_source.most_common():
        print(f"    {src}: {cnt}")
    if not products:
        print("\n  Nothing to do!"); return

    print(f"\nFetching pages (concurrency={CONCURRENCY})...")
    done = found = 0
    total = len(products)
    batch: list[tuple[float, int]] = []

    tasks = [asyncio.create_task(fetch_price(p["id"], p["source_url"])) for p in products]
    for coro in asyncio.as_completed(tasks):
        db_id, price = await coro
        done += 1
        if price:
            batch.append((price, db_id))
            found += 1
        if len(batch) >= 50 or (done == total and batch):
            saved = save_prices(batch); batch = []
            print(f"  [{done}/{total}] {found} prices found — saved {saved}")
        elif done % 100 == 0 or done == total:
            print(f"  [{done}/{total}] {found} prices found ({round(100*found/done) if done else 0}%)")

    if batch:
        save_prices(batch)

    print(f"\n{'='*60}")
    print(f"  DONE — updated {found}/{total} products with a price")
    print(f"{'='*60}")

if __name__ == "__main__":
    asyncio.run(main())
