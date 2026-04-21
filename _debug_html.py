import httpx, asyncio, re

async def main():
    headers = {"User-Agent": "Mozilla/5.0 Chrome/124", "Accept-Language": "en-US"}
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as c:
        r = await c.get(
            "https://eshop.se.com/sa/all-products/ev-chargers.html?product_list_limit=48",
            headers=headers
        )
        print("Status:", r.status_code)
        html = r.text

        # Look for product-item
        idx = html.find("product-item")
        if idx > 0:
            print(f"\nFound 'product-item' at index {idx}")
            print(html[max(0, idx-300):idx+1000])
        else:
            print("\nNo 'product-item' class found in HTML!")
            # Check for SAR prices
            sar_idx = html.find("SAR")
            if sar_idx > 0:
                print(f"\nFound SAR price at {sar_idx}:")
                print(html[max(0, sar_idx-200):sar_idx+200])
            else:
                print("No SAR prices found either - page might be empty or JS-rendered")
            # Show first 2000 chars
            with open("_debug_page.html", "w", encoding="utf-8") as f:
                f.write(html)
            print(f"\nSaved full HTML to _debug_page.html ({len(html)} bytes)")

asyncio.run(main())
