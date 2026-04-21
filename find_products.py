"""Find active categories on El Buroj and their product APIs."""
import httpx, re, json

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ar,en;q=0.5',
}

# First get homepage to find categories and products
r = httpx.get('https://elburoj.com/ar', headers=headers, follow_redirects=True, timeout=30)
html = r.text
print("Homepage HTML length:", len(html))

# Find category links
cats = re.findall(r'href=["\']([^"\']*?/c\d+)["\']', html)
print("\nCategory URLs found:", cats[:20])

# Look for product links in JSON data embedded in page
json_matches = re.findall(r'"products"\s*:\s*\[.*?\]', html[:50000], re.DOTALL)
print("\nJSON product arrays:", len(json_matches))

# Look for Salla product card data
pc_data = re.findall(r'salla-product-card[^>]*>', html)
print("\nProduct card elements:", len(pc_data))
if pc_data:
    for p in pc_data[:3]:
        print(" ", p[:200])

# Try Salla's storefront products API 
print("\n--- Trying Salla API ---")
api_headers = dict(headers)
api_headers['Accept'] = 'application/json'

# Known working Salla storefront endpoint
endpoints = [
    'https://elburoj.com/api/product/list?page=1&per_page=20',
    'https://elburoj.com/api/products/list',
    'https://elburoj.com/api/category/list',
    'https://elburoj.com/api/categories',
]
for ep in endpoints:
    try:
        resp = httpx.get(ep, headers=api_headers, follow_redirects=True, timeout=10)
        print(f"GET {ep.split('elburoj.com')[1]} -> {resp.status_code} {resp.headers.get('content-type','')[:40]}")
        if resp.status_code == 200 and 'json' in resp.headers.get('content-type',''):
            print("  BODY:", resp.text[:300])
    except Exception as e:
        print(f"  ERROR: {e}")
