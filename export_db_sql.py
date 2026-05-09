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
    python export_db_sql.py --mysql                   # MySQL/MariaDB compatible output
    python export_db_sql.py --mysql --split 5000      # split into chunks of 5000 rows each
"""

from __future__ import annotations

import argparse
import os
import re
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


def _sqlite_val_to_sql(val, mysql: bool = False) -> str:
    """Convert a Python value to a safe SQL literal."""
    if val is None:
        return "NULL"
    if isinstance(val, (int, float)):
        return str(val)
    # In MySQL mode, convert boolean strings to integers
    if mysql and isinstance(val, str) and val.lower() in ("true", "false"):
        return "1" if val.lower() == "true" else "0"
    # Escape single quotes by doubling them
    escaped = str(val).replace("'", "''")
    return f"'{escaped}'"


def _convert_create_to_mysql(create_sql: str, table: str) -> str:
    """Convert SQLite CREATE TABLE statement to MySQL-compatible syntax."""
    sql = create_sql.strip()

    # Replace double-quoted identifiers with backticks
    sql = re.sub(r'"(\w+)"', r'`\1`', sql)

    # Replace unquoted table name in CREATE TABLE
    sql = re.sub(
        r'(?i)(CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?)\s*' + re.escape(table),
        rf'\1`{table}`',
        sql
    )

    # Type conversions
    sql = re.sub(r'\bINTEGER\b', 'BIGINT', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bREAL\b',    'DOUBLE', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bTEXT\b',    'LONGTEXT', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bBLOB\b',    'LONGBLOB', sql, flags=re.IGNORECASE)

    # SQLite AUTOINCREMENT → MySQL AUTO_INCREMENT
    sql = re.sub(r'\bAUTOINCREMENT\b', 'AUTO_INCREMENT', sql, flags=re.IGNORECASE)

    # Move PRIMARY KEY inline for MySQL AUTO_INCREMENT tables
    # SQLite: col INTEGER PRIMARY KEY AUTOINCREMENT  -> already inline, just fix keyword

    # Default datetime expressions
    sql = re.sub(r"DEFAULT\s+\(datetime\('now'\)\)", 'DEFAULT CURRENT_TIMESTAMP', sql, flags=re.IGNORECASE)
    sql = re.sub(r"DEFAULT\s+\(CURRENT_TIMESTAMP\)", 'DEFAULT CURRENT_TIMESTAMP', sql, flags=re.IGNORECASE)

    # Remove SQLite-specific clauses
    sql = re.sub(r'\bWITHOUT\s+ROWID\b', '', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bSTRICT\b', '', sql, flags=re.IGNORECASE)

    # Add ENGINE=InnoDB at the end
    sql = sql.rstrip().rstrip(';')
    sql += ' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci'

    return sql


def export_table(
    conn: sqlite3.Connection,
    table: str,
    out,
    include_create: bool = True,
    include_data: bool = True,
    batch_size: int = 500,
    mysql: bool = False,
):
    q = "`" if mysql else '"'
    out.write(f"\n-- ===================================================\n")
    out.write(f"-- Table: {table}\n")
    out.write(f"-- ===================================================\n\n")

    if include_create:
        create_sql = _get_create_sql(conn, table)
        if create_sql:
            out.write(f"DROP TABLE IF EXISTS {q}{table}{q};\n")
            if mysql:
                out.write(_convert_create_to_mysql(create_sql, table))
            else:
                out.write(create_sql.strip())
            out.write(";\n\n")

            if not mysql:
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
    q = "`" if mysql else '"'
    cols_sql = ", ".join(f'{q}{c}{q}' for c in cols)

    out.write(f"-- {row_count:,} rows\n")

    batch = []
    written = 0

    def flush_batch():
        if not batch:
            return
        values_block = ",\n  ".join(batch)
        out.write(f'INSERT INTO {q}{table}{q} ({cols_sql}) VALUES\n  {values_block};\n')

    for row in cursor:
        vals = ", ".join(_sqlite_val_to_sql(v, mysql) for v in row)
        batch.append(f"({vals})")
        if len(batch) >= batch_size:
            flush_batch()
            written += len(batch)
            batch = []

    flush_batch()
    written += len(batch)
    out.write("\n")


def _header(out, tables: list[str], mysql: bool, part: int = 0, total: int = 0):
    out.write("-- =========================================================\n")
    out.write(f"-- SQL Export of scraper_data.db\n")
    out.write(f"-- Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
    out.write(f"-- Tables: {', '.join(tables)}\n")
    if mysql:
        out.write("-- Target: MySQL / MariaDB\n")
    if part:
        out.write(f"-- Part: {part} / {total}\n")
    out.write("-- =========================================================\n")
    if mysql:
        out.write("SET NAMES utf8mb4;\nSET FOREIGN_KEY_CHECKS=0;\nSTART TRANSACTION;\n")
    else:
        out.write("PRAGMA foreign_keys = OFF;\nBEGIN TRANSACTION;\n")


def _footer(out, mysql: bool):
    if mysql:
        out.write("COMMIT;\nSET FOREIGN_KEY_CHECKS=1;\n")
    else:
        out.write("COMMIT;\nPRAGMA foreign_keys = ON;\n")


def _export_split(conn: sqlite3.Connection, tables: list[str], args, chunk_size: int):
    """Export data split into multiple numbered files."""
    base, ext = os.path.splitext(args.output)
    if not ext:
        ext = ".sql"
    mysql = args.mysql
    q = "`" if mysql else '"'

    file_index = 1
    total_rows_written = 0
    generated_files: list[str] = []

    # First file: schema only (CREATE TABLE)
    if not args.no_create:
        schema_path = f"{base}_part00_schema{ext}"
        with open(schema_path, "w", encoding="utf-8") as out:
            _header(out, tables, mysql)
            for table in tables:
                create_sql = _get_create_sql(conn, table)
                if not create_sql:
                    continue
                out.write(f"\nDROP TABLE IF EXISTS {q}{table}{q};\n")
                if mysql:
                    out.write(_convert_create_to_mysql(create_sql, table))
                else:
                    out.write(create_sql.strip())
                out.write(";\n")
            _footer(out, mysql)
        size_kb = os.path.getsize(schema_path) / 1024
        _log(f"  [schema] {schema_path}  ({size_kb:.1f} KB)")
        generated_files.append(schema_path)

    if args.no_data:
        _log(f"\n[DONE] {len(generated_files)} file(s) generated.")
        return

    # Data files: chunk_size rows per file
    for table in tables:
        row_count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        if row_count == 0:
            _log(f"  Skipping {table}: 0 rows")
            continue

        _log(f"  Exporting {table}: {row_count:,} rows -> chunks of {chunk_size:,}...")
        cursor = conn.execute(f'SELECT * FROM "{table}"')
        cols = [d[0] for d in cursor.description]
        cols_sql = ", ".join(f'{q}{c}{q}' for c in cols)

        part_num = 0
        batch = []
        current_file = None
        current_out = None

        def open_next_part():
            nonlocal part_num, current_file, current_out
            if current_out:
                _footer(current_out, mysql)
                current_out.close()
                size_kb = os.path.getsize(current_file) / 1024
                _log(f"    -> {current_file}  ({size_kb:.1f} KB)")
                generated_files.append(current_file)
            part_num += 1
            total_parts = (row_count + chunk_size - 1) // chunk_size
            current_file = f"{base}_part{file_index:02d}_{table}_{part_num:03d}{ext}"
            current_out = open(current_file, "w", encoding="utf-8")
            _header(current_out, [table], mysql, part_num, total_parts)

        def flush_batch():
            if not batch:
                return
            values_block = ",\n  ".join(batch)
            current_out.write(f'INSERT INTO {q}{table}{q} ({cols_sql}) VALUES\n  {values_block};\n')

        open_next_part()
        rows_in_part = 0

        for row in cursor:
            vals = ", ".join(_sqlite_val_to_sql(v, mysql) for v in row)
            batch.append(f"({vals})")
            rows_in_part += 1
            total_rows_written += 1

            if len(batch) >= 500:
                flush_batch()
                batch = []

            if rows_in_part >= chunk_size:
                flush_batch()
                batch = []
                rows_in_part = 0
                open_next_part()

        flush_batch()
        if current_out:
            _footer(current_out, mysql)
            current_out.close()
            size_kb = os.path.getsize(current_file) / 1024
            _log(f"    -> {current_file}  ({size_kb:.1f} KB)")
            generated_files.append(current_file)

        file_index += 1

    _log(f"\n[DONE] {len(generated_files)} files, {total_rows_written:,} rows total.")
    for f in generated_files:
        _log(f"  {f}")


def main():
    parser = argparse.ArgumentParser(description="Export scraper_data.db to SQL file")
    parser.add_argument("--output", default=_OUT, help="Output file path")
    parser.add_argument("--table", default=None, help="Export one specific table only")
    parser.add_argument("--no-create", action="store_true", help="Skip CREATE TABLE statements")
    parser.add_argument("--no-data",   action="store_true", help="Export schema only, no INSERT data")
    parser.add_argument("--mysql",     action="store_true", help="MySQL/MariaDB compatible output")
    parser.add_argument("--split",     type=int, default=0, help="Split into multiple files, N rows each (e.g. 5000)")
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
    if args.mysql:
        _log("[INFO] Mode: MySQL/MariaDB compatible")
    if args.split:
        _log(f"[INFO] Split mode: {args.split:,} rows per file")
        _export_split(conn, tables, args, args.split)
        conn.close()
        return

    with open(args.output, "w", encoding="utf-8") as out:
        _header(out, tables, args.mysql)

        for table in tables:
            export_table(
                conn, table, out,
                include_create=not args.no_create,
                include_data=not args.no_data,
                mysql=args.mysql,
            )

        _footer(out, args.mysql)

    size_mb = os.path.getsize(args.output) / 1024 / 1024
    _log(f"\n[DONE] Exported to: {args.output}  ({size_mb:.2f} MB)")
    conn.close()


if __name__ == "__main__":
    main()
