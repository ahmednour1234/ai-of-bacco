import sqlite3
import os

DB_PATH = "scraper_data.db"
OUTPUT_PATH = "db_viewer.html"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# Fetch data
products = conn.execute("""
    SELECT 
        p.id, p.external_id, p.sku, p.name, p.price,
        p.source_url, p.is_synced, p.last_scraped_at,
        b.name AS brand_name,
        c.name AS category_name,
        s.name AS source_name,
        p.created_at
    FROM scraper_products p
    LEFT JOIN scraper_brands b ON p.scraper_brand_id = b.id
    LEFT JOIN scraper_categories c ON p.scraper_category_id = c.id
    LEFT JOIN scraper_sources s ON p.source_id = s.id
    ORDER BY p.id
""").fetchall()

brands = conn.execute("SELECT * FROM scraper_brands ORDER BY name").fetchall()
categories = conn.execute("SELECT * FROM scraper_categories ORDER BY name").fetchall()
sources = conn.execute("SELECT * FROM scraper_sources").fetchall()
sync_logs = conn.execute("SELECT * FROM scraper_sync_logs ORDER BY id DESC LIMIT 20").fetchall()
conn.close()

def esc(v):
    if v is None:
        return ""
    return str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

product_rows = ""
for p in products:
    url = f'<a href="{esc(p["source_url"])}" target="_blank" style="color:#4f8ef7;">🔗</a>' if p["source_url"] else ""
    synced = '<span class="badge green">✓</span>' if p["is_synced"] else '<span class="badge yellow">pending</span>'
    price = f'<strong>{float(p["price"]):.2f}</strong> SAR' if p["price"] else "—"
    product_rows += f"""
    <tr>
        <td>{esc(p["id"])}</td>
        <td style="direction:rtl;text-align:right">{esc(p["name"])}</td>
        <td>{esc(p["sku"])}</td>
        <td>{price}</td>
        <td style="direction:rtl">{esc(p["brand_name"])}</td>
        <td style="direction:rtl">{esc(p["category_name"])}</td>
        <td>{synced}</td>
        <td>{url}</td>
    </tr>"""

brand_rows = ""
for b in brands:
    brand_rows += f"<tr><td>{esc(b['id'])}</td><td style='direction:rtl'>{esc(b['name'])}</td><td>{esc(b['external_id'])}</td></tr>"

category_rows = ""
for c in categories:
    url_link = f'<a href="{esc(c["url"])}" target="_blank">🔗</a>' if c["url"] else ""
    category_rows += f"<tr><td>{esc(c['id'])}</td><td style='direction:rtl'>{esc(c['name'])}</td><td>{url_link}</td></tr>"

source_rows = ""
for s in sources:
    source_rows += f"<tr><td>{esc(s['id'])}</td><td>{esc(s['name'])}</td><td>{esc(s['base_url'])}</td><td>{esc(s['active'])}</td></tr>"

sync_rows = ""
for sl in sync_logs:
    status_cls = "green" if sl["sync_status"] == "success" else ("red" if sl["sync_status"] == "failed" else "yellow")
    sync_rows += f"<tr><td>{esc(sl['id'])}</td><td>{esc(sl['scraper_product_id'])}</td><td><span class='badge {status_cls}'>{esc(sl['sync_status'])}</span></td><td>{esc(sl['synced_at'])}</td><td>{esc(sl['created_at'])}</td></tr>"

html = f"""<!DOCTYPE html>
<html lang="ar" dir="ltr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Scraper Database Viewer</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Tahoma, Arial, sans-serif; background: #0f1117; color: #e0e0e0; }}
  header {{ background: linear-gradient(135deg, #1a1f2e, #2d3561); padding: 24px 32px; border-bottom: 1px solid #2a2f4a; }}
  header h1 {{ font-size: 1.8rem; color: #fff; }}
  header p {{ color: #8892b0; margin-top: 4px; }}
  .stats {{ display: flex; gap: 16px; padding: 20px 32px; flex-wrap: wrap; }}
  .stat {{ background: #1a1f2e; border: 1px solid #2a2f4a; border-radius: 10px; padding: 16px 24px; flex: 1; min-width: 140px; }}
  .stat .num {{ font-size: 2rem; font-weight: 700; color: #4f8ef7; }}
  .stat .lbl {{ color: #8892b0; font-size: 0.85rem; margin-top: 2px; }}
  .tabs {{ display: flex; gap: 4px; padding: 0 32px; border-bottom: 1px solid #2a2f4a; }}
  .tab {{ padding: 10px 20px; cursor: pointer; border-radius: 8px 8px 0 0; color: #8892b0; user-select: none; }}
  .tab.active {{ background: #1a1f2e; color: #fff; border: 1px solid #2a2f4a; border-bottom: 1px solid #1a1f2e; }}
  .tab:hover:not(.active) {{ color: #ccc; }}
  .panel {{ display: none; padding: 24px 32px; }}
  .panel.active {{ display: block; }}
  .search-bar {{ margin-bottom: 16px; }}
  .search-bar input {{ background: #1a1f2e; border: 1px solid #2a2f4a; color: #e0e0e0; padding: 8px 14px; border-radius: 6px; width: 340px; font-size: 0.95rem; }}
  .search-bar input:focus {{ outline: none; border-color: #4f8ef7; }}
  .table-wrap {{ overflow-x: auto; border-radius: 10px; border: 1px solid #2a2f4a; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
  thead tr {{ background: #1a1f2e; }}
  thead th {{ padding: 10px 12px; text-align: left; color: #8892b0; font-weight: 600; border-bottom: 1px solid #2a2f4a; white-space: nowrap; }}
  tbody tr {{ border-bottom: 1px solid #1e2436; transition: background 0.1s; }}
  tbody tr:hover {{ background: #1a2035; }}
  tbody td {{ padding: 8px 12px; vertical-align: middle; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.78rem; font-weight: 600; }}
  .badge.green {{ background: #0d3327; color: #4caf82; }}
  .badge.red {{ background: #3a1020; color: #e05060; }}
  .badge.yellow {{ background: #332900; color: #e0b040; }}
  a {{ color: #4f8ef7; text-decoration: none; }}
</style>
</head>
<body>
<header>
  <h1>🗄️ Scraper Database Viewer</h1>
  <p>SQLite · scraper_data.db · Generated {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
</header>

<div class="stats">
  <div class="stat"><div class="num">{len(products)}</div><div class="lbl">Products</div></div>
  <div class="stat"><div class="num">{len(brands)}</div><div class="lbl">Brands</div></div>
  <div class="stat"><div class="num">{len(categories)}</div><div class="lbl">Categories</div></div>
  <div class="stat"><div class="num">{len(sources)}</div><div class="lbl">Sources</div></div>
  <div class="stat"><div class="num">{sum(1 for p in products if p['price'])}</div><div class="lbl">With Price</div></div>
  <div class="stat"><div class="num">{sum(1 for p in products if p['is_synced'])}</div><div class="lbl">Synced</div></div>
</div>

<div class="tabs">
  <div class="tab active" onclick="showTab('products', this)">Products ({len(products)})</div>
  <div class="tab" onclick="showTab('brands', this)">Brands ({len(brands)})</div>
  <div class="tab" onclick="showTab('categories', this)">Categories ({len(categories)})</div>
  <div class="tab" onclick="showTab('sources', this)">Sources ({len(sources)})</div>
  <div class="tab" onclick="showTab('synclogs', this)">Sync Logs ({len(sync_logs)})</div>
</div>

<div id="products" class="panel active">
  <div class="search-bar"><input type="text" id="productSearch" placeholder="Search products (name, SKU, brand)..." oninput="filterTable('productSearch','productTable')"></div>
  <div class="table-wrap">
  <table id="productTable">
    <thead><tr>
      <th>#</th><th>Name</th><th>SKU</th><th>Price</th><th>Brand</th><th>Category</th><th>Synced</th><th>URL</th>
    </tr></thead>
    <tbody>{product_rows}</tbody>
  </table>
  </div>
</div>

<div id="brands" class="panel">
  <div class="table-wrap">
  <table>
    <thead><tr><th>ID</th><th>Name</th><th>External ID</th></tr></thead>
    <tbody>{brand_rows}</tbody>
  </table>
  </div>
</div>

<div id="categories" class="panel">
  <div class="table-wrap">
  <table>
    <thead><tr><th>ID</th><th>Name</th><th>URL</th></tr></thead>
    <tbody>{category_rows}</tbody>
  </table>
  </div>
</div>

<div id="sources" class="panel">
  <div class="table-wrap">
  <table>
    <thead><tr><th>ID</th><th>Name</th><th>Base URL</th><th>Active</th></tr></thead>
    <tbody>{source_rows}</tbody>
  </table>
  </div>
</div>

<div id="synclogs" class="panel">
  <div class="table-wrap">
  <table>
    <thead><tr><th>ID</th><th>Product ID</th><th>Status</th><th>Synced At</th><th>Created At</th></tr></thead>
    <tbody>{sync_rows}</tbody>
  </table>
  </div>
</div>

<script>
function showTab(id, el) {{
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  el.classList.add('active');
}}
function filterTable(inputId, tableId) {{
  const q = document.getElementById(inputId).value.toLowerCase();
  const rows = document.getElementById(tableId).querySelectorAll('tbody tr');
  rows.forEach(row => {{
    row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
  }});
}}
</script>
</body>
</html>"""

with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Generated: {os.path.abspath(OUTPUT_PATH)}")
print(f"Products: {len(products)}, Brands: {len(brands)}, Categories: {len(categories)}")

# Auto-open in browser
import webbrowser
webbrowser.open(f"file:///{os.path.abspath(OUTPUT_PATH).replace(chr(92), '/')}")
print("Opened in browser.")
