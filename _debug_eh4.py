"""Debug4: check pagination + nav on electric-house.com."""
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
            user_agent="Mozilla/5.0 Chrome/124",
            locale="en",
            extra_http_headers={"Accept-Language": "en,ar;q=0.5"},
        )
        page = await ctx.new_page()
        url = "https://electric-house.com/en/load-centers-circuit-breakers.html?product_list_limit=12"
        await page.goto(url, wait_until="networkidle", timeout=60_000)
        await page.wait_for_timeout(3000)

        # Check pagination
        pag = await page.evaluate("""() => {
            // Find all elements related to pagination
            const els = document.querySelectorAll('[class*="pagination"], [class*="pager"], [class*="page"]');
            const result = [];
            els.forEach(el => {
                if (el.children.length > 0 || el.tagName === 'A' || el.tagName === 'BUTTON') {
                    result.push({
                        tag: el.tagName,
                        cls: el.className.substring(0, 80),
                        text: el.textContent.trim().substring(0, 50),
                        href: el.getAttribute('href') || '',
                    });
                }
            });
            return result.slice(0, 20);
        }""")
        print("--- Pagination elements ---")
        for p2 in pag:
            print(f"  <{p2['tag']} cls='{p2['cls'][:60]}'> text={p2['text'][:40]} href={p2['href']}")

        # Extract product items using item-root class
        products = await page.evaluate("""() => {
            const items = [];
            const BASE = 'https://electric-house.com';
            document.querySelectorAll('[class*="galleryItem-root"]').forEach(card => {
                // Name + URL
                const nameLink = card.querySelector('a[class*="item-name"]');
                const name = nameLink ? nameLink.textContent.trim() : '';
                let href = nameLink ? nameLink.getAttribute('href') : '';
                if (href && !href.startsWith('http')) href = BASE + href;

                // Image (the lazy-loaded one)
                const imgEl = card.querySelector('img[loading="lazy"]');
                let img = imgEl ? (imgEl.getAttribute('src') || '') : '';
                if (img && !img.startsWith('http')) img = BASE + img;

                // Prices: first productPrice-root = Excl VAT
                const priceRoots = card.querySelectorAll('[class*="productPrice-root"]');
                let price = null, orig = null;
                if (priceRoots.length > 0) {
                    const priceTags = priceRoots[0].querySelectorAll('[class*="productPrice-priceTag"]');
                    if (priceTags.length >= 1) {
                        price = parseFloat(priceTags[0].textContent.replace(/[^0-9.]/g, '')) || null;
                    }
                    if (priceTags.length >= 2) {
                        orig = parseFloat(priceTags[1].textContent.replace(/[^0-9.]/g, '')) || null;
                    }
                }

                // Stock badge
                const stockBadge = card.querySelector('[class*="rightTopBadge"]');
                const in_stock = stockBadge ? stockBadge.textContent.trim() : '';

                // Discount badge
                const discBadge = card.querySelector('[class*="leftTopBadge"]');
                const discount = discBadge ? discBadge.textContent.trim() : '';

                if (name && href) items.push({name, href, img: img.substring(0,100), price, orig, in_stock, discount});
            });
            return items;
        }""")
        print(f"\n--- Products ({len(products)}) ---")
        for p2 in products[:5]:
            print(f"  name: {p2['name'][:60]}")
            print(f"  href: {p2['href'][:70]}")
            print(f"  price={p2['price']}  orig={p2['orig']}  stock={p2['in_stock']}  disc={p2['discount']}")
            print(f"  img: {p2['img'][:70]}")

        # Nav category links
        nav_cats = await page.evaluate("""() => {
            const BASE = 'https://electric-house.com';
            const cats = {};
            document.querySelectorAll('a[href]').forEach(a => {
                let href = a.getAttribute('href') || '';
                if (!href.startsWith('http')) href = BASE + href;
                // Top-level category: /en/<slug>.html (no subcategory slash)
                if (/\\/en\\/[^/]+\\.html$/.test(href) &&
                    !href.includes('/brands/') && !href.includes('/brand/') &&
                    !href.includes('/register') && !href.includes('/privacy') &&
                    !href.includes('/terms') && !href.includes('/our-location') &&
                    !href.includes('/gift-items')) {
                    const text = a.textContent.trim();
                    if (text && !cats[href]) cats[href] = text;
                }
            });
            return Object.entries(cats).map(([url, name]) => ({name, url}));
        }""")
        print(f"\n--- Top-level category links ({len(nav_cats)}) ---")
        for c in nav_cats:
            print(f"  {c['name']}: {c['url']}")

        await br.close()

asyncio.run(debug())
