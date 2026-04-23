import sqlite3, asyncio, httpx, re, json

c = sqlite3.connect('scraper_data.db')
rows = c.execute("SELECT p.source_url, p.raw_data FROM scraper_products p JOIN scraper_sources s ON p.source_id=s.id WHERE s.name='Zorins Technologies' AND (p.price IS NULL OR p.price=0) LIMIT 3").fetchall()
c.close()

async def test():
    for url, raw in rows:
        print("URL:", url)
        raw_j = json.loads(raw or '{}')
        print("  raw price:", raw_j.get('price'), '| regular_price:', raw_j.get('regular_price'))
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as cl:
                r = await cl.get(url, headers={"User-Agent": "Mozilla/5.0 Chrome/124"})
                print("  HTTP:", r.status_code)
                if r.status_code == 200:
                    m = re.search(r'SAR[\s\xa0]*([\d,]+(?:\.\d+)?)', r.text)
                    print("  SAR:", m.group(0) if m else "not found")
                    prices = re.findall(r'"price"\s*:\s*"?([0-9.]+)"?', r.text)
                    print("  price hits:", prices[:5])
        except Exception as e:
            print("  Error:", e)
        print()

asyncio.run(test())
