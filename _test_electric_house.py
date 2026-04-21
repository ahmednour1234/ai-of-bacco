"""Quick smoke-test: discover categories + scrape first page of first category."""
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


async def test():
    async with async_playwright() as pw:
        br, ctx = await seh._make_context(pw)

        # ── Step 1: discover categories ────────────────────────────────────
        print("Discovering categories...")
        cats = await seh.discover_categories(ctx)
        print(f"Discovered {len(cats)} from nav")
        for c in cats[:6]:
            print(f"  {c['name']}: {c['url']}")

        # ── Step 2: scrape first page of 'Load Centers' ────────────────────
        test_cat = {
            "name": "Load Centers & Circuit Breakers",
            "url":  "https://electric-house.com/en/load-centers-circuit-breakers.html",
        }
        page = await ctx.new_page()
        url = test_cat["url"] + "?product_list_limit=48&page=1"
        print(f"\nScraping first page: {url}")
        products, next_url = await seh.scrape_page(
            page, url, test_cat["name"], test_cat["url"]
        )
        await page.close()

        print(f"Products found: {len(products)}")
        print(f"Next page: {next_url}")
        for p in products[:5]:
            nm = p['name'][:55]
            print(f"  {nm:55s}  eid={p['external_id'][:30]:30s}  price={p['price']}")

        await br.close()

asyncio.run(test())
