"""
Find what API endpoint the Schneider e-shop uses to load products.
Run with: .\.venv\Scripts\python _find_se_api.py
"""
import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()

        captured = []

        # Intercept all requests
        async def on_request(request):
            url = request.url
            if any(x in url for x in ["api", "graphql", "search", "product", "catalog", "rest"]):
                captured.append({
                    "method": request.method,
                    "url": url[:200],
                    "headers": dict(list(request.headers.items())[:5]),
                })

        async def on_response(response):
            url = response.url
            ct = response.headers.get("content-type", "")
            if "json" in ct and any(x in url for x in ["api", "graphql", "product", "search", "catalog", "rest"]):
                try:
                    body = await response.text()
                    if len(body) > 100:
                        print(f"\n[API RESPONSE] {url[:120]}")
                        print(f"  Content-Type: {ct}")
                        print(f"  Body preview: {body[:500]}")
                except Exception:
                    pass

        page.on("request", on_request)
        page.on("response", on_response)

        url = "https://eshop.se.com/sa/all-products/ev-chargers.html"
        print(f"Navigating to {url} ...")
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(8000)  # wait for JS to load products

        print(f"\n\nCaptured {len(captured)} API-like requests:")
        for r in captured[:20]:
            print(f"  [{r['method']}] {r['url']}")

        # Check how many products are in the DOM
        items = await page.query_selector_all("li.product-item, li[class*='product-item'], .product-card")
        print(f"\nProducts in DOM: {len(items)}")

        # Get first product's outerHTML
        if items:
            html = await items[0].inner_html()
            print(f"\nFirst product HTML snippet:\n{html[:800]}")

        # Get cookies for potential reuse
        cookies = await page.context.cookies()
        print(f"\nCookies: {[c['name'] for c in cookies[:5]]}")

        await browser.close()

asyncio.run(main())
