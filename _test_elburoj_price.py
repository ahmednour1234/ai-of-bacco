import asyncio, httpx, re, sqlite3, json

DB = "scraper_data.db"

async def test():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT p.external_id, p.source_url, p.raw_data
        FROM scraper_products p
        JOIN scraper_sources s ON p.source_id = s.id
        WHERE s.name = 'El Buroj' AND (p.price IS NULL OR p.price = 0)
        LIMIT 3
    """).fetchall()
    conn.close()

    for row in rows:
        ext_id = row["external_id"]
        url = row["source_url"]
        raw = json.loads(row["raw_data"] or "{}")
        print(f"\n=== Product {ext_id} ===")
        print(f"URL: {url}")
        print(f"raw price={raw.get('price')} regular_price={raw.get('regular_price')}")

        # Try Salla API
        api_url = f"https://elburoj.salla.sa/api/products/{ext_id}"
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
                r = await c.get(api_url, headers={"User-Agent": "Mozilla/5.0"})
                print(f"Salla API {r.status_code}: {api_url}")
                if r.status_code == 200:
                    body = r.json()
                    data = body.get("data", body)
                    print(f"  API price: {data.get('price')} regular_price: {data.get('regular_price')}")
        except Exception as e:
            print(f"  API error: {e}")

        # Try product page
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
                r2 = await c.get(url, headers={"User-Agent": "Mozilla/5.0"})
                print(f"Page {r2.status_code}: {url}")
                if r2.status_code == 200:
                    html = r2.text
                    m = re.search(r"SAR[\s\xa0]*([\d,]+(?:\.\d+)?)", html)
                    print(f"  SAR in page: {m.group(0) if m else 'not found'}")
                    prices = re.findall(r'"price"\s*:\s*([\d.]+)', html)
                    print(f"  price JSON values: {prices[:8]}")
        except Exception as e:
            print(f"  Page error: {e}")

asyncio.run(test())
