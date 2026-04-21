"""Try the Salla storefront graphql or newer REST API."""
import httpx

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
    'Referer': 'https://elburoj.com/',
}

# Encode Arabic URLs properly
from urllib.parse import quote

cat_slug = quote('كهرباء')
cat_id = '931950675'

tests = [
    f'https://elburoj.com/api/storefront/v1/products?category_id={cat_id}',
    f'https://elburoj.com/ar/{cat_slug}/c{cat_id}?page=1',
    f'https://elburoj.com/products?category_id={cat_id}&page=1&per_page=20',
    f'https://elburoj.com/api/category/{cat_id}/products',
]

for ep in tests:
    try:
        resp = httpx.get(ep, headers=headers, follow_redirects=True, timeout=15)
        ct = resp.headers.get('content-type','')
        body = resp.text
        has_prod = any(k in body for k in ['product', 'sku', 'price', 'data-id'])
        print(f"\n{resp.status_code} {ct[:40]} | has_product_data={has_prod}")
        print(f"URL: {ep[-60:]}")
        if has_prod:
            print("BODY:", body[:500])
        else:
            print("BODY:", body[:200])
    except Exception as e:
        print(f"ERROR {ep[-50:]}: {e}")

# Check what JavaScript loads the products
print("\n\n--- Checking product-card.js source ---")
try:
    r = httpx.get('https://cdn.assets.salla.network/themes/581928698/1.172.0/product-card.js', 
                  timeout=15)
    # Find API endpoint in the JS
    import re
    api_urls = re.findall(r'["\'](/api/[^"\']{5,60})["\']', r.text)
    print("API endpoints in product-card.js:", api_urls[:20])
    # Also search for "products" related
    prod_related = re.findall(r'["\']([^"\']*product[^"\']{0,50})["\']', r.text)
    print("Product related strings:", prod_related[:20])
except Exception as e:
    print(f"ERROR: {e}")
