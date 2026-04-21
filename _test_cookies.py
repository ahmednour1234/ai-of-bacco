"""
Use Playwright to get session cookies, then test if httpx works with those cookies.
This avoids Playwright overhead for 16,400 products.
"""
import asyncio, json, httpx
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
        )
        page = await ctx.new_page()

        # Capture the serviceability API request/response
        product_data = []

        async def on_response(response):
            if "serviceability" in response.url and response.status == 200:
                try:
                    data = await response.json()
                    product_data.extend(data)
                    print(f"[Serviceability API] {len(data)} products")
                except Exception as e:
                    print(f"[Serviceability parse error] {e}")

        page.on("response", on_response)

        test_url = "https://eshop.se.com/sa/all-products/ev-chargers.html"
        print(f"Loading {test_url} with Playwright...")
        await page.goto(test_url, wait_until="networkidle", timeout=45000)
        await page.wait_for_timeout(3000)

        # Get DOM structure
        count = await page.evaluate("""() => {
            const items = document.querySelectorAll('li.product-item');
            return {
                count: items.length,
                firstHTML: items.length > 0 ? items[0].outerHTML.substring(0, 600) : 'none',
            };
        }""")
        print(f"\nDOM product-item count: {count['count']}")
        if count['count'] == 0:
            # Try other selectors
            alt = await page.evaluate("""() => {
                const sels = ['li[class*=product]', '.product-card', '[data-product-id]', 'li[class*=item]'];
                let found = {};
                for (const s of sels) {
                    found[s] = document.querySelectorAll(s).length;
                }
                return found;
            }""")
            print("Alternative selectors:", alt)
        else:
            print("First product HTML:", count['firstHTML'])

        # Get cookies
        cookies = await ctx.cookies()
        cookie_dict = {c['name']: c['value'] for c in cookies}
        print(f"\nCookies: {list(cookie_dict.keys())}")

        # Save cookies
        with open("_se_cookies.json", "w") as f:
            json.dump(cookie_dict, f, indent=2)
        print("Saved cookies to _se_cookies.json")

        await browser.close()

    # Now test httpx with cookies
    if cookie_dict:
        print("\n\nTesting httpx WITH cookies...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }
        cookie_header = "; ".join(f"{k}={v}" for k, v in cookie_dict.items())
        headers["Cookie"] = cookie_header

        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as c:
            r = await c.get(test_url, headers=headers)
            print(f"Status: {r.status_code} | Length: {len(r.text)}")
            if r.status_code == 200 and "product-item" in r.text:
                print("SUCCESS! httpx gets products with cookies!")
                # Count products
                from bs4 import BeautifulSoup
                s = BeautifulSoup(r.text, "html.parser")
                items = s.select("li.product-item")
                print(f"Found {len(items)} product items in HTML")
                if items:
                    print("First item:", items[0].get_text(strip=True)[:200])
            else:
                print(f"Response text: {r.text[:300]}")
                print("product-item in HTML:", "product-item" in r.text)

asyncio.run(main())
