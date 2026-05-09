"""
push_to_main_db.py
-------------------
Reads ALL products from scraper_data.db (SQLite) and upserts them into the
main PostgreSQL database (qumta_db) — products + supplier_products tables.

What it does:
  1. Connects to scraper_data.db and reads all scraper_products rows.
  2. Connects to PostgreSQL (DATABASE_URL_SYNC from .env).
  3. Ensures an organization "Scraper Import" exists (creates it if not).
  4. Ensures a Supplier row exists for each source name (elburoj, janoubco…).
  5. Upserts each product into `products` (dedup by org_id + slug).
  6. Upserts each product into `supplier_products` (dedup by supplier_id + product_id).
  7. Marks the scraper_products row as is_synced = 1.

Usage:
    python push_to_main_db.py            # all products
    python push_to_main_db.py --all      # force re-upload even if already synced
    python push_to_main_db.py --limit 200
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import uuid
from datetime import datetime, timezone

# ── Load .env manually (no pydantic-settings) ─────────────────────────────────
def _load_env(path: str = ".env"):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            os.environ.setdefault(k, v)

_load_env(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

import psycopg2
import psycopg2.extras

# ── Paths ──────────────────────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.abspath(__file__))
_SQLITE_PATH = os.path.join(_ROOT, "scraper_data.db")
_PG_DSN = os.environ.get("DATABASE_URL_SYNC", "")

# Strip SQLAlchemy driver prefix so psycopg2 can parse it
_PG_DSN = re.sub(r"^postgresql\+\w+://", "postgresql://", _PG_DSN)
_PG_DSN = re.sub(r"^postgres\+\w+://", "postgresql://", _PG_DSN)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:500] or "product"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(msg: str):
    print(msg, flush=True)


# ── Read from SQLite ───────────────────────────────────────────────────────────

def read_scraper_products(only_unsynced: bool = True, limit: int | None = None) -> list[dict]:
    if not os.path.exists(_SQLITE_PATH):
        _log(f"[ERROR] scraper_data.db not found at {_SQLITE_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(_SQLITE_PATH)
    conn.row_factory = sqlite3.Row

    where = "WHERE p.price IS NOT NULL AND p.price > 0" if only_unsynced else "WHERE 1=1"
    if only_unsynced:
        where += " AND (p.is_synced IS NULL OR p.is_synced = 0)"

    lim = f"LIMIT {limit}" if limit else ""

    rows = conn.execute(f"""
        SELECT
            p.id         AS scraper_id,
            p.name,
            p.sku,
            p.source_url,
            p.price,
            p.description,
            p.specifications,
            p.external_id,
            b.name       AS brand_name,
            c.name       AS category_name,
            s.name       AS source_name,
            s.id         AS source_id
        FROM scraper_products p
        LEFT JOIN scraper_brands    b ON p.scraper_brand_id = b.id
        LEFT JOIN scraper_categories c ON p.scraper_category_id = c.id
        LEFT JOIN scraper_sources   s ON p.source_id = s.id
        {where}
        ORDER BY p.id
        {lim}
    """).fetchall()

    conn.close()
    return [dict(r) for r in rows]


def mark_synced(scraper_ids: list[int]):
    if not scraper_ids:
        return
    conn = sqlite3.connect(_SQLITE_PATH)
    conn.execute(
        f"UPDATE scraper_products SET is_synced = 1 WHERE id IN ({','.join('?' * len(scraper_ids))})",
        scraper_ids,
    )
    conn.commit()
    conn.close()


# ── PostgreSQL helpers ─────────────────────────────────────────────────────────

def ensure_org(cur) -> str:
    """Return the UUID of the 'Scraper Import' org, creating it if needed."""
    cur.execute("SELECT id FROM organizations WHERE slug = 'scraper-import' LIMIT 1")
    row = cur.fetchone()
    if row:
        return str(row[0])

    org_id = str(uuid.uuid4())
    now = _now()
    cur.execute(
        """
        INSERT INTO organizations (id, name, slug, is_active, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (slug) DO NOTHING
        """,
        (org_id, "Scraper Import", "scraper-import", True, now, now),
    )
    # Re-fetch in case of race
    cur.execute("SELECT id FROM organizations WHERE slug = 'scraper-import' LIMIT 1")
    return str(cur.fetchone()[0])


def ensure_supplier(cur, org_id: str, source_name: str, source_website_map: dict) -> str:
    """Return UUID of supplier for this source, creating if needed."""
    slug = _slugify(source_name or "unknown")
    cur.execute(
        "SELECT id FROM suppliers WHERE org_id = %s AND slug = %s AND deleted_at IS NULL LIMIT 1",
        (org_id, slug),
    )
    row = cur.fetchone()
    if row:
        return str(row[0])

    sup_id = str(uuid.uuid4())
    now = _now()
    website = source_website_map.get(source_name, "")
    cur.execute(
        """
        INSERT INTO suppliers (id, org_id, name, slug, website, country, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        """,
        (sup_id, org_id, source_name or "Unknown", slug, website, "SA", now, now),
    )
    cur.execute(
        "SELECT id FROM suppliers WHERE org_id = %s AND slug = %s LIMIT 1",
        (org_id, slug),
    )
    return str(cur.fetchone()[0])


def upsert_product(cur, org_id: str, row: dict) -> str:
    """Upsert into products table; return its UUID."""
    name = (row["name"] or "").strip() or "Unnamed"
    base_slug = _slugify(name)
    # Keep slug unique per org by appending sku suffix if available
    sku_suffix = ("-" + _slugify(row["sku"])) if row.get("sku") else ""
    slug = (base_slug + sku_suffix)[:500] or "product"

    metadata = {}
    if row.get("brand_name"):
        metadata["brand"] = row["brand_name"]
    if row.get("source_name"):
        metadata["source"] = row["source_name"]
    if row.get("source_url"):
        metadata["source_url"] = row["source_url"]
    if row.get("external_id"):
        metadata["external_id"] = row["external_id"]
    if row.get("specifications"):
        metadata["specifications"] = row["specifications"]

    now = _now()
    product_id = str(uuid.uuid4())

    cur.execute(
        """
        INSERT INTO products (id, org_id, name, slug, sku, category, description, metadata, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        """,
        (
            product_id,
            org_id,
            name,
            slug,
            row.get("sku"),
            row.get("category_name"),
            row.get("description"),
            json.dumps(metadata, ensure_ascii=False),
            now,
            now,
        ),
    )

    # Fetch actual id (may already exist)
    cur.execute(
        "SELECT id FROM products WHERE org_id = %s AND slug = %s AND deleted_at IS NULL LIMIT 1",
        (org_id, slug),
    )
    result = cur.fetchone()
    if result:
        return str(result[0])

    # If slug had collision, try by sku
    if row.get("sku"):
        cur.execute(
            "SELECT id FROM products WHERE org_id = %s AND sku = %s AND deleted_at IS NULL LIMIT 1",
            (org_id, row["sku"]),
        )
        result = cur.fetchone()
        if result:
            return str(result[0])

    return product_id


def upsert_supplier_product(cur, org_id: str, supplier_id: str, product_id: str, row: dict):
    """Upsert into supplier_products; update price if changed."""
    now = _now()
    sp_id = str(uuid.uuid4())
    price = float(row["price"]) if row.get("price") else None

    cur.execute(
        """
        INSERT INTO supplier_products
            (id, org_id, supplier_id, product_id, supplier_sku, price, currency, is_active, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        """,
        (sp_id, org_id, supplier_id, product_id, row.get("sku"), price, "SAR", True, now, now),
    )

    # Update price if row already existed
    cur.execute(
        """
        UPDATE supplier_products
        SET price = %s, updated_at = %s
        WHERE supplier_id = %s AND product_id = %s AND price IS DISTINCT FROM %s
        """,
        (price, now, supplier_id, product_id, price),
    )


# ── Main ───────────────────────────────────────────────────────────────────────

SOURCE_WEBSITES = {
    "elburoj":        "https://elburoj.com",
    "electric-house": "https://electrichouse.com.sa",
    "electric_house": "https://electrichouse.com.sa",
    "janoubco":       "https://janoubco.com",
    "microless":      "https://microless.com",
    "mejdaf":         "https://mejdaf.com",
    "baytalebaa":     "https://baytalebaa.com",
    "kmco":           "https://kmco.com.sa",
    "zorinstechnologies": "https://zorinstechnologies.com",
    "schneider":      "https://www.se.com/sa/ar/",
}


def main():
    parser = argparse.ArgumentParser(description="Push scraped products to main PostgreSQL DB")
    parser.add_argument("--all", action="store_true", help="Re-upload all products, not just unsynced")
    parser.add_argument("--limit", type=int, default=None, help="Max products to push")
    args = parser.parse_args()

    if not _PG_DSN or "example.com" in _PG_DSN:
        _log("[ERROR] DATABASE_URL_SYNC is not configured in .env")
        sys.exit(1)

    _log(f"[INFO] Reading from: {_SQLITE_PATH}")
    products = read_scraper_products(only_unsynced=not args.all, limit=args.limit)
    _log(f"[INFO] Products to upload: {len(products)}")

    if not products:
        _log("[INFO] Nothing to upload. Run scrapers first, or use --all to re-upload.")
        return

    _log(f"[INFO] Connecting to PostgreSQL...")
    try:
        pg = psycopg2.connect(_PG_DSN)
    except Exception as e:
        _log(f"[ERROR] Cannot connect to PostgreSQL: {e}")
        sys.exit(1)

    pg.autocommit = False
    cur = pg.cursor()

    try:
        org_id = ensure_org(cur)
        _log(f"[INFO] Organization ID: {org_id}")

        # Cache suppliers per source
        supplier_cache: dict[str, str] = {}

        synced_ids: list[int] = []
        ok = 0
        fail = 0

        for i, row in enumerate(products, 1):
            source_name = row.get("source_name") or "unknown"
            if source_name not in supplier_cache:
                supplier_cache[source_name] = ensure_supplier(cur, org_id, source_name, SOURCE_WEBSITES)
            supplier_id = supplier_cache[source_name]

            try:
                product_id = upsert_product(cur, org_id, row)
                upsert_supplier_product(cur, org_id, supplier_id, product_id, row)
                synced_ids.append(row["scraper_id"])
                ok += 1
            except Exception as e:
                _log(f"  [WARN] Row {i} ({row.get('name','?')!r}) failed: {e}")
                pg.rollback()
                fail += 1
                continue

            if i % 50 == 0:
                pg.commit()
                _log(f"  [{i}/{len(products)}] committed — ok={ok} fail={fail}")

        pg.commit()
        _log(f"\n[DONE] Uploaded: {ok}  Failed: {fail}")

        if synced_ids:
            mark_synced(synced_ids)
            _log(f"[INFO] Marked {len(synced_ids)} rows as is_synced=1 in SQLite")

    except Exception as e:
        pg.rollback()
        _log(f"[ERROR] {e}")
        raise
    finally:
        cur.close()
        pg.close()


if __name__ == "__main__":
    main()
