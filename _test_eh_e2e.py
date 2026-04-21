"""Final e2e test: scrape 2 pages of one category and save to DB."""
import asyncio, sys, os
sys.path.insert(0, r"C:\Users\USER\Documents\GitHub\ai-of-bacco")
os.chdir(r"C:\Users\USER\Documents\GitHub\ai-of-bacco")
_DB = r"C:\Users\USER\Documents\GitHub\ai-of-bacco\scraper_data.db"
for k, v in [
    ("SCRAPER_DATABASE_URL",      f"sqlite+aiosqlite:///{_DB}"),
    ("SCRAPER_DATABASE_URL_SYNC", f"sqlite:///{_DB}"),
    ("DATABASE_URL",              f"sqlite+aiosqlite:///{_DB}"),
    ("DATABASE_URL_SYNC",         f"sqlite:///{_DB}"),
    ("SCRAPER_SYNC_API_URL",      "https://api.example.com"),
    ("SCRAPER_SYNC_API_KEY",      ""),
    ("SECRET_KEY",                "dev"),
    ("OPENAI_API_KEY",            "sk-placeholder"),
]:
    os.environ.setdefault(k, v)

import importlib.util
spec = importlib.util.spec_from_file_location(
    "seh", r"C:\Users\USER\Documents\GitHub\ai-of-bacco\scrape_electric_house.py"
)
seh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seh)

from playwright.async_api import async_playwright
import httpx

async def test():
    async with async_playwright() as pw:
        br, ctx = await seh._make_context(pw)
        page = await ctx.new_page()

        test_cat = {
            "name": "E-Mobility",
            "url":  "https://electric-house.com/en/e-mobility.html",
        }

        # Scrape 2 pages
        already: set[str] = set()
        page_url = test_cat["url"] + "?product_list_limit=48&page=1"
        all_products = []

        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=seh.HEADERS) as client:
            for pg in range(1, 3):
                print(f"Scraping page {pg}: {page_url}")
                products, next_url = await seh.scrape_page(page, page_url, test_cat["name"], test_cat["url"])
                new = [p for p in products if p["external_id"] not in already]
                for p in new:
                    already.add(p["external_id"])
                print(f"  {len(products)} found, {len(new)} new, next={next_url}")

                if new:
                    print(f"  Enriching {len(new[:5])} (first 5 only for test)...")
                    import asyncio as asy
                    enriched = await asy.gather(*[seh.enrich_product(client, p) for p in new[:5]])
                    for p in enriched:
                        if isinstance(p, dict):
                            print(f"    {p['name'][:50]:50s}  SKU={p['sku'] or '?':20s}  price={p['price']}")
                    all_products.extend(new)

                if not next_url:
                    break
                page_url = next_url

        await page.close()
        await br.close()

        if all_products:
            print(f"\nSaving {len(all_products)} products to DB...")
            ins, upd, skp = seh.save_to_sqlite(all_products)
            print(f"Done: inserted={ins}, updated={upd}, skipped={skp}")

asyncio.run(test())
