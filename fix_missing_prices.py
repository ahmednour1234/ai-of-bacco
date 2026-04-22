"""
fix_missing_prices.py
---------------------
Finds all Janoubco products in the DB with price=NULL,
re-fetches each product page, and updates the price.

Usage:
    python fix_missing_prices.py
"""
import asyncio
import re
import sqlite3
import random
import sys
import os
from datetime import datetime

import httpx
try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False

_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scraper_data.db")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ar,en;q=0.5",
}

CONCURRENCY = 12
_SEM = asyncio.Semaphore(CONCURRENCY)


def _parse_price(text: str):
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


def _extract_price(html: str) -> float | None:
    if not html:
        return None
    if _HAS_BS4:
        soup = BeautifulSoup(html, "html.parser")
        for sel in [
            ".price-new",
            ".price-normal",
            ".product-price .price-new",
            ".product-price .price-normal",
            "[itemprop='price']",
            ".price-group",
            ".product-price",
        ]:
            el = soup.select_one(sel)
            if el:
                content = el.get("content") or el.get_text(strip=True)
                price = _parse_price(content)
                if price:
                    return price
    else:
        # regex fallback
        m = re.search(r'class="price-(?:new|normal)[^"]*"[^>]*>([^<]+)<', html)
        if m:
            return _parse_price(m.group(1))
    return None


async def fetch_price(client: httpx.AsyncClient, product_id: int, url: str) -> tuple[int, float | None]:
    async with _SEM:
        await asyncio.sleep(random.uniform(0.2, 0.8))
        try:
            r = await client.get(url, headers=HEADERS, timeout=20)
            if r.status_code != 200:
                return product_id, None
            price = _extract_price(r.text)
            return product_id, price
        except Exception as e:
            print(f"  [error] {url[-60:]}: {e}")
            return product_id, None


async def main():
    print("=" * 60)
    print("  FIX MISSING PRICES — Janoubco")
    print("=" * 60)

    # Load all no-price products with a source_url
    con = sqlite3.connect(_DB_FILE)
    rows = con.execute("""
        SELECT p.id, p.source_url
        FROM scraper_products p
        JOIN scraper_sources s ON s.id = p.source_id
        WHERE s.name = 'Janoubco'
          AND (p.price IS NULL OR p.price = 0)
          AND p.source_url != ''
        ORDER BY p.id
    """).fetchall()
    con.close()

    total = len(rows)
    if total == 0:
        print("  No products without prices found!")
        return

    print(f"  Found {total} Janoubco products without price")
    print(f"  Re-fetching with concurrency={CONCURRENCY}...\n")

    updated = failed = 0
    now = datetime.now().isoformat(sep=" ", timespec="seconds")

    async with httpx.AsyncClient(follow_redirects=True) as client:
        tasks = [fetch_price(client, pid, url) for pid, url in rows]

        batch_updates = []
        done = 0

        for coro in asyncio.as_completed(tasks):
            pid, price = await coro
            done += 1

            if price is not None:
                batch_updates.append((price, now, pid))
                updated += 1
            else:
                failed += 1

            if done % 10 == 0 or done == total:
                print(f"  [{done}/{total}] found price: {updated}, missing: {failed}", flush=True)

            # Write in batches of 50
            if len(batch_updates) >= 50 or done == total:
                if batch_updates:
                    con = sqlite3.connect(_DB_FILE)
                    con.executemany(
                        "UPDATE scraper_products SET price=?, updated_at=? WHERE id=?",
                        batch_updates,
                    )
                    con.commit()
                    con.close()
                    batch_updates = []

    print(f"\n{'=' * 60}")
    print(f"  DONE — updated={updated}, still missing={failed}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())
