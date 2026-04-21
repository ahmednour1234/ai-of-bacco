import httpx, re
HEADERS = {'User-Agent': 'Mozilla/5.0 Chrome/124', 'Accept-Language': 'en'}
r = httpx.get('https://electric-house.com/en/schneider-mcb-easy9-6000a-c-curve.html',
              headers=HEADERS, follow_redirects=True, timeout=20)
text = r.text
print('len', len(text))
m = re.search(r'"sku":"([^"]{2,50})"', text)
print('json_sku', m.group(1) if m else 'none')
idx = text.lower().find('sku')
print('context', repr(text[max(0,idx-10):idx+100]) if idx >= 0 else 'none')
# Also check for "item_number" or "part_number" patterns
for pat in [r'"item_number":"([^"]+)"', r'"part_number":"([^"]+)"',
            r'"product_number":"([^"]+)"', r'MG\.[A-Z0-9]+']:
    m2 = re.search(pat, text, re.IGNORECASE)
    if m2:
        print(f'  {pat}: {m2.group(0)[:60]}')
