"""
scrape_elburoj_playwright.py
-----------------------------
Scrapes El Buroj using Playwright (headless Chromium).
Intercepts Salla's internal API calls to capture product data.

Usage:
    .\.venv\Scripts\python scrape_elburoj_playwright.py
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scraper_data.db")
_SQLITE_URL = f"sqlite+aiosqlite:///{_DB_FILE}"

os.environ.setdefault("SCRAPER_DATABASE_URL", _SQLITE_URL)
os.environ.setdefault("SCRAPER_DATABASE_URL_SYNC", f"sqlite:///{_DB_FILE}")
os.environ.setdefault("DATABASE_URL", _SQLITE_URL)
os.environ.setdefault("DATABASE_URL_SYNC", f"sqlite:///{_DB_FILE}")
os.environ.setdefault("SCRAPER_SYNC_API_URL", "https://api.example.com/v1/products/import")
os.environ.setdefault("SCRAPER_SYNC_API_KEY", "")
os.environ.setdefault("SECRET_KEY", "dev-only-secret")
os.environ.setdefault("OPENAI_API_KEY", "sk-placeholder")

from playwright.async_api import async_playwright

TARGET_URL = "https://elburoj.com/ar/%D8%A5%D9%86%D8%A7%D8%B1%D8%A9/c539403396"
# Also try the cables category which had items on the homepage
CABLES_URL = "https://elburoj.com/ar/%D9%83%D8%A7%D8%A8%D9%84%D8%A7%D8%AA/c413920175"


async def scrape_with_playwright(url: str) -> tuple[list[dict], list[dict]]:
    """Open a page, wait for API calls, capture products from Salla API responses."""
    products = []
    captured_api_data = []
    captured_token = None

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            locale="ar",
            extra_http_headers={"Accept-Language": "ar,en;q=0.5"},
        )
        page = await context.new_page()

        # Intercept requests to capture the Authorization token
        async def handle_request(request):
            nonlocal captured_token
            if "api.salla.dev" in request.url:
                auth = request.headers.get("authorization", "")
                if auth and not captured_token:
                    captured_token = auth
                    print(f"  [TOKEN] {auth[:40]}...")

        # Intercept API responses to capture product data
        async def handle_response(response):
            try:
                url_str = response.url
                ct = response.headers.get("content-type", "")
                if "api.salla.dev" in url_str and "json" in ct:
                    try:
                        body = await response.json()
                    except Exception:
                        return
                    captured_api_data.append({"url": url_str, "data": body})
                    print(f"  [API] {url_str[-100:]}")
                    # Extract products directly from Salla API response
                    if isinstance(body, dict):
                        data = body.get("data", [])
                        if isinstance(data, list):
                            for p in data:
                                if isinstance(p, dict) and ("name" in p or "id" in p):
                                    products.append(p)
            except Exception:
                pass

        page.on("request", handle_request)
        page.on("response", handle_response)

        print(f"[Playwright] Loading {url}")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"  [WARN] goto: {e}")

        # Wait for Salla's product-card JS to fire API calls
        await page.wait_for_timeout(8000)

        print(f"[Playwright] Page title: {await page.title()}")
        print(f"[Playwright] Captured API calls so far: {len(captured_api_data)}")
        print(f"[Playwright] Products from API so far: {len(products)}")
        if captured_token:
            print(f"[Playwright] Token captured: YES ({captured_token[:30]}...)")
        else:
            print(f"[Playwright] Token captured: NO")

        # Also check captured API data summary
        for item in captured_api_data:
            data = item["data"]
            if isinstance(data, dict) and "data" in data:
                inner = data["data"]
                if isinstance(inner, list) and len(inner) > 0:
                    print(f"  API {item['url'][-80:]} -> {len(inner)} items")

        await browser.close()

    return products, captured_api_data, captured_token


async def fetch_all_pages_with_token(token: str, category_id: str = "539403396") -> list[dict]:
    """Use the captured Salla token to fetch all product pages directly."""
    import httpx
    all_products = []
    page_num = 1

    headers = {
        "Authorization": token,
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://elburoj.com",
        "Referer": "https://elburoj.com/",
    }

    while True:
        url = (
            f"https://api.salla.dev/store/v1/products"
            f"?source=categories"
            f"&includes[]=images"
            f"&filterable=1"
            f"&source_value[]={category_id}"
            f"&page={page_num}"
            f"&per_page=20"
        )
        print(f"  [API] Fetching page {page_num}: {url[-80:]}")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=headers)
        print(f"    Status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"    Body: {resp.text[:200]}")
            break
        data = resp.json()
        items = data.get("data", [])
        if not items:
            print(f"    Empty page, stopping.")
            break
        all_products.extend(items)
        print(f"    Got {len(items)} products (total: {len(all_products)})")
        pagination = data.get("pagination", {})
        if page_num >= pagination.get("totalPages", 1):
            break
        page_num += 1

    return all_products


async def main():
    print("=" * 60)
    print("EL BUROJ PLAYWRIGHT SCRAPER")
    print("=" * 60)

    # Step 1: Get the Salla auth token by loading the category page
    print("\n[1] Loading El Buroj lighting category to capture API token...")
    products, api_data, token = await scrape_with_playwright(TARGET_URL)

    if not token:
        print("\n[2] Lighting category empty — trying cables category to get token...")
        products2, api_data2, token = await scrape_with_playwright(CABLES_URL)
        products.extend(products2)
        api_data.extend(api_data2)

    if not token:
        print("\n[3] Trying homepage...")
        products3, api_data3, token = await scrape_with_playwright("https://elburoj.com/ar")
        products.extend(products3)
        api_data.extend(api_data3)

    print(f"\nProducts from page render: {len(products)}")

    # Step 2: If we got a token, fetch all products directly from Salla API
    if token:
        print(f"\n[API] Token obtained! Fetching all lighting products directly from Salla API...")
        # Try the lighting category
        api_products = await fetch_all_pages_with_token(token, "539403396")
        if not api_products:
            print("  Lighting category empty — trying main 'كهرباء' category (931950675)...")
            api_products = await fetch_all_pages_with_token(token, "931950675")
        if not api_products:
            print("  Trying all products (no category filter)...")
            api_products = await fetch_all_pages_with_token(token, "")
        products.extend(api_products)

    print(f"\nTotal products collected: {len(products)}")

    # Deduplicate by product ID
    seen = {}
    for p in products:
        pid = str(p.get("id", "")) or str(p.get("url", ""))
        if pid and pid not in seen:
            seen[pid] = p
    products = list(seen.values())
    print(f"After dedup: {len(products)}")

    # Print summary
    print("\n" + "=" * 60)
    print("SCRAPED PRODUCTS")
    print("=" * 60)
    for i, p in enumerate(products[:30]):
        name = p.get("name", "—")
        if isinstance(name, dict):
            name = name.get("ar") or name.get("en") or str(name)
        price = p.get("price", {})
        if isinstance(price, dict):
            price_str = str(price.get("amount", "—"))
        else:
            price_str = str(price) if price else "—"
        sku = p.get("sku") or p.get("product_number") or "—"
        print(f"  {i+1:3}. {name[:50]:<50}  {price_str:>10}  SKU: {sku}")

    # Save raw results to JSON for inspection
    output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scraped_products_raw.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({"products": products, "api_data": api_data, "token": token}, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nFull results saved to: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())

