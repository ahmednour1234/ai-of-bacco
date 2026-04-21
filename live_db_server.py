"""
live_db_server.py
------------------
Live web dashboard for scraper_data.db.
Auto-refreshes every 3 seconds so you can watch the scraper fill the DB in real time.

Usage:
    .\.venv\Scripts\python live_db_server.py
Then open: http://localhost:8765
"""
import sqlite3
import json
import os
import webbrowser
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scraper_data.db")
PORT = 8765


def query_db():
    if not os.path.exists(DB_PATH):
        return {"error": "DB not found yet", "products": [], "stats": {}, "categories": [], "brands": []}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        products = conn.execute("""
            SELECT p.id, p.sku, p.name, p.price, p.source_url, p.is_synced,
                   b.name AS brand_name,
                   c.name AS category_name
            FROM scraper_products p
            LEFT JOIN scraper_brands b ON p.scraper_brand_id = b.id
            LEFT JOIN scraper_categories c ON p.scraper_category_id = c.id
            ORDER BY p.id DESC
            LIMIT 500
        """).fetchall()

        stats = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN price IS NOT NULL AND price > 0 THEN 1 ELSE 0 END) as with_price,
                SUM(CASE WHEN is_synced = 1 THEN 1 ELSE 0 END) as synced,
                COUNT(DISTINCT scraper_category_id) as categories,
                COUNT(DISTINCT scraper_brand_id) as brands
            FROM scraper_products
        """).fetchone()

        by_category = conn.execute("""
            SELECT c.name, COUNT(*) as cnt
            FROM scraper_products p
            LEFT JOIN scraper_categories c ON p.scraper_category_id = c.id
            GROUP BY c.name ORDER BY cnt DESC
        """).fetchall()

        brands = conn.execute("""
            SELECT b.name, COUNT(*) as cnt
            FROM scraper_products p
            LEFT JOIN scraper_brands b ON p.scraper_brand_id = b.id
            WHERE b.name IS NOT NULL
            GROUP BY b.name ORDER BY cnt DESC LIMIT 30
        """).fetchall()

    except Exception as e:
        conn.close()
        return {"error": str(e), "products": [], "stats": {}, "categories": [], "brands": []}

    result = {
        "stats": dict(stats) if stats else {},
        "products": [dict(p) for p in products],
        "categories": [dict(r) for r in by_category],
        "brands": [dict(r) for r in brands],
        "error": None,
    }
    conn.close()
    return result


HTML = r"""<!DOCTYPE html>
<html lang="ar" dir="ltr">
<head>
<meta charset="UTF-8">
<title>Live DB — El Buroj Scraper</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',sans-serif;background:#0d1117;color:#e0e0e0;min-height:100vh}
header{background:linear-gradient(135deg,#161b27,#1f2b50);padding:18px 28px;display:flex;align-items:center;gap:16px;border-bottom:1px solid #21283a}
header h1{font-size:1.5rem;color:#fff}
.live-dot{width:10px;height:10px;border-radius:50%;background:#22c55e;box-shadow:0 0 8px #22c55e;animation:pulse 1.2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.sub{color:#7d8590;font-size:.8rem;margin-top:2px}
.stats{display:flex;flex-wrap:wrap;gap:12px;padding:16px 28px;background:#0d1117;border-bottom:1px solid #21283a}
.stat{background:#161b27;border:1px solid #21283a;border-radius:10px;padding:14px 20px;min-width:120px;flex:1}
.stat .n{font-size:2rem;font-weight:700;color:#58a6ff}
.stat .l{color:#7d8590;font-size:.78rem;margin-top:2px}
.layout{display:grid;grid-template-columns:220px 1fr;gap:0;height:calc(100vh - 160px)}
.sidebar{background:#0d1117;border-right:1px solid #21283a;overflow-y:auto;padding:12px}
.sidebar h3{color:#7d8590;font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px;padding:0 6px}
.cat-item{padding:6px 8px;border-radius:6px;cursor:pointer;font-size:.84rem;display:flex;justify-content:space-between;align-items:center;transition:background .1s}
.cat-item:hover,.cat-item.active{background:#1c2333}
.cat-item .badge{background:#21283a;border-radius:10px;padding:1px 7px;font-size:.75rem;color:#58a6ff}
.main{overflow-y:auto;padding:0}
.toolbar{padding:10px 16px;border-bottom:1px solid #21283a;display:flex;gap:10px;align-items:center;background:#0d1117;position:sticky;top:0;z-index:10}
.toolbar input{background:#161b27;border:1px solid #21283a;color:#e0e0e0;padding:6px 12px;border-radius:6px;width:260px;font-size:.88rem}
.toolbar input:focus{outline:none;border-color:#58a6ff}
.toolbar .count{color:#7d8590;font-size:.82rem}
table{width:100%;border-collapse:collapse;font-size:.82rem}
thead th{padding:8px 10px;text-align:left;color:#7d8590;font-weight:600;border-bottom:1px solid #21283a;position:sticky;top:44px;background:#0d1117;z-index:5;white-space:nowrap}
tbody tr{border-bottom:1px solid #161b27;transition:background .1s}
tbody tr:hover{background:#161b27}
tbody td{padding:7px 10px;vertical-align:middle}
.price{font-weight:700;color:#22c55e}
.no-price{color:#484f58}
.name-ar{direction:rtl;text-align:right}
.brand-ar,.cat-ar{direction:rtl;color:#7d8590;font-size:.78rem}
a.url-link{color:#58a6ff;text-decoration:none;font-size:.8rem}
.new-row{animation:flash .8s}
@keyframes flash{0%{background:#1a3a1a}100%{background:transparent}}
.brand-list{display:flex;flex-wrap:wrap;gap:6px;padding:12px 16px}
.brand-chip{background:#161b27;border:1px solid #21283a;border-radius:20px;padding:3px 10px;font-size:.78rem;direction:rtl}
.brand-chip span{color:#58a6ff;font-weight:700}
.tabs{display:flex;gap:2px;padding:0 16px;border-bottom:1px solid #21283a;background:#0d1117;position:sticky;top:0;z-index:11}
.tab{padding:8px 16px;cursor:pointer;color:#7d8590;font-size:.84rem;border-bottom:2px solid transparent;transition:color .1s}
.tab.active{color:#58a6ff;border-bottom-color:#58a6ff}
#status-bar{position:fixed;bottom:0;left:0;right:0;background:#161b27;border-top:1px solid #21283a;padding:4px 16px;font-size:.75rem;color:#7d8590;display:flex;gap:16px}
</style>
</head>
<body>
<header>
  <div class="live-dot"></div>
  <div>
    <h1>🗄️ El Buroj — Live Scraper Dashboard</h1>
    <div class="sub">Auto-refreshes every 3s · <span id="last-update">—</span></div>
  </div>
</header>

<div class="stats" id="stats-bar">
  <div class="stat"><div class="n" id="s-total">—</div><div class="l">Total Products</div></div>
  <div class="stat"><div class="n" id="s-price">—</div><div class="l">With Price</div></div>
  <div class="stat"><div class="n" id="s-cats">—</div><div class="l">Categories</div></div>
  <div class="stat"><div class="n" id="s-brands">—</div><div class="l">Brands</div></div>
  <div class="stat"><div class="n" id="s-synced">—</div><div class="l">Synced</div></div>
</div>

<div class="layout">
  <!-- Sidebar: categories -->
  <div class="sidebar">
    <h3>Categories</h3>
    <div id="cat-list"></div>
  </div>

  <!-- Main panel -->
  <div class="main">
    <div class="tabs">
      <div class="tab active" onclick="showTab('products',this)">Products</div>
      <div class="tab" onclick="showTab('brands',this)">Brands</div>
    </div>

    <div id="tab-products">
      <div class="toolbar">
        <input type="text" id="search" placeholder="Search name, SKU, brand..." oninput="applyFilter()">
        <span class="count" id="shown-count"></span>
      </div>
      <table id="ptable">
        <thead>
          <tr>
            <th>#</th>
            <th>Name</th>
            <th>SKU</th>
            <th>Price (SAR)</th>
            <th>Brand</th>
            <th>Category</th>
            <th>URL</th>
          </tr>
        </thead>
        <tbody id="tbody"></tbody>
      </table>
    </div>

    <div id="tab-brands" style="display:none">
      <div class="brand-list" id="brand-list"></div>
    </div>
  </div>
</div>

<div id="status-bar">
  <span id="sb-fetch">Connecting...</span>
  <span id="sb-rows">—</span>
</div>

<script>
let allProducts = [];
let activeCategory = null;
let knownIds = new Set();

function esc(s){ return s==null?'':(s+'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function showTab(name, el){
  document.getElementById('tab-products').style.display = name==='products'?'':'none';
  document.getElementById('tab-brands').style.display   = name==='brands'?'':'none';
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
}

function applyFilter(){
  const q = document.getElementById('search').value.toLowerCase();
  const rows = document.querySelectorAll('#tbody tr');
  let shown = 0;
  rows.forEach(r=>{
    const catMatch = activeCategory===null || r.dataset.cat===activeCategory;
    const textMatch = !q || r.dataset.text.includes(q);
    const vis = catMatch && textMatch;
    r.style.display = vis ? '' : 'none';
    if(vis) shown++;
  });
  document.getElementById('shown-count').textContent = shown + ' products shown';
}

function setCategory(name){
  activeCategory = name;
  document.querySelectorAll('.cat-item').forEach(el=>{
    el.classList.toggle('active', el.dataset.cat===name);
  });
  applyFilter();
}

async function refresh(){
  try {
    const res = await fetch('/api/data');
    const data = await res.json();

    if(data.error){ document.getElementById('sb-fetch').textContent='⚠ '+data.error; return; }

    const s = data.stats;
    document.getElementById('s-total').textContent  = s.total||0;
    document.getElementById('s-price').textContent  = s.with_price||0;
    document.getElementById('s-cats').textContent   = s.categories||0;
    document.getElementById('s-brands').textContent = s.brands||0;
    document.getElementById('s-synced').textContent = s.synced||0;

    // Categories sidebar
    const catList = document.getElementById('cat-list');
    const oldCatHtml = catList.innerHTML;
    const newCatHtml = ['<div class="cat-item'+(activeCategory===null?' active':'')+'" data-cat="" onclick="setCategory(null)"><span>All</span><span class="badge">'+(s.total||0)+'</span></div>',
      ...data.categories.map(c=>`<div class="cat-item${activeCategory===c.name?' active':''}" data-cat="${esc(c.name)}" onclick="setCategory('${esc(c.name)}')" style="direction:rtl"><span>${esc(c.name)}</span><span class="badge">${c.cnt}</span></div>`)
    ].join('');
    if(newCatHtml !== oldCatHtml) catList.innerHTML = newCatHtml;

    // Products table — only add new rows, don't rebuild
    const tbody = document.getElementById('tbody');
    const newProducts = data.products.filter(p=>!knownIds.has(p.id));
    newProducts.forEach(p=>{
      knownIds.add(p.id);
      allProducts.unshift(p);
      const tr = document.createElement('tr');
      tr.className = 'new-row';
      tr.dataset.cat = p.category_name||'';
      tr.dataset.text = [(p.name||''),(p.sku||''),(p.brand_name||''),(p.category_name||'')].join(' ').toLowerCase();
      const price = p.price&&p.price>0
        ? `<span class="price">${parseFloat(p.price).toFixed(2)}</span>`
        : `<span class="no-price">—</span>`;
      const url = p.source_url ? `<a class="url-link" href="${esc(p.source_url)}" target="_blank">🔗</a>` : '';
      tr.innerHTML = `
        <td>${esc(p.id)}</td>
        <td class="name-ar">${esc(p.name)}</td>
        <td>${esc(p.sku)}</td>
        <td>${price}</td>
        <td class="brand-ar">${esc(p.brand_name)}</td>
        <td class="cat-ar">${esc(p.category_name)}</td>
        <td>${url}</td>`;
      tbody.prepend(tr);
    });

    // Brands tab
    const brandList = document.getElementById('brand-list');
    brandList.innerHTML = data.brands.map(b=>
      `<div class="brand-chip">${esc(b.name)} <span>${b.cnt}</span></div>`
    ).join('');

    applyFilter();

    const total = tbody.querySelectorAll('tr').length;
    document.getElementById('sb-rows').textContent = total + ' rows in table';
    document.getElementById('sb-fetch').textContent = '✓ Live · ' + new Date().toLocaleTimeString();
    document.getElementById('last-update').textContent = new Date().toLocaleTimeString();

  } catch(e){
    document.getElementById('sb-fetch').textContent = '✗ ' + e.message;
  }
}

refresh();
setInterval(refresh, 3000);
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress access logs

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML.encode("utf-8"))

        elif self.path == "/api/data":
            data = query_db()
            body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)

        else:
            self.send_response(404)
            self.end_headers()


def open_browser():
    import time
    time.sleep(1)
    webbrowser.open(f"http://localhost:{PORT}")


if __name__ == "__main__":
    print(f"Starting live dashboard on http://localhost:{PORT}")
    print(f"Watching: {DB_PATH}")
    print("Press Ctrl+C to stop.\n")
    threading.Thread(target=open_browser, daemon=True).start()
    server = HTTPServer(("localhost", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
