"""Debug: dump product-related HTML from electric-house.com category page."""
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
        print(f"Loading: {url}")
        await page.goto(url, wait_until="networkidle", timeout=45_000)
        print("Page loaded. Waiting extra 3s...")
        await page.wait_for_timeout(3000)

        # Check what product-related selectors exist
        selectors_to_check = [
            "li.product-item",
            ".product-item",
            ".products-grid",
            ".products-list",
            ".product-item-info",
            "a.product-item-link",
            "[data-price-type]",
            ".price",
            ".product-items",
            "ol.products",
            ".items",
            ".product",
            "form.product_addtocart_form",
            "[class*='product']",
        ]
        print("\n--- Selector counts ---")
        for sel in selectors_to_check:
            count = await page.eval_on_selector_all(sel, "els => els.length")
            if count > 0:
                print(f"  {sel:45s}: {count}")

        # Dump classes of direct children of body
        body_children = await page.evaluate("""() => {
            return Array.from(document.body.children).map(el =>
                el.tagName + '.' + (el.className || '').split(' ').join('.')
            ).join('\\n');
        }""")
        print("\n--- Body children ---")
        print(body_children[:2000])

        # Get a snippet of the first product-like element
        snippet = await page.evaluate("""() => {
            const els = document.querySelectorAll('li.product-item, .product-item-info, form.product_addtocart_form');
            if (els.length === 0) return 'NONE FOUND';
            return els[0].outerHTML.substring(0, 1500);
        }""")
        print("\n--- First product element snippet ---")
        print(snippet[:2000])

        # Check nav links
        nav_links = await page.evaluate("""() => {
            const links = [];
            document.querySelectorAll('nav a, .navigation a, .nav-sections a').forEach(a => {
                const href = a.getAttribute('href') || '';
                if (href.includes('electric-house.com/en/') && href.endsWith('.html')) {
                    links.push(href);
                }
            });
            return links.slice(0, 20);
        }""")
        print("\n--- Nav links ---")
        for l in nav_links:
            print(" ", l)

        await br.close()

asyncio.run(debug())
