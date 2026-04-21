import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as pw:
        br = await pw.chromium.launch(headless=True)
        ctx = await br.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124")
        page = await ctx.new_page()
        
        await page.goto("https://eshop.se.com/sa/all-products/ev-chargers.html?product_list_limit=48",
                        wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(8000)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(3000)

        # Check what selectors exist
        info = await page.evaluate("""() => {
            const sels = [
                'li.product-item', 'li[class*=product]', '.product-item',
                '[data-product-id]', '.card-interactive', 'li.item',
                'ol.product-items li', '.products-grid li', 'li[class*=item]',
                'form.product_addtocart_form'
            ];
            const result = {};
            for (const s of sels) {
                result[s] = document.querySelectorAll(s).length;
            }
            // also get a snippet of first matching thing
            const first = document.querySelector('li.product-item') ||
                          document.querySelector('[data-product-id]') ||
                          document.querySelector('.card-interactive') ||
                          document.querySelector('li[class*=item]');
            result['_firstEl'] = first ? first.className : 'NONE';
            result['_firstHTML'] = first ? first.outerHTML.substring(0, 800) : 'NONE';
            return result;
        }""")
        
        for k, v in info.items():
            if k.startswith('_'):
                print(f"{k}:\n{v}\n")
            else:
                print(f"  {k}: {v}")
        
        await br.close()

asyncio.run(main())
