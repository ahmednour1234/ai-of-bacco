"""Try newer Salla storefront API formats."""
import httpx, json

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Accept-Language': 'ar,en;q=0.5',
    'Referer': 'https://elburoj.com/ar/كهرباء/c931950675',
}

# Try a category with actual products - كهرباء c931950675
endpoints = [
    # Salla v2 storefront 
    'https://elburoj.com/api/storefront/products?category_id=931950675',
    'https://elburoj.com/api/storefront/products?filters[category_id]=931950675',
    # Salla newer endpoints
    'https://elburoj.com/api/v1/products?category_id=931950675',
    'https://elburoj.com/api/store/products?category_id=931950675',
    # Category page with JSON accept
    'https://elburoj.com/ar/كهرباء/c931950675',
    # Salla product-card CDN data endpoint
    'https://elburoj.com/ar/كهرباء/c931950675?layout=list',
]

for ep in endpoints:
    try:
        h = dict(headers)
        if not ep.endswith('.com'):
            pass
        resp = httpx.get(ep, headers=h, follow_redirects=True, timeout=15)
        ct = resp.headers.get('content-type', '')
        print(f"\nGET ...{ep[-60:]}")
        print(f"  Status: {resp.status_code}  CT: {ct[:50]}")
        body = resp.text[:300]
        if 'product' in body.lower() or 'data-id' in body.lower():
            print(f"  ** PRODUCTS FOUND IN RESPONSE **")
            print(f"  Body: {body}")
        else:
            print(f"  Body: {body[:150]}")
    except Exception as e:
        print(f"  ERROR: {e}")

# Try the storefront product listing endpoint  
print("\n\n--- Salla Storefront Internal API ---")
# Salla uses a specific storefront component API
storefront_headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
    'Referer': 'https://elburoj.com/',
}
api_tests = [
    'https://elburoj.com/api/product/list?category_id=931950675&page=1&per_page=20&include=options',
    'https://elburoj.com/store/api/products?category_id=931950675',
    'https://store.salla.sa/api/products?store=elburoj&category_id=931950675',
]
for ep in api_tests:
    try:
        resp = httpx.get(ep, headers=storefront_headers, follow_redirects=True, timeout=10)
        print(f"\nGET {ep[-70:]}")
        print(f"  {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"  ERROR: {e}")
