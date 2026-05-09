"""
export_db_sql.py
-----------------
يصدّر كل بيانات scraper_data.db إلى ملف SQL جاهز للاستيراد في أي قاعدة بيانات.

Usage:
    python export_db_sql.py                          # exports to scraper_export.sql
    python export_db_sql.py --output my_export.sql
    python export_db_sql.py --table scraper_products  # جدول واحد فقط
    python export_db_sql.py --no-create               # بدون CREATE TABLE
    python export_db_sql.py --no-data                 # هيكل فقط بدون بيانات
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone

_ROOT = os.path.dirname(os.path.abspath(__file__))
_DB   = os.path.join(_ROOT, "scraper_data.db")
_OUT  = os.path.join(_ROOT, "scraper_export.sql")

TABLE_ORDER = [
    "scraper_sources",
    "scraper_brands",
    "scraper_categories",
    "scraper_products",
    "scraper_sync_logs",
]


def _log(msg: str):
    print(msg, flush=True)


def _get_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows]


def _get_create_sql(conn: sqlite3.Connection, table: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row[0] if row else ""


def _sqlite_val_to_sql(val) -> str:
    """Convert a Python value to a safe SQL literal."""
    if val is None:
        return "NULL"
    if isinstance(val, (int, float)):
        return str(val)
    # Escape single quotes by doubling them
    escaped = str(val).replace("'", "''")
    return f"'{escaped}'"


def export_table(
    conn: sqlite3.Connection,
    table: str,
    out,
    include_create: bool = True,
    include_data: bool = True,
    batch_size: int = 500,
):
    out.write(f"\n-- ═══════════════════════════════════════\n")
    out.write(f"-- Table: {table}\n")
    out.write(f"-- ═══════════════════════════════════════\n\n")

    if include_create:
        create_sql = _get_create_sql(conn, table)
        if create_sql:
            out.write(f"DROP TABLE IF EXISTS \"{table}\";\n")
            out.write(create_sql.strip())
            out.write(";\n\n")

            # Also write indexes
            indexes = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL",
                (table,),
            ).fetchall()
            for idx in indexes:
                out.write(idx[0].strip() + ";\n")
            if indexes:
                out.write("\n")

    if not include_data:
        return

    row_count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    _log(f"  Exporting {table}: {row_count:,} rows...")

    if row_count == 0:
        out.write(f"-- (no data)\n")
        return

    cursor = conn.execute(f'SELECT * FROM "{table}"')
    cols = [d[0] for d in cursor.description]
    cols_sql = ", ".join(f'"{c}"' for c in cols)

    out.write(f"-- {row_count:,} rows\n")

    batch = []
    written = 0

    def flush_batch():
        if not batch:
            return
        values_block = ",\n  ".join(batch)
        out.write(f'INSERT INTO "{table}" ({cols_sql}) VALUES\n  {values_block};\n')

    for row in cursor:
        vals = ", ".join(_sqlite_val_to_sql(v) for v in row)
        batch.append(f"({vals})")
        if len(batch) >= batch_size:
            flush_batch()
            written += len(batch)
            batch = []

    flush_batch()
    written += len(batch)
    out.write("\n")


def main():
    parser = argparse.ArgumentParser(description="Export scraper_data.db to SQL file")
    parser.add_argument("--output", default=_OUT, help="Output file path")
    parser.add_argument("--table", default=None, help="Export one specific table only")
    parser.add_argument("--no-create", action="store_true", help="Skip CREATE TABLE statements")
    parser.add_argument("--no-data",   action="store_true", help="Export schema only, no INSERT data")
    args = parser.parse_args()

    if not os.path.exists(_DB):
        _log(f"[ERROR] Database not found: {_DB}")
        sys.exit(1)

    conn = sqlite3.connect(_DB)
    all_tables = _get_tables(conn)

    if args.table:
        if args.table not in all_tables:
            _log(f"[ERROR] Table '{args.table}' not found. Available: {all_tables}")
            sys.exit(1)
        tables = [args.table]
    else:
        # Export in logical order, then any remaining tables
        tables = [t for t in TABLE_ORDER if t in all_tables]
        tables += [t for t in all_tables if t not in tables]

    _log(f"[INFO] Exporting {len(tables)} table(s) -> {args.output}")

    with open(args.output, "w", encoding="utf-8") as out:
        out.write("-- =========================================================\n")
        out.write(f"-- SQL Export of scraper_data.db\n")
        out.write(f"-- Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
        out.write(f"-- Tables: {', '.join(tables)}\n")
        out.write("-- =========================================================\n")
        out.write("PRAGMA foreign_keys = OFF;\n")
        out.write("BEGIN TRANSACTION;\n")

        for table in tables:
            export_table(
                conn, table, out,
                include_create=not args.no_create,
                include_data=not args.no_data,
            )

        out.write("COMMIT;\n")
        out.write("PRAGMA foreign_keys = ON;\n")

    size_mb = os.path.getsize(args.output) / 1024 / 1024
    _log(f"\n[DONE] Exported to: {args.output}  ({size_mb:.2f} MB)")
    conn.close()


if __name__ == "__main__":
    main()
