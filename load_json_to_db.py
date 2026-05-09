"""
load_json_to_db.py
-------------------
يقرأ كل ملفات JSON المـ scraped ويحطها في scraper_data.db (SQLite).

Usage:
    python load_json_to_db.py
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone

_ROOT = os.path.dirname(os.path.abspath(__file__))
_DB = os.path.join(_ROOT, "scraper_data.db")

_NOW = datetime.now(timezone.utc).isoformat()

# ── ملفات JSON المعروفة مع اسم المصدر ─────────────────────────────────────────
JSON_SOURCES = [
    {
        "file":        "scraped_products_raw.json",
        "source_name": "elburoj",
        "base_url":    "https://elburoj.com",
        "format":      "salla",         # {"products": [...]}
    },
    {
        "file":        "scraped_kmco.json",
        "source_name": "kmco",
        "base_url":    "https://kmco.sa",
        "format":      "flat_list",     # [...]
    },
    {
        "file":        "scraped_zorinstechnologies.json",
        "source_name": "zorinstechnologies",
        "base_url":    "https://www.zorinstechnologies.sa",
        "format":      "flat_list",
    },
    {
        "file":        "scraped_all_products.json",
        "source_name": "elburoj",
        "base_url":    "https://elburoj.com",
        "format":      "auto",
    },
]


def _log(msg: str):
    print(msg, flush=True)


def _parse_price(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v) if v > 0 else None
    if isinstance(v, dict):
        for k in ("amount", "price", "value", "regular"):
            p = _parse_price(v.get(k))
            if p:
                return p
        return None
    if isinstance(v, str):
        m = re.search(r"[\d]+(?:[\d,]*\.\d+)?", v.replace(",", ""))
        if m:
            try:
                return float(m.group().replace(",", "")) or None
            except ValueError:
                pass
    return None


def _extract_products(data, fmt: str) -> list[dict]:
    if fmt == "salla":
        return data.get("products", []) if isinstance(data, dict) else []
    if fmt == "flat_list":
        return data if isinstance(data, list) else []
    # auto
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in ("products", "items", "data", "results"):
            if isinstance(data.get(k), list):
                return data[k]
    return []


def _extract_name(p: dict) -> str:
    name = p.get("name") or p.get("title") or ""
    if isinstance(name, dict):
        return name.get("ar") or name.get("en") or ""
    return str(name).strip()


def _extract_url(p: dict, base_url: str) -> str:
    url = p.get("source_url") or p.get("url") or p.get("link") or p.get("share_link") or ""
    if isinstance(url, dict):
        url = url.get("slug") or url.get("link") or ""
    url = str(url).strip()
    if url and not url.startswith("http"):
        url = base_url.rstrip("/") + "/" + url.lstrip("/")
    return url


def _extract_category(p: dict) -> str | None:
    for k in ("_category_name", "category", "cat_tag", "category_name"):
        v = p.get(k)
        if v and isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _extract_brand(p: dict) -> str | None:
    b = p.get("brand")
    if isinstance(b, dict):
        return (b.get("name") or "").strip() or None
    if isinstance(b, str) and b.strip():
        return b.strip()
    return None


def _init_db(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS scraper_sources (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            base_url TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS scraper_categories (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER REFERENCES scraper_sources(id),
            name      TEXT NOT NULL,
            external_id TEXT,
            url       TEXT,
            created_at TEXT,
            updated_at TEXT,
            UNIQUE(source_id, name)
        );
        CREATE TABLE IF NOT EXISTS scraper_brands (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER REFERENCES scraper_sources(id),
            name      TEXT NOT NULL,
            created_at TEXT,
            updated_at TEXT,
            UNIQUE(source_id, name)
        );
        CREATE TABLE IF NOT EXISTS scraper_products (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id       INTEGER REFERENCES scraper_sources(id),
            scraper_category_id INTEGER REFERENCES scraper_categories(id),
            scraper_brand_id    INTEGER REFERENCES scraper_brands(id),
            external_id     TEXT,
            source_url      TEXT NOT NULL,
            sku             TEXT,
            name            TEXT NOT NULL,
            description     TEXT,
            specifications  TEXT,
            price           REAL,
            raw_data        TEXT,
            hash            TEXT,
            is_synced       INTEGER DEFAULT 0,
            synced_at       TEXT,
            last_scraped_at TEXT,
            created_at      TEXT,
            updated_at      TEXT
        );
        CREATE INDEX IF NOT EXISTS ix_sp_source_ext ON scraper_products(source_id, external_id);
        CREATE INDEX IF NOT EXISTS ix_sp_source_url ON scraper_products(source_id, source_url);
        CREATE INDEX IF NOT EXISTS ix_sp_source_sku ON scraper_products(source_id, sku);
    """)
    conn.commit()


def _get_or_create_source(conn: sqlite3.Connection, name: str, base_url: str) -> int:
    row = conn.execute("SELECT id FROM scraper_sources WHERE name = ?", (name,)).fetchone()
    if row:
        return row[0]
    conn.execute(
        "INSERT INTO scraper_sources (name, base_url, created_at, updated_at) VALUES (?,?,?,?)",
        (name, base_url, _NOW, _NOW),
    )
    conn.commit()
    return conn.execute("SELECT id FROM scraper_sources WHERE name = ?", (name,)).fetchone()[0]


def _get_or_create_category(conn: sqlite3.Connection, source_id: int, name: str) -> int:
    row = conn.execute(
        "SELECT id FROM scraper_categories WHERE source_id=? AND name=?", (source_id, name)
    ).fetchone()
    if row:
        return row[0]
    conn.execute(
        "INSERT INTO scraper_categories (source_id, name, created_at, updated_at) VALUES (?,?,?,?)",
        (source_id, name, _NOW, _NOW),
    )
    conn.commit()
    return conn.execute(
        "SELECT id FROM scraper_categories WHERE source_id=? AND name=?", (source_id, name)
    ).fetchone()[0]


def _get_or_create_brand(conn: sqlite3.Connection, source_id: int, name: str) -> int:
    row = conn.execute(
        "SELECT id FROM scraper_brands WHERE source_id=? AND name=?", (source_id, name)
    ).fetchone()
    if row:
        return row[0]
    conn.execute(
        "INSERT INTO scraper_brands (source_id, name, created_at, updated_at) VALUES (?,?,?,?)",
        (source_id, name, _NOW, _NOW),
    )
    conn.commit()
    return conn.execute(
        "SELECT id FROM scraper_brands WHERE source_id=? AND name=?", (source_id, name)
    ).fetchone()[0]


def _upsert_product(conn: sqlite3.Connection, source_id: int, cat_id, brand_id, p: dict, base_url: str):
    name = _extract_name(p)
    if not name:
        return False

    external_id = str(p.get("external_id") or p.get("id") or "").strip() or None
    source_url  = _extract_url(p, base_url)
    sku         = str(p.get("sku") or "").strip() or None
    price       = _parse_price(p.get("price"))
    description = p.get("description") or None
    raw_data    = json.dumps(p, ensure_ascii=False)

    # Dedup: external_id → url → sku
    existing = None
    if external_id:
        existing = conn.execute(
            "SELECT id FROM scraper_products WHERE source_id=? AND external_id=?",
            (source_id, external_id),
        ).fetchone()
    if not existing and source_url:
        existing = conn.execute(
            "SELECT id FROM scraper_products WHERE source_id=? AND source_url=?",
            (source_id, source_url),
        ).fetchone()
    if not existing and sku:
        existing = conn.execute(
            "SELECT id FROM scraper_products WHERE source_id=? AND sku=?",
            (source_id, sku),
        ).fetchone()

    if existing:
        conn.execute(
            """UPDATE scraper_products
               SET name=?, price=?, sku=?, description=?, scraper_category_id=?,
                   scraper_brand_id=?, raw_data=?, updated_at=?, last_scraped_at=?
               WHERE id=?""",
            (name, price, sku, description, cat_id, brand_id, raw_data, _NOW, _NOW, existing[0]),
        )
        return False   # updated
    else:
        conn.execute(
            """INSERT INTO scraper_products
               (source_id, scraper_category_id, scraper_brand_id, external_id, source_url,
                sku, name, description, price, raw_data, is_synced, created_at, updated_at, last_scraped_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,0,?,?,?)""",
            (source_id, cat_id, brand_id, external_id, source_url or "?",
             sku, name, description, price, raw_data, _NOW, _NOW, _NOW),
        )
        return True    # inserted


def process_file(conn: sqlite3.Connection, cfg: dict) -> tuple[int, int, int]:
    filepath = os.path.join(_ROOT, cfg["file"])
    if not os.path.exists(filepath):
        _log(f"  [SKIP] {cfg['file']} not found")
        return 0, 0, 0

    size_kb = os.path.getsize(filepath) / 1024
    if size_kb < 0.1:
        _log(f"  [SKIP] {cfg['file']} is empty")
        return 0, 0, 0

    _log(f"  Reading {cfg['file']}  ({size_kb:.1f} KB)...")
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    products = _extract_products(data, cfg["format"])
    _log(f"  Found {len(products)} records")

    source_id = _get_or_create_source(conn, cfg["source_name"], cfg["base_url"])

    cat_cache:   dict[str, int] = {}
    brand_cache: dict[str, int] = {}
    inserted = updated = skipped = 0

    for p in products:
        name = _extract_name(p)
        if not name:
            skipped += 1
            continue

        # Category
        cat_name = _extract_category(p)
        cat_id = None
        if cat_name:
            if cat_name not in cat_cache:
                cat_cache[cat_name] = _get_or_create_category(conn, source_id, cat_name)
            cat_id = cat_cache[cat_name]

        # Brand
        brand_name = _extract_brand(p)
        brand_id = None
        if brand_name:
            if brand_name not in brand_cache:
                brand_cache[brand_name] = _get_or_create_brand(conn, source_id, brand_name)
            brand_id = brand_cache[brand_name]

        try:
            was_inserted = _upsert_product(conn, source_id, cat_id, brand_id, p, cfg["base_url"])
            if was_inserted:
                inserted += 1
            else:
                updated += 1
        except Exception as e:
            _log(f"    [WARN] {name!r}: {e}")
            skipped += 1

    conn.commit()
    _log(f"  ✓ {cfg['source_name']}: inserted={inserted}  updated={updated}  skipped={skipped}")
    return inserted, updated, skipped


def main():
    _log(f"[INFO] Database: {_DB}")
    conn = sqlite3.connect(_DB)
    _init_db(conn)

    total_ins = total_upd = total_skip = 0
    for cfg in JSON_SOURCES:
        ins, upd, skip = process_file(conn, cfg)
        total_ins  += ins
        total_upd  += upd
        total_skip += skip

    conn.close()
    _log(f"\n[DONE] Total inserted={total_ins}  updated={total_upd}  skipped={total_skip}")


if __name__ == "__main__":
    main()
