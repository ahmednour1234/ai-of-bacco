"""Debug3: dump full HTML of first product card on electric-house.com."""
import asyncio, sys, os
sys.path.insert(0, r"C:\Users\USER\Documents\GitHub\ai-of-bacco")
os.chdir(r"C:\Users\USER\Documents\GitHub\ai-of-bacco")
for k, v in [("SCRAPER_DATABASE_URL", "sqlite:///x.db"), ("SECRET_KEY", "dev"),
              ("OPENAI_API_KEY", "sk-x"), ("DATABASE_URL", "sqlite:///x.db"),
              ("DATABASE_URL_SYNC", "sqlite:///x.db"),
              ("SCRAPER_DATABASE_URL_SYNC", "sqlite:///x.db"),
              ("SCRAPER_SYNC_API_URL", "https://api.example.com"), ("SCRAPER_SYNC_API_KEY", "")]:
    os.environ.setdefault(k, v)

from playwright.async_api import async_playwright

async def debug():
    async with async_playwright() as pw:
        br = await pw.chromium.launch(headless=True)
        ctx = await br.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124",
            locale="en",
            extra_http_headers={"Accept-Language": "en,ar;q=0.5"},
        )
        page = await ctx.new_page()
        url = "https://electric-house.com/en/load-centers-circuit-breakers.html?product_list_limit=12"
        await page.goto(url, wait_until="networkidle", timeout=60_000)
        await page.wait_for_timeout(5000)

        # Dump the HTML of the product grid container
        grid_html = await page.evaluate("""() => {
            const grid = document.querySelector('[class*="category-product_items"]');
            if (!grid) return 'GRID NOT FOUND';
            return grid.outerHTML.substring(0, 8000);
        }""")
        print("--- Product grid HTML ---")
        print(grid_html[:8000])

        # Also dump all anchor text+href in the grid
        links_in_grid = await page.evaluate("""() => {
            const grid = document.querySelector('[class*="category-product_items"]');
            if (!grid) return [];
            return Array.from(grid.querySelectorAll('a[href]')).map(a => ({
                href: a.getAttribute('href'),
                text: a.textContent.trim().substring(0, 80),
                cls: a.className.substring(0, 80),
            }));
        }""")
        print("\n--- Links in grid ---")
        for l in links_in_grid[:20]:
            print(f"  href={l['href'][:70]}")
            print(f"    text={l['text'][:60]}")
            print(f"    cls={l['cls'][:60]}")

        await br.close()

asyncio.run(debug())
