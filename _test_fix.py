import asyncio, sys, re
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as pw:
        br = await pw.chromium.launch(headless=True)
        ctx = await br.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124")
        page = await ctx.new_page()
        
        price_map = {}
        async def handle_response(response):
            if "serviceability" in response.url and response.status == 200:
                try:
                    data = await response.json()
                    for item in (data if isinstance(data, list) else []):
                        sku = item.get("sku","").upper()
                        if sku:
                            price_map[sku] = {
                                "special_price": item.get("special_price"),
                                "orig_price": item.get("orig_price")
                            }
                except: pass
        page.on("response", handle_response)
        
        await page.goto("https://eshop.se.com/sa/all-products/ev-chargers.html?product_list_limit=48",
                        wait_until="domcontentloaded", timeout=30000)
        try:
            await page.wait_for_selector("form.product_addtocart_form", timeout=15000)
        except:
            await page.wait_for_timeout(6000)

        items = await page.evaluate("""() => {
            const items = [];
            document.querySelectorAll('form.product_addtocart_form').forEach(card => {
                const linkEl = card.querySelector('a.product-item-link');
                const name = linkEl ? linkEl.textContent.trim() : '';
                const url  = linkEl ? linkEl.getAttribute('href') : '';
                const skuEl = card.querySelector('.product-card-num');
                const sku = skuEl ? skuEl.textContent.trim() : '';
                const finalPriceEl = card.querySelector('[data-price-type="finalPrice"]');
                const price = finalPriceEl ? parseFloat(finalPriceEl.getAttribute('data-price-amount')||'0') : 0;
                if (url) items.push({name: name.substring(0,60), url, sku, price});
            });
            return items;
        }""")
        
        print(f"Products found: {len(items)}")
        print(f"Price map entries: {len(price_map)}")
        for p in items[:3]:
            print(f"  {p['sku']}: {p['name']} | SAR {p['price']}")
        await br.close()

asyncio.run(main())
