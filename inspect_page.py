import httpx, sys, re

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ar,en;q=0.5',
}

url = 'https://elburoj.com/ar/%D8%A5%D9%86%D8%A7%D8%B1%D8%A9/c539403396'
r = httpx.get(url, headers=headers, follow_redirects=True, timeout=30)
html = r.text

print("HTML length:", len(html))

# Find product IDs
products = re.findall(r'/p(\d+)', html)
print('Product /p IDs found:', products[:20])

# Find JSON-LD
json_blocks = re.findall(r'application/ld\+json[^>]*>(.*?)</script>', html, re.DOTALL)
print('JSON-LD blocks:', len(json_blocks))

# Find salla-product
if 'salla-product' in html:
    idx = html.index('salla-product')
    print('salla-product found:')
    print(html[idx:idx+800])
else:
    print('No salla-product tag found')

# Find data-id
m = re.findall(r'data-id=.(\d+)', html)
print('data-id matches:', m[:10])

# Find API endpoint hints
api_hints = re.findall(r'api[^"\'<>]{0,80}product[^"\'<>]{0,80}', html)
print('API hints:', api_hints[:5])

# Search for product name patterns (Arabic text in product context)
if 'product-card' in html.lower():
    idx = html.lower().index('product-card')
    print('product-card context:')
    print(html[idx:idx+500])
