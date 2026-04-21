"""Debug2: find actual product selectors on electric-house.com."""
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
        await page.goto(url, wait_until="networkidle", timeout=60_000)
        print("networkidle reached. Waiting 5s more...")
        await page.wait_for_timeout(5000)

        # Check the full page HTML size
        html_len = await page.evaluate("() => document.documentElement.outerHTML.length")
        print(f"HTML length: {html_len}")

        # Sample 'product' class elements
        sample = await page.evaluate("""() => {
            const els = document.querySelectorAll('[class*="product"]');
            return Array.from(els).slice(0, 10).map(el => ({
                tag: el.tagName,
                cls: el.className,
                text: el.innerText ? el.innerText.substring(0, 80) : '',
                html: el.outerHTML.substring(0, 200),
            }));
        }""")
        print("\n--- Sample [class*=product] elements ---")
        for s in sample:
            print(f"  <{s['tag']} class='{s['cls'][:60]}'>")
            print(f"    text: {s['text'][:70]}")

        # Check div structure more deeply
        deep = await page.evaluate("""() => {
            function walk(el, depth) {
                if (depth > 4) return '';
                const tag = el.tagName;
                const cls = (el.className || '').toString().substring(0, 50);
                const children = Array.from(el.children);
                let s = '  '.repeat(depth) + tag + (cls ? '.' + cls.split(' ')[0] : '') + '\\n';
                if (children.length <= 5) {
                    children.forEach(c => { s += walk(c, depth + 1); });
                } else {
                    s += '  '.repeat(depth+1) + `(${children.length} children)\\n`;
                }
                return s;
            }
            return walk(document.body, 0).substring(0, 3000);
        }""")
        print("\n--- DOM tree (depth 4) ---")
        print(deep[:3000])

        # Try to find any anchor with .html in href
        anchors = await page.evaluate("""() => {
            const hrefs = [];
            document.querySelectorAll('a[href]').forEach(a => {
                const h = a.getAttribute('href') || '';
                if (h.includes('/en/') && h.endsWith('.html') && !h.includes('/en/brands')) {
                    hrefs.push(h);
                }
            });
            return hrefs.slice(0, 15);
        }""")
        print("\n--- Sample product links ---")
        for h in anchors:
            print(" ", h)

        # Check title + URL
        title = await page.title()
        cur_url = page.url
        print(f"\nTitle: {title}")
        print(f"URL: {cur_url}")

        await br.close()

asyncio.run(debug())
