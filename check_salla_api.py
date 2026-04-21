"""Check Salla storefront API endpoints for El Buroj store."""
import httpx, json

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ar,en;q=0.5',
    'Referer': 'https://elburoj.com/',
    'X-Requested-With': 'XMLHttpRequest',
}

base = 'https://elburoj.com'

# Try Salla storefront API v2 endpoints
endpoints = [
    '/api/product/list?category_id=539403396&page=1&per_page=20',
    '/api/products?category_id=539403396&page=1',
    '/ar/api/product/list?category_id=539403396',
    '/api/v2/products?category_id=539403396',
    '/ar/إنارة/c539403396?format=json',
    '/api/product/list?filters[category_id]=539403396',
]

for ep in endpoints:
    try:
        r = httpx.get(base + ep, headers=headers, follow_redirects=True, timeout=10)
        ct = r.headers.get('content-type', '')
        body = r.text[:200]
        print(f"\nGET {ep}")
        print(f"  Status: {r.status_code}  Content-Type: {ct}")
        print(f"  Body: {body}")
    except Exception as e:
        print(f"\nGET {ep}  ERROR: {e}")
