import httpx, json

url_key = "schneider-mcb-easy9-6000a-c-curve"
query = """
{
  products(filter: {url_key: {eq: "%s"}}) {
    items {
      sku
      name
    }
  }
}
""" % url_key

r = httpx.post(
    'https://electric-house.com/graphql',
    json={'query': query},
    headers={
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 Chrome/124',
        'Store': 'en',
    },
    timeout=15,
)
print('status:', r.status_code)
print(r.text[:1000])
