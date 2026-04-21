import httpx, asyncio, json

async def main():
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 Chrome/124",
        "Accept": "application/json, text/plain, */*",
    }

    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as c:
        # ── Magento 2 GraphQL ──────────────────────────────────────────
        print("Testing GraphQL...")
        gql_url = "https://eshop.se.com/sa/graphql"
        query = """{ products(search: "", pageSize: 5, currentPage: 1) {
            total_count
            items { id name sku
                price_range { minimum_price { final_price { value currency } } }
            }
        }}"""
        r = await c.post(gql_url, json={"query": query}, headers=headers)
        print("  Status:", r.status_code, " | body length:", len(r.text))
        if r.status_code == 200:
            data = r.json()
            print("  Keys:", list(data.keys()))
            print(json.dumps(data, indent=2)[:2000])
        else:
            print("  Response:", r.text[:300])

        # ── REST API ───────────────────────────────────────────────────
        print("\nTesting REST V1 products...")
        rest_url = "https://eshop.se.com/sa/rest/V1/products"
        params = {
            "searchCriteria[pageSize]": "5",
            "searchCriteria[currentPage]": "1",
            "searchCriteria[filter_groups][0][filters][0][field]": "status",
            "searchCriteria[filter_groups][0][filters][0][value]": "1",
            "searchCriteria[filter_groups][0][filters][0][condition_type]": "eq",
            "fields": "items[id,sku,name,price,status]",
        }
        r2 = await c.get(rest_url, params=params, headers=headers)
        print("  Status:", r2.status_code, " | body length:", len(r2.text))
        if r2.status_code == 200:
            print(r2.text[:1500])
        else:
            print("  Response:", r2.text[:300])

asyncio.run(main())
