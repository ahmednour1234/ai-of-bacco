"""
Direct Salla storefront API test.
The API is at api.salla.dev/store/v1/ and requires the store's token.
But we can extract the token from the page's JavaScript.
"""
import httpx, re

# First, get the category page and extract the store token
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ar,en;q=0.5',
}

r = httpx.get('https://elburoj.com/ar', headers=headers, follow_redirects=True, timeout=30)
html = r.text

# Find the store token / API token in the HTML
token_patterns = [
    r'"token"\s*:\s*"([^"]+)"',
    r"'token'\s*:\s*'([^']+)'",
    r'window\.token\s*=\s*["\']([^"\']+)',
    r'Authorization["\']?\s*:\s*["\']Bearer\s+([^"\']+)',
    r'"access_token"\s*:\s*"([^"]+)"',
    r'window\.__storeToken\s*=\s*["\']([^"\']+)',
    r'"store_token"\s*:\s*"([^"]+)"',
    r'salla\.token\s*=\s*["\']([^"\']+)',
    r'"merchantToken"\s*:\s*"([^"]+)"',
    # Salla uses a specific pattern
    r'window\.salla_token\s*=\s*["\']([^"\']+)',
    r'"token":"([a-zA-Z0-9._-]{30,})"',
]

print("Looking for API token in HTML...")
for pat in token_patterns:
    m = re.search(pat, html)
    if m:
        print(f"  FOUND ({pat[:40]}): {m.group(1)[:50]}...")

# Look for api.salla.dev references
salla_api_refs = re.findall(r'api\.salla\.dev[^"\'<]{0,150}', html)
print(f"\napi.salla.dev references: {len(salla_api_refs)}")
for ref in salla_api_refs[:5]:
    print(f"  {ref[:150]}")

# Look for store ID
store_refs = re.findall(r'"store_id"\s*:\s*(\d+)', html)
print(f"\nStore IDs: {store_refs[:5]}")

merchant_refs = re.findall(r'"merchant"\s*:\s*(\d+|\{[^}]{0,100}\})', html)
print(f"Merchant refs: {merchant_refs[:3]}")

# Check for any Authorization header patterns
auth_refs = re.findall(r'Authorization[^"\'<>]{0,80}', html)
print(f"Auth refs: {auth_refs[:3]}")

# Check window variables for store info
window_vars = re.findall(r'window\.(\w+)\s*=\s*["\']([^"\']{10,100})["\']', html)
print(f"\nWindow vars:")
for k, v in window_vars[:20]:
    print(f"  window.{k} = {v[:60]}")
