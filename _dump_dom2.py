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

        info = await page.evaluate("""() => {
            const card = document.querySelector('.product-item') ||
                         document.querySelector('form.product_addtocart_form') ||
                         document.querySelector('.card-interactive');
            if (!card) return {html: 'NO CARD FOUND', parent: 'none'};
            return {
                tagName: card.tagName,
                className: card.className.substring(0, 100),
                html: card.outerHTML.substring(0, 2000),
                parentTag: card.parentElement ? card.parentElement.tagName : 'none',
                parentClass: card.parentElement ? card.parentElement.className.substring(0,80) : ''
            };
        }""")
        print("Tag:", info.get("tagName"))
        print("Class:", info.get("className"))
        print("Parent:", info.get("parentTag"), "|", info.get("parentClass"))
        print("HTML:")
        print(info.get("html"))
        await br.close()

asyncio.run(main())
