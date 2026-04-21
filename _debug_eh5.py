"""Debug5: check pagination links structure."""
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
        ctx = await br.new_context(user_agent="Mozilla/5.0 Chrome/124", locale="en",
            extra_http_headers={"Accept-Language": "en,ar;q=0.5"})
        page = await ctx.new_page()

        url = "https://electric-house.com/en/load-centers-circuit-breakers.html?product_list_limit=48&page=1"
        await page.goto(url, wait_until="networkidle", timeout=60_000)
        await page.wait_for_timeout(3000)

        print(f"Current URL: {page.url}")

        # Check pagination widget HTML
        pag_html = await page.evaluate("""() => {
            const root = document.querySelector('[class*="pagination-root"]');
            return root ? root.outerHTML.substring(0, 2000) : 'NOT FOUND';
        }""")
        print("\n--- Pagination HTML ---")
        print(pag_html[:2000])

        # Get all anchor hrefs in pagination
        pag_links = await page.evaluate("""() => {
            const root = document.querySelector('[class*="pagination-root"]') ||
                         document.querySelector('[class*="category-pagination"]');
            if (!root) return [];
            return Array.from(root.querySelectorAll('a')).map(a => ({
                text: a.textContent.trim(),
                href: a.getAttribute('href') || '',
                cls: a.className.substring(0, 60),
            }));
        }""")
        print("\n--- Pagination links ---")
        for l in pag_links:
            print(f"  text={l['text']:5s}  href={l['href']}  cls={l['cls'][:50]}")

        # Run the same pagination JS from scrape_page
        next_url = await page.evaluate("""() => {
            const candidates = [
                document.querySelector('a[aria-label="Go to next page"]'),
                document.querySelector('a[aria-label="Next"]'),
                document.querySelector('a[rel="next"]'),
                document.querySelector('[class*="pagination"] a[class*="next"]'),
            ];
            for (const el of candidates) {
                if (el) {
                    const h = el.getAttribute('href') || '';
                    if (h) return h.startsWith('http') ? h : 'https://electric-house.com' + h;
                }
            }
            const paginationRoot = document.querySelector('[class*="pagination-root"]');
            if (!paginationRoot) return 'NO PAGINATION ROOT';
            const pageLinks = Array.from(paginationRoot.querySelectorAll('a[href]'));
            const curUrl = window.location.href;
            const curPageM = curUrl.match(/[?&]page=(\\d+)/);
            const curPage = curPageM ? parseInt(curPageM[1]) : 1;
            const info = {curUrl, curPage, linkCount: pageLinks.length,
                links: pageLinks.map(a => ({text: a.textContent.trim(), href: a.getAttribute('href')}))};
            return JSON.stringify(info);
        }""")
        print(f"\n--- Pagination next_url result ---")
        print(next_url)

        # How many products on page 2?
        await page.goto(
            "https://electric-house.com/en/load-centers-circuit-breakers.html?product_list_limit=48&page=2",
            wait_until="networkidle", timeout=60_000)
        await page.wait_for_timeout(3000)
        count2 = await page.eval_on_selector_all('[class*="galleryItem-root"]', 'els => els.length')
        print(f"\nPage 2 product count: {count2}")
        print(f"Page 2 URL: {page.url}")

        await br.close()

asyncio.run(debug())
