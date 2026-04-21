import asyncio, sys, os
sys.path.insert(0, r"C:\Users\USER\Documents\GitHub\ai-of-bacco")
os.chdir(r"C:\Users\USER\Documents\GitHub\ai-of-bacco")
_DB = r"C:\Users\USER\Documents\GitHub\ai-of-bacco\scraper_data.db"
for k, v in [
    ("SCRAPER_DATABASE_URL", f"sqlite+aiosqlite:///{_DB}"),
    ("SCRAPER_DATABASE_URL_SYNC", f"sqlite:///{_DB}"),
    ("DATABASE_URL", f"sqlite+aiosqlite:///{_DB}"),
    ("DATABASE_URL_SYNC", f"sqlite:///{_DB}"),
    ("SCRAPER_SYNC_API_URL", "https://api.example.com"),
    ("SCRAPER_SYNC_API_KEY", ""),
    ("SECRET_KEY", "dev"),
    ("OPENAI_API_KEY", "sk-placeholder"),
]:
    os.environ.setdefault(k, v)

from playwright.async_api import async_playwright
import importlib.util

spec = importlib.util.spec_from_file_location("ss", r"C:\Users\USER\Documents\GitHub\ai-of-bacco\scrape_schneider.py")
ss = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ss)

async def test():
    async with async_playwright() as pw:
        br = await pw.chromium.launch(headless=True)
        ctx = await br.new_context(user_agent="Mozilla/5.0 Chrome/124")
        page = await ctx.new_page()
        price_map = {}
        ss.attach_price_interceptor(page, price_map)
        url = "https://eshop.se.com/sa/all-products/ev-chargers.html?product_list_limit=48"
        products, nxt = await ss.scrape_page(page, url, "EV Chargers", url, price_map)
        print(f"Products found: {len(products)}")
        print(f"Price map entries: {len(price_map)}")
        for p in products[:5]:
            print(f"  {str(p['name'])[:50]:50s}  SKU={str(p['sku']):20s}  price={p['price']}")
        print(f"Next page: {nxt}")
        await br.close()

asyncio.run(test())
