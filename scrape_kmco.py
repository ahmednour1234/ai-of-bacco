from typing import Optional
"""
scrape_kmco.py
--------------
Scrapes ALL products from kmco.sa (WooCommerce / static HTML).
No Playwright needed — standard httpx + BeautifulSoup.

Usage:
    .\.venv\Scripts\python scrape_kmco.py
"""
import asyncio
import json
import re
import sys
import os
from collections import Counter
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
from bs4 import BeautifulSoup

BASE_URL   = "https://kmco.sa"
SHOP_URL   = "https://kmco.sa/shop/"
SOURCE_NAME = "KMCO"
BRAND_NAME  = "KM"          # all products are KMCO's own brand

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ar,en;q=0.9",
}


# ─── helpers ─────────────────────────────────────────────────────────────────

def _parse_price(text: str) ->Optional[ float]:
    """Parse WooCommerce price like '⃁ 42,00' or '42.00'."""
    if not text:
        return None
    clean = re.sub(r"[^\d.,]", "", text).replace(",", ".")
    # handle "130.00–285.00" (variable product range) → take first
    clean = clean.split("–")[0].split("-")[0].strip(".")
    try:
        v = float(clean)
        return v if v > 0 else None
    except ValueError:
        return None


def _get_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


# ─── STEP 1: discover categories ─────────────────────────────────────────────

async def discover_categories(client: httpx.AsyncClient) -> list[dict]:
    """Scrape the shop page footer / nav to find all product-category links."""
    r = await client.get(SHOP_URL, headers=HEADERS, follow_redirects=True)
    soup = _get_soup(r.text)
    cats: dict[str, dict] = {}

    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = re.match(r"https://kmco\.sa/product-category/([\w-]+)/?", href)
        if m:
            slug = m.group(1)
            name = a.get_text(strip=True) or slug
            if slug not in cats:
                cats[slug] = {"slug": slug, "name": name, "url": href.rstrip("/") + "/"}

    return list(cats.values())


# ─── STEP 2: scrape one category (all pages) ─────────────────────────────────

async def scrape_category_page(client: httpx.AsyncClient, url: str) ->Optional[ tuple[list[dict], str]]:
    """Scrape a single listing page. Returns (products, next_page_url)."""
    try:
        r = await client.get(url, headers=HEADERS, follow_redirects=True, timeout=30)
        if r.status_code != 200:
            print(f"    [HTTP {r.status_code}] {url}")
            return [], None
    except Exception as e:
        print(f"    [ERROR] {url}: {e}")
        return [], None

    soup = _get_soup(r.text)
    products = []

    # WooCommerce product grid
    for li in soup.select("li.product"):
        # Name
        name_el = (
            li.select_one("h2.woocommerce-loop-product__title")
            or li.select_one(".wc-block-grid__product-title")
            or li.select_one("h2")
            or li.select_one("h3")
        )
        name = name_el.get_text(strip=True) if name_el else ""
        if not name:
            continue

        # URL + slug (= external_id)
        a_el = li.select_one("a.woocommerce-loop-product__link") or li.select_one("a")
        product_url = a_el["href"] if a_el and a_el.get("href") else ""
        slug_m = re.search(r"/product/([^/?]+)", product_url)
        external_id = slug_m.group(1) if slug_m else product_url

        # Price
        price_el = li.select_one(".price ins .amount") or li.select_one(".price .amount") or li.select_one(".price")
        price_raw = price_el.get_text(strip=True) if price_el else ""
        price = _parse_price(price_raw)

        # Category tag shown on card
        cat_el = li.select_one(".wc-block-grid__product-category") or li.select_one(".product-category")
        cat_tag = cat_el.get_text(strip=True) if cat_el else ""

        # Image
        img_el = li.select_one("img")
        img_url = img_el.get("src", "") if img_el else ""

        products.append({
            "external_id": external_id,
            "name":        name,
            "price":       price,
            "source_url":  product_url,
            "image_url":   img_url,
            "cat_tag":     cat_tag,
        })

    # Next page
    next_el = soup.select_one("a.next.page-numbers") or soup.select_one(".pagination a[rel='next']")
    next_url = next_el["href"] if next_el and next_el.get("href") else None

    return products, next_url


async def scrape_category(client: httpx.AsyncClient, category: dict) -> list[dict]:
    cat_name = category["name"]
    cat_url  = category["url"]
    cat_slug = category["slug"]
    all_products = []
    page_url = cat_url
    page_num = 1

    while page_url:
        print(f"  Page {page_num}: {page_url}")
        products, next_url = await scrape_category_page(client, page_url)
        for p in products:
            p["_category_name"] = cat_name
            p["_category_url"]  = cat_url
            p["_category_slug"] = cat_slug
        all_products.extend(products)
        print(f"    → {len(products)} products")
        page_url = next_url
        page_num += 1

    print(f"  [{cat_name}] Done — {len(all_products)} products")
    return all_products


# ─── STEP 3: enrich product pages (SKU) ─────────────────────────────────────

async def enrich_product(client: httpx.AsyncClient, product: dict) -> dict:
    """Visit product page to grab SKU."""
    url = product.get("source_url", "")
    if not url:
        return product
    try:
        r = await client.get(url, headers=HEADERS, follow_redirects=True, timeout=20)
        soup = _get_soup(r.text)
        sku_el = soup.select_one(".sku") or soup.select_one("[itemprop='sku']")
        if sku_el:
            product["sku"] = sku_el.get_text(strip=True)
        # Also try to get brand from product meta
        brand_el = soup.select_one(".woocommerce-product-attributes-item--attribute_pa_brand td")
        if brand_el:
            product["brand"] = brand_el.get_text(strip=True)
    except Exception:
        pass
    return product


# ─── STEP 4: save to SQLite ─────────────────────────────────────────────────

def save_to_sqlite(all_products: list[dict]) -> tuple[int, int, int]:
    from scraper.models.source import ScraperSource
    from scraper.models.category import ScraperCategory
    from scraper.models.brand import ScraperBrand
    from scraper.models.product import ScraperProduct
    from scraper.core.database import ScraperBase
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    engine = create_engine(f"sqlite:///{_DB_FILE}", echo=False)
    ScraperBase.metadata.create_all(engine)

    inserted = updated = skipped = 0

    with Session(engine) as session:
        # ── source ────────────────────────────────────────────────────
        source = session.execute(
            select(ScraperSource).where(ScraperSource.name == SOURCE_NAME)
        ).scalar_one_or_none()
        if not source:
            source = ScraperSource(name=SOURCE_NAME, base_url=BASE_URL, active=True)
            session.add(source)
            session.flush()

        # ── brand: KM (single brand for whole site) ───────────────────
        brand_cache: dict[str, ScraperBrand] = {}
        cat_cache: dict[str, ScraperCategory] = {}

        def get_brand(name: str) -> ScraperBrand:
            if name not in brand_cache:
                b = session.execute(
                    select(ScraperBrand).where(
                        ScraperBrand.source_id == source.id,
                        ScraperBrand.name == name,
                    )
                ).scalar_one_or_none()
                if not b:
                    b = ScraperBrand(source_id=source.id, name=name)
                    session.add(b)
                    session.flush()
                brand_cache[name] = b
            return brand_cache[name]

        def get_category(name: str, slug: str, url: str) -> ScraperCategory:
            if name not in cat_cache:
                c = session.execute(
                    select(ScraperCategory).where(
                        ScraperCategory.source_id == source.id,
                        ScraperCategory.name == name,
                    )
                ).scalar_one_or_none()
                if not c:
                    c = ScraperCategory(
                        source_id=source.id,
                        name=name,
                        external_id=slug,
                        url=url,
                    )
                    session.add(c)
                    session.flush()
                cat_cache[name] = c
            return cat_cache[name]

        for raw in all_products:
            name = raw.get("name", "").strip()
            if not name:
                skipped += 1
                continue

            external_id = raw.get("external_id", "")
            sku         = raw.get("sku", "") or external_id
            price       = raw.get("price")
            source_url  = raw.get("source_url", "")
            brand_name  = raw.get("brand", BRAND_NAME)

            cat_name = raw.get("_category_name", "عام")
            cat_slug = raw.get("_category_slug", "")
            cat_url  = raw.get("_category_url", "")

            category = get_category(cat_name, cat_slug, cat_url)
            brand    = get_brand(brand_name)

            # upsert by external_id
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
                existing.raw_data            = json.dumps(raw, ensure_ascii=False, default=str)
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
                    raw_data=json.dumps(raw, ensure_ascii=False, default=str),
                    last_scraped_at=datetime.now(),
                    is_synced=False,
                ))
                inserted += 1

        session.commit()

    print(f"  DB → inserted={inserted}, updated={updated}, skipped={skipped}")
    return inserted, updated, skipped


# ─── main ────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("  KMCO.SA — FULL SITE SCRAPER")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:

        # ── STEP 1: categories ────────────────────────────────────────
        print("\n[STEP 1] Discovering categories...")
        categories = await discover_categories(client)

        if not categories:
            # fallback
            categories = [
                {"slug": "linear-lighting",    "name": "اﻻﺿﺎءة اﻟﺨﻄﻴﺔ",     "url": "https://kmco.sa/product-category/linear-lighting/"},
                {"slug": "plugs-and-switches", "name": "الافياش والمفاتيح",   "url": "https://kmco.sa/product-category/plugs-and-switches/"},
                {"slug": "pvc-pipes",          "name": "مواسير Pvc",           "url": "https://kmco.sa/product-category/pvc-pipes/"},
            ]

        print(f"  Found {len(categories)} categories:")
        for c in categories:
            print(f"    [{c['slug']}] {c['name']}")

        # ── STEP 2: scrape each category ──────────────────────────────
        print(f"\n[STEP 2] Scraping {len(categories)} categories...\n")
        all_products: list[dict] = []
        seen_ids: set[str] = set()

        for i, cat in enumerate(categories, 1):
            print(f"── [{i}/{len(categories)}] {cat['name']} ────────────────────")
            try:
                products = await scrape_category(client, cat)
            except Exception as e:
                print(f"  [ERROR] {cat['name']}: {e}")
                continue

            # dedup
            new_products = []
            for p in products:
                pid = p.get("external_id", "") or p.get("source_url", "")
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    new_products.append(p)

            if new_products:
                all_products.extend(new_products)

                # ── STEP 3: enrich with SKU from product pages ────────
                print(f"  Enriching {len(new_products)} products (SKU/brand)...")
                tasks = [enrich_product(client, p) for p in new_products]
                enriched = await asyncio.gather(*tasks, return_exceptions=True)
                new_products = [p for p in enriched if isinstance(p, dict)]

                # ── STEP 4: save to DB ────────────────────────────────
                print(f"  Saving {len(new_products)} products to DB...")
                save_to_sqlite(new_products)
            else:
                print("  No new unique products.")

    print(f"\n{'='*60}")
    print(f"  Total unique products: {len(all_products)}")
    print("  Breakdown by category:")
    for name, count in Counter(p.get("_category_name", "?") for p in all_products).most_common():
        print(f"    {name}: {count}")

    # save raw JSON
    output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scraped_kmco.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_products, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n  Raw JSON → {output_file}")

    # regenerate HTML viewer
    print("\n[STEP 5] Regenerating HTML viewer...")
    import subprocess
    subprocess.run([sys.executable, "view_db.py"], check=False)

    print(f"\n{'='*60}")
    print("  DONE — check http://localhost:8765")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
