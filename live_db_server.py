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
import sys
import subprocess
import webbrowser
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- Scraper process state (keyed by scraper name) ---
_SCRAPERS = {
    "elburoj":        "scrape_all_elburoj.py",
    "electric-house":  "scrape_electric_house.py",
    "janoubco":        "scrape_janoubco.py",
    "microless":       "scrape_microless.py",
    "mejdaf":          "scrape_mejdaf.py",
    "baytalebaa":      "scrape_baytalebaa.py",
}
_scraper_procs: dict[str, object] = {}
_scraper_logs:  dict[str, list]   = {k: [] for k in _SCRAPERS}
_scraper_lock = threading.Lock()

_refetch_proc   = None
_refetch_log:   list  = []
_refetch_lock   = threading.Lock()

def _refetch_status() -> str:
    with _refetch_lock:
        if _refetch_proc is None:
            return "idle"
        ret = _refetch_proc.poll()
        if ret is None:
            return "running"
        return "done" if ret == 0 else f"error:{ret}"

def _collect_refetch_output(proc):
    global _refetch_log
    for raw in proc.stdout:
        line = raw.decode("utf-8", errors="replace").rstrip()
        with _refetch_lock:
            _refetch_log.append(line)
            if len(_refetch_log) > 500:
                _refetch_log = _refetch_log[-500:]

def _run_price_refetch():
    global _refetch_proc, _refetch_log
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fix_missing_prices.py")
    with _refetch_lock:
        if _refetch_proc is not None and _refetch_proc.poll() is None:
            return
        _refetch_log = []
        env = os.environ.copy()
        new_proc = subprocess.Popen(
            [sys.executable, script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        _refetch_proc = new_proc
    threading.Thread(target=_collect_refetch_output, args=(new_proc,), daemon=True).start()

def _scraper_status(name: str = "elburoj") -> str:
    with _scraper_lock:
        proc = _scraper_procs.get(name)
        if proc is None:
            return "idle"
        ret = proc.poll()
        if ret is None:
            return "running"
        return "done" if ret == 0 else f"error:{ret}"

def _collect_output(name: str, proc):
    for raw in proc.stdout:
        line = raw.decode("utf-8", errors="replace").rstrip()
        with _scraper_lock:
            _scraper_logs[name].append(line)
            if len(_scraper_logs[name]) > 500:
                _scraper_logs[name] = _scraper_logs[name][-500:]

def _run_scraper(name: str = "elburoj"):
    script_file = _SCRAPERS.get(name)
    if not script_file:
        return
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), script_file)
    with _scraper_lock:
        proc = _scraper_procs.get(name)
        if proc is not None and proc.poll() is None:
            return  # already running
        _scraper_logs[name] = []
        env = os.environ.copy()
        new_proc = subprocess.Popen(
            [sys.executable, script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        _scraper_procs[name] = new_proc
    threading.Thread(target=_collect_output, args=(name, new_proc), daemon=True).start()

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scraper_data.db")
PORT = 8765


def query_price_stats():
    """Return per-source price coverage stats."""
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT
                s.name AS source,
                COUNT(*) AS total,
                SUM(CASE WHEN p.price IS NOT NULL AND p.price > 0 THEN 1 ELSE 0 END) AS with_price,
                SUM(CASE WHEN p.price IS NULL OR p.price = 0 THEN 1 ELSE 0 END) AS no_price,
                ROUND(100.0 * SUM(CASE WHEN p.price IS NOT NULL AND p.price > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct,
                ROUND(MIN(CASE WHEN p.price > 0 THEN p.price END), 2) AS min_price,
                ROUND(MAX(CASE WHEN p.price > 0 THEN p.price END), 2) AS max_price,
                ROUND(AVG(CASE WHEN p.price > 0 THEN p.price END), 2) AS avg_price
            FROM scraper_products p
            LEFT JOIN scraper_sources s ON p.source_id = s.id
            GROUP BY s.name
            ORDER BY total DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def query_db():
    if not os.path.exists(DB_PATH):
        return {"error": "DB not found yet", "products": [], "stats": {}, "categories": [], "brands": []}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        products = conn.execute("""
            SELECT p.id, p.sku, p.name, p.price, p.source_url, p.is_synced,
                   b.name AS brand_name,
                   c.name AS category_name,
                   s.name AS source_name
            FROM scraper_products p
            LEFT JOIN scraper_brands b ON p.scraper_brand_id = b.id
            LEFT JOIN scraper_categories c ON p.scraper_category_id = c.id
            LEFT JOIN scraper_sources s ON p.source_id = s.id
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
.filter-btn{background:#161b27;border:1px solid #21283a;color:#7d8590;padding:5px 12px;border-radius:6px;font-size:.82rem;cursor:pointer;transition:all .1s}
.filter-btn.active{background:#1c2333;border-color:#58a6ff;color:#58a6ff}
.filter-btn:hover{background:#1c2333}
.pc-table{width:100%;border-collapse:collapse;font-size:.86rem;margin-top:8px}
.pc-table th{padding:10px 14px;text-align:left;color:#7d8590;font-weight:600;border-bottom:2px solid #21283a}
.pc-table td{padding:10px 14px;border-bottom:1px solid #161b27}
.pc-table tr:hover td{background:#161b27}
.pc-bar{height:10px;border-radius:5px;background:#21283a;overflow:hidden;min-width:120px}
.pc-fill{height:100%;background:#22c55e;transition:width .4s}
.pc-fill.low{background:#f85149}
.pc-fill.mid{background:#f59e0b}
.bad-name{color:#f85149;font-style:italic}
.source-badge{font-size:.72rem;background:#1c2333;border:1px solid #21283a;border-radius:10px;padding:1px 7px;color:#7d8590}
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
    <h1>🗄️ Live Scraper Dashboard</h1>
    <div class="sub">Auto-refreshes every 3s · <span id="last-update">—</span></div>
  </div>
  <div style="margin-left:auto;display:flex;align-items:center;gap:10px;flex-wrap:wrap">
    <span id="scraper-status" style="font-size:.8rem;color:#7d8590"></span>
    <button id="run-btn-elburoj" onclick="runScraper('elburoj',this)"
      style="background:#3b82f6;color:#fff;border:none;padding:8px 16px;border-radius:8px;font-size:.83rem;font-weight:700;cursor:pointer">
      ▶ El Buroj
    </button>
    <button id="run-btn-electric-house" onclick="runScraper('electric-house',this)"
      style="background:#22c55e;color:#000;border:none;padding:8px 16px;border-radius:8px;font-size:.83rem;font-weight:700;cursor:pointer">
      ▶ Electric House
    </button>
    <button id="run-btn-janoubco" onclick="runScraper('janoubco',this)"
      style="background:#a855f7;color:#fff;border:none;padding:8px 16px;border-radius:8px;font-size:.83rem;font-weight:700;cursor:pointer">
      ▶ Janoubco
    </button>
    <button id="run-btn-microless" onclick="runScraper('microless',this)"
      style="background:#0ea5e9;color:#fff;border:none;padding:8px 16px;border-radius:8px;font-size:.83rem;font-weight:700;cursor:pointer">
      ▶ Microless
    </button>
    <button id="run-btn-mejdaf" onclick="runScraper('mejdaf',this)"
      style="background:#f97316;color:#fff;border:none;padding:8px 16px;border-radius:8px;font-size:.83rem;font-weight:700;cursor:pointer">
      ▶ Mejdaf
    </button>
    <button id="run-btn-baytalebaa" onclick="runScraper('baytalebaa',this)"
      style="background:#10b981;color:#fff;border:none;padding:8px 16px;border-radius:8px;font-size:.83rem;font-weight:700;cursor:pointer">
      ▶ Baytalebaa
    </button>
    <button id="refetch-btn" onclick="refetchPrices(this)"
      style="background:#8b5cf6;color:#fff;border:none;padding:8px 16px;border-radius:8px;font-size:.83rem;font-weight:700;cursor:pointer">
      ↺ Refetch Prices
    </button>
    <button onclick="window.open('/api/export','_blank')"
      style="background:#64748b;color:#fff;border:none;padding:8px 16px;border-radius:8px;font-size:.83rem;font-weight:700;cursor:pointer">
      ⬇ Export JSON
    </button>
    <button id="run-btn-all" onclick="runAll(this)"
      style="background:#f59e0b;color:#000;border:none;padding:8px 16px;border-radius:8px;font-size:.83rem;font-weight:700;cursor:pointer">
      ▶ Run All
    </button>
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
      <div class="tab" onclick="showTab('price-check',this)">💰 Price Check</div>
    </div>

    <div id="tab-products">
      <div class="toolbar">
        <input type="text" id="search" placeholder="Search name, SKU, brand..." oninput="applyFilter()">
        <button class="filter-btn active" id="f-all"     onclick="setPriceFilter('all',this)">All</button>
        <button class="filter-btn"        id="f-priced"  onclick="setPriceFilter('priced',this)">✓ Has Price</button>
        <button class="filter-btn"        id="f-noPrice" onclick="setPriceFilter('noPrice',this)">✗ No Price</button>
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
            <th>Source</th>
            <th>URL</th>
          </tr>
        </thead>
        <tbody id="tbody"></tbody>
      </table>
    </div>

    <div id="tab-brands" style="display:none">
      <div class="brand-list" id="brand-list"></div>
    </div>

    <div id="tab-price-check" style="display:none;padding:20px">
      <h2 style="color:#58a6ff;margin-bottom:16px;font-size:1.1rem">💰 Price Coverage by Scraper</h2>
      <div id="price-check-content" style="color:#7d8590">Loading...</div>
      <pre id="refetch-log" style="display:none;margin-top:16px;padding:12px;background:#0d1117;border:1px solid #21283a;border-radius:8px;font-size:.78rem;color:#22c55e;max-height:260px;overflow-y:auto;white-space:pre-wrap"></pre>
    </div>
  </div>
</div>

<div id="log-section" style="display:none;padding:12px 28px;background:#0d1117;border-top:1px solid #21283a">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
    <span style="color:#7d8590;font-size:.78rem;text-transform:uppercase;letter-spacing:.06em">Scraper Output</span>
    <span style="color:#484f58;font-size:.75rem;cursor:pointer" onclick="document.getElementById('log-section').style.display='none'">✕ hide</span>
  </div>
  <pre id="log-box" style="background:#0a0d14;border:1px solid #21283a;border-radius:8px;padding:10px 14px;font-size:.75rem;max-height:200px;overflow-y:auto;color:#c0c0c0;white-space:pre-wrap;word-break:break-word"></pre>
</div>

<div id="status-bar">
  <span id="sb-fetch">Connecting...</span>
  <span id="sb-rows">—</span>
</div>

<script>
let allProducts = [];
let activeCategory = null;
let knownIds = new Set();
let _priceFilter = 'all'; // 'all' | 'priced' | 'noPrice'

function setPriceFilter(mode, btn){
  _priceFilter = mode;
  document.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  applyFilter();
}

function esc(s){ return s==null?'':(s+'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function showTab(name, el){
  document.getElementById('tab-products').style.display   = name==='products'?'':'none';
  document.getElementById('tab-brands').style.display     = name==='brands'?'':'none';
  document.getElementById('tab-price-check').style.display= name==='price-check'?'':'none';
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  if(name==='price-check') loadPriceCheck();
}

function applyFilter(){
  const q = document.getElementById('search').value.toLowerCase();
  const rows = document.querySelectorAll('#tbody tr');
  let shown = 0;
  rows.forEach(r=>{
    const catMatch  = activeCategory===null || r.dataset.cat===activeCategory;
    const textMatch = !q || r.dataset.text.includes(q);
    const hasPrice  = r.dataset.price === '1';
    const priceMatch = _priceFilter==='all' || (_priceFilter==='priced' && hasPrice) || (_priceFilter==='noPrice' && !hasPrice);
    const vis = catMatch && textMatch && priceMatch;
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
      tr.dataset.cat   = p.category_name||'';
      tr.dataset.text  = [(p.name||''),(p.sku||''),(p.brand_name||''),(p.category_name||''),(p.source_name||'')].join(' ').toLowerCase();
      tr.dataset.price = (p.price && p.price > 0) ? '1' : '0';
      const price = p.price&&p.price>0
        ? `<span class="price">${parseFloat(p.price).toFixed(2)}</span>`
        : `<span class="no-price">—</span>`;
      const url = p.source_url ? `<a class="url-link" href="${esc(p.source_url)}" target="_blank">🔗</a>` : '';
      const isBadName = p.name && (p.name.includes('.com') || p.name.includes('.sa'));
      const nameHtml = isBadName ? `<span class="bad-name" title="Suspicious name — page was likely blocked">⚠ ${esc(p.name)}</span>` : esc(p.name);
      tr.innerHTML = `
        <td>${esc(p.id)}</td>
        <td class="name-ar">${nameHtml}</td>
        <td>${esc(p.sku)}</td>
        <td>${price}</td>
        <td class="brand-ar">${esc(p.brand_name)}</td>
        <td class="cat-ar">${esc(p.category_name)}</td>
        <td><span class="source-badge">${esc(p.source_name||'')}</span></td>
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

let logInterval = null;
let _activeScraper = null;

async function runScraper(name, btn){
  const st = document.getElementById('scraper-status');
  btn.disabled = true;
  btn.textContent = '⏳ Starting...';
  st.textContent = '⏳ Launching ' + name + '...'; st.style.color='#e0b040';
  document.getElementById('log-box').textContent = '';
  document.getElementById('log-section').style.display = '';
  _activeScraper = name;
  try {
    const res = await fetch('/api/run-scraper?scraper='+name, {method:'POST'});
    const d = await res.json();
    if(d.status==='started'||d.status==='already_running'){
      btn.textContent = '⏳ Running...';
      st.textContent='🟢 ' + name + ' running'; st.style.color='#22c55e';
    } else {
      btn.textContent = name==='elburoj' ? '▶ El Buroj' : '▶ Electric House';
      btn.disabled=false;
    }
  } catch(e){
    btn.textContent = name==='elburoj' ? '▶ El Buroj' : '▶ Electric House';
    btn.disabled=false;
    st.textContent='✗ Failed to start'; st.style.color='#f85149';
  }
  startLogPolling(name);
}

function startLogPolling(name){
  if(logInterval) clearInterval(logInterval);
  logInterval = setInterval(async()=>{
    try{
      const r = await fetch('/api/scraper-log?scraper='+name);
      const d = await r.json();
      const box = document.getElementById('log-box');
      box.textContent = d.log.join('\n');
      box.scrollTop = box.scrollHeight;
    }catch(_){}
  }, 1500);
}

async function pollScraperStatus(){
  const _SCRAPER_LABELS = {
    'elburoj': '▶ El Buroj', 'electric-house': '▶ Electric House',
    'janoubco': '▶ Janoubco', 'microless': '▶ Microless',
    'mejdaf': '▶ Mejdaf', 'baytalebaa': '▶ Baytalebaa',
  };
  for(const name of ['elburoj','electric-house','janoubco','microless','mejdaf','baytalebaa']){
    try {
      const res = await fetch('/api/scraper-status?scraper='+name);
      const d = await res.json();
      const btnId = 'run-btn-' + name;
      const btn = document.getElementById(btnId);
      if(!btn) continue;
      const label = _SCRAPER_LABELS[name] || ('▶ '+name);
      const st = document.getElementById('scraper-status');
      if(d.status==='running'){
        btn.disabled=true; btn.textContent='⏳ Running...';
        if(_activeScraper===name){ st.textContent='🟢 '+name+' running'; st.style.color='#22c55e'; }
        startLogPolling(name);
      } else if(d.status==='done'){
        btn.disabled=false; btn.textContent=label;
        if(_activeScraper===name){ st.textContent='✓ '+name+' done'; st.style.color='#22c55e'; if(logInterval){clearInterval(logInterval);logInterval=null;} }
      } else if(d.status && d.status.startsWith('error')){
        btn.disabled=false; btn.textContent=label;
        if(_activeScraper===name){
          st.textContent='✗ '+name+' failed — see log below'; st.style.color='#f85149';
          document.getElementById('log-section').style.display='';
          if(logInterval){clearInterval(logInterval);logInterval=null;}
        }
      } else {
        btn.disabled=false; btn.textContent=label;
      }
    } catch(_){}
  }
}

async function runAll(btn){
  btn.disabled = true;
  btn.textContent = '⏳ Running All...';
  const st = document.getElementById('scraper-status');
  st.textContent = '⏳ Running all scrapers...'; st.style.color='#e0b040';
  document.getElementById('log-box').textContent = '';
  document.getElementById('log-section').style.display = '';
  _activeScraper = 'elburoj';
  const scrapers = [
    {name:'elburoj',       btnId:'run-btn-elburoj'},
    {name:'electric-house',btnId:'run-btn-electric-house'},
    {name:'janoubco',      btnId:'run-btn-janoubco'},
    {name:'microless',     btnId:'run-btn-microless'},
    {name:'mejdaf',        btnId:'run-btn-mejdaf'},
    {name:'baytalebaa',    btnId:'run-btn-baytalebaa'},
  ];
  for(const s of scrapers){
    const b = document.getElementById(s.btnId);
    if(b){ b.disabled=true; b.textContent='⏳ Running...'; }
    try {
      await fetch('/api/run-scraper?scraper='+s.name, {method:'POST'});
    } catch(_){}
  }
  startLogPolling('elburoj');
  // re-enable Run All when both finish
  const check = setInterval(async()=>{
    let anyRunning = false;
    for(const s of scrapers){
      try{
        const r = await fetch('/api/scraper-status?scraper='+s.name);
        const d = await r.json();
        if(d.status==='running') anyRunning=true;
      }catch(_){}
    }
    if(!anyRunning){
      clearInterval(check);
      btn.disabled=false; btn.textContent='▶ Run All';
      st.textContent='✓ All scrapers done'; st.style.color='#22c55e';
    }
  }, 3000);
}

async function refetchPrices(btn){
  if(btn){ btn.disabled=true; btn.textContent='⏳ Refetching...'; }
  try{ await fetch('/api/run-refetch', {method:'POST'}); } catch(_){}
  const logEl = document.getElementById('refetch-log');
  if(logEl){ logEl.style.display='block'; logEl.textContent='Starting...'; }
  const check = setInterval(async()=>{
    try{
      const r = await fetch('/api/refetch-status');
      const d = await r.json();
      if(logEl && d.log) logEl.textContent = d.log.join('\n');
      if(d.status !== 'running'){
        clearInterval(check);
        if(btn){ btn.disabled=false; btn.textContent='↺ Refetch Prices'; }
        loadPriceCheck();
      }
    }catch(_){ clearInterval(check); if(btn){ btn.disabled=false; btn.textContent='↺ Refetch Prices'; } }
  }, 2000);
}

async function loadPriceCheck(){
  const el = document.getElementById('price-check-content');
  el.textContent = 'Loading...';
  try{
    const res = await fetch('/api/price-stats');
    const rows = await res.json();
    if(!rows.length){ el.textContent='No data'; return; }
    const totalAll = rows.reduce((s,r)=>s+(r.total||0),0);
    const pricedAll = rows.reduce((s,r)=>s+(r.with_price||0),0);
    const pctAll = totalAll>0 ? (100*pricedAll/totalAll).toFixed(1) : 0;
    const fillClass = pct => pct>=70?'':'pct<40?low:mid';
    let html = `
      <div style="margin-bottom:16px;padding:14px;background:#161b27;border:1px solid #21283a;border-radius:10px;display:flex;gap:32px">
        <div><div style="font-size:1.6rem;font-weight:700;color:#58a6ff">${pricedAll.toLocaleString()}</div><div style="color:#7d8590;font-size:.8rem">Total With Price</div></div>
        <div><div style="font-size:1.6rem;font-weight:700;color:#f85149">${(totalAll-pricedAll).toLocaleString()}</div><div style="color:#7d8590;font-size:.8rem">Missing Price</div></div>
        <div><div style="font-size:1.6rem;font-weight:700;color:#22c55e">${pctAll}%</div><div style="color:#7d8590;font-size:.8rem">Overall Coverage</div></div>
      </div>
      <table class="pc-table">
        <thead><tr>
          <th>Scraper / Source</th><th>Total</th><th>With Price</th><th>Missing</th>
          <th>Coverage</th><th>Min SAR</th><th>Avg SAR</th><th>Max SAR</th>
        </tr></thead><tbody>`;
    for(const r of rows){
      const pct = r.pct||0;
      const fc  = pct>=70 ? '' : (pct<40 ? 'low' : 'mid');
      html += `<tr>
        <td><strong>${esc(r.source||'Unknown')}</strong></td>
        <td>${(r.total||0).toLocaleString()}</td>
        <td style="color:#22c55e">${(r.with_price||0).toLocaleString()}</td>
        <td style="color:#f85149">${(r.no_price||0).toLocaleString()}</td>
        <td>
          <div style="display:flex;align-items:center;gap:8px">
            <div class="pc-bar"><div class="pc-fill ${fc}" style="width:${pct}%"></div></div>
            <span style="min-width:42px;color:${pct>=70?'#22c55e':pct<40?'#f85149':'#f59e0b'}">${pct}%</span>
          </div>
        </td>
        <td style="color:#7d8590">${r.min_price!=null?r.min_price:'—'}</td>
        <td style="color:#7d8590">${r.avg_price!=null?r.avg_price:'—'}</td>
        <td style="color:#7d8590">${r.max_price!=null?r.max_price:'—'}</td>
      </tr>`;
    }
    html += '</tbody></table>';
    el.innerHTML = html;
  }catch(e){
    el.textContent = '✗ Failed: '+e.message;
  }
}

refresh();
setInterval(refresh, 3000);
setInterval(pollScraperStatus, 2000);
pollScraperStatus();
</script>
</body>
</html>"""


def export_db_json():
    """Export all products as JSON for download."""
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT p.id, p.external_id, p.sku, p.name, p.price,
                   p.source_url, p.is_synced, p.last_scraped_at,
                   p.description, p.specifications,
                   b.name AS brand,
                   c.name AS category,
                   s.name AS source
            FROM scraper_products p
            LEFT JOIN scraper_brands b ON p.scraper_brand_id = b.id
            LEFT JOIN scraper_categories c ON p.scraper_category_id = c.id
            LEFT JOIN scraper_sources s ON p.source_id = s.id
            ORDER BY p.id
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress access logs

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML.encode("utf-8"))

        elif self.path == "/api/scraper-status":
            body = json.dumps({"status": _scraper_status()}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)

        elif self.path.startswith("/api/scraper-status?"):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            name = qs.get("scraper", ["elburoj"])[0]
            body = json.dumps({"status": _scraper_status(name), "scraper": name}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)

        elif self.path.startswith("/api/scraper-log"):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            name = qs.get("scraper", ["elburoj"])[0]
            with _scraper_lock:
                lines = list(_scraper_logs.get(name, []))
            body = json.dumps({"log": lines}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)

        elif self.path == "/api/price-stats":
            data = query_price_stats()
            body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)

        elif self.path == "/api/refetch-status":
            body = json.dumps({"status": _refetch_status(), "log": _refetch_log[-50:]}, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)

        elif self.path == "/api/export":
            products = export_db_json()
            body = json.dumps(products, ensure_ascii=False, default=str, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Disposition", "attachment; filename=\"products_export.json\"")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)

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

    def do_POST(self):
        if self.path == "/api/run-refetch":
            status = _refetch_status()
            if status == "running":
                body = json.dumps({"status": "already_running"}).encode("utf-8")
            else:
                threading.Thread(target=_run_price_refetch, daemon=True).start()
                body = json.dumps({"status": "started"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)

        elif self.path.startswith("/api/run-scraper"):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            name = qs.get("scraper", ["elburoj"])[0]
            if name not in _SCRAPERS:
                self.send_response(400)
                self.end_headers()
                return
            status = _scraper_status(name)
            if status == "running":
                body = json.dumps({"status": "already_running", "scraper": name}).encode("utf-8")
            else:
                threading.Thread(target=_run_scraper, args=(name,), daemon=True).start()
                body = json.dumps({"status": "started", "scraper": name}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
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
