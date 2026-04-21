"""Find products by getting a session first and using the storefront products endpoint."""
import httpx, re, json

# Create a persistent client to maintain session cookies
with httpx.Client(follow_redirects=True, timeout=30) as client:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'ar,en;q=0.5',
    }
    
    # First get the homepage to get cookies/session
    r = client.get('https://elburoj.com/ar', headers=headers)
    print("Homepage:", r.status_code, len(r.text), "bytes")
    print("Cookies:", dict(client.cookies))
    
    # Now try the products endpoint
    api_headers = dict(headers)
    api_headers['Accept'] = 'application/json'
    api_headers['Referer'] = 'https://elburoj.com/ar'
    
    # Try different category IDs from the homepage
    cat_ids = ['931950675', '413920175', '1245853323', '62458249']
    
    for cat_id in cat_ids:
        r2 = client.get(
            f'https://elburoj.com/products?category_id={cat_id}&page=1&per_page=20',
            headers=api_headers
        )
        print(f"\nCategory {cat_id}: {r2.status_code}")
        body = r2.text
        if r2.status_code == 200:
            try:
                data = r2.json()
                print("JSON:", json.dumps(data, ensure_ascii=False)[:500])
            except:
                print("HTML:", body[:300])
        else:
            # Extract error message
            try:
                err = r2.json()
                msg = err.get('error', {}).get('message', '')
                print("Error:", msg)
            except:
                print("Body:", body[:200])
    
    # Try without category filter
    r3 = client.get('https://elburoj.com/products?page=1&per_page=20', headers=api_headers)
    print(f"\nAll products: {r3.status_code}")
    if r3.status_code == 200:
        try:
            d = r3.json()
            print(json.dumps(d, ensure_ascii=False)[:1000])
        except:
            print(r3.text[:500])
