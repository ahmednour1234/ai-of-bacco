"""
app/ai/parsers/csv_parser.py
============================
CSV (comma, semicolon, tab-delimited, etc.) → DocumentRepresentation

Uses stdlib csv.Sniffer to auto-detect the delimiter.
The entire file maps to a single DocumentTable.
Encoding: tries UTF-8 first, then Latin-1 / Windows-1252 as fallback to
handle common supplier-exported files.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata

from app.ai.interfaces.base_parser import BaseParser
from app.schemas.document_representation import (
    DocumentBlock,
    DocumentRepresentation,
    DocumentTable,
)

_ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")

_FALLBACK_ENCODINGS = ["utf-8-sig", "utf-8", "latin-1", "windows-1252", "cp1256"]


def _detect_language(text: str) -> tuple[str, bool]:
    if not text:
        return "unknown", False
    arabic_chars = len(_ARABIC_RE.findall(text))
    latin_chars = sum(1 for c in text if c.isascii() and c.isalpha())
    total = arabic_chars + latin_chars
    if total == 0:
        return "unknown", False
    ratio = arabic_chars / total
    if ratio > 0.70:
        return "ar", True
    if ratio > 0.20:
        return "mixed", True
    return "en", False


def _decode(file_bytes: bytes) -> tuple[str, str]:
    """
    Try multiple encodings; return (decoded_text, encoding_used).
    Raises ValueError if all encodings fail.
    """
    for enc in _FALLBACK_ENCODINGS:
        try:
            return file_bytes.decode(enc), enc
        except (UnicodeDecodeError, LookupError):
            continue
    raise ValueError(
        "Cannot decode CSV file. Tried: " + ", ".join(_FALLBACK_ENCODINGS)
    )


def _is_header_row(row: list[str]) -> bool:
    non_empty = [c for c in row if c.strip()]
    if len(non_empty) < 2:
        return False
    numeric = sum(
        1 for c in non_empty
        if re.fullmatch(r"[-+]?\d+([.,]\d+)?", c.replace(",", "").replace(" ", ""))
    )
    return numeric < len(non_empty) / 2


class CSVParser(BaseParser):
    """
    Parse a CSV file into a DocumentRepresentation.
    Single-sheet; produces one DocumentTable and a flat all_rows list.
    """

    async def parse(self, file_bytes: bytes, filename: str) -> dict:
        rep = self._parse_to_representation(file_bytes, filename)
        return {"representation": rep}

    def _parse_to_representation(
        self, file_bytes: bytes, filename: str
    ) -> DocumentRepresentation:
        text, encoding = _decode(file_bytes)
        warnings: list[str] = []
        if encoding != "utf-8" and encoding != "utf-8-sig":
            warnings.append(f"CSV decoded with {encoding} (not UTF-8). Check for special characters.")

        # Detect delimiter
        sample = text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample)
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = ","  # safe default

        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        raw_rows: list[list[str]] = []
        for row in reader:
            cleaned = [unicodedata.normalize("NFKC", c).strip() for c in row]
            if any(c for c in cleaned):
                raw_rows.append(cleaned)

        if not raw_rows:
            warnings.append("CSV file appears to be empty.")
            return DocumentRepresentation(
                source_format="csv",
                filename=filename,
                full_text="",
                pages=[""],
                blocks=[],
                tables=[],
                all_rows=[],
                coordinates_available=False,
                language_hint="unknown",
                has_rtl=False,
                parse_warnings=warnings,
                page_count=1,
            )

        # Detect header row
        headers: list[str] = []
        data_rows: list[list[str]] = []

        if _is_header_row(raw_rows[0]):
            headers = raw_rows[0]
            data_rows = raw_rows[1:]
        else:
            data_rows = raw_rows

        table = DocumentTable(
            table_id="t0",
            page=0,
            headers=headers,
            rows=data_rows,
            raw_rows=raw_rows,
        )

        # Build flat representation
        all_rows: list[str] = []
        blocks: list[DocumentBlock] = []
        block_counter = 0

        if headers:
            header_line = " | ".join(h for h in headers if h)
            all_rows.append(header_line)
            blocks.append(DocumentBlock(
                block_id=f"b{block_counter}",
                block_type="heading",
                raw_text=header_line,
                page=0,
            ))
            block_counter += 1

        for row in data_rows:
            row_line = " | ".join(c for c in row if c)
            if not row_line.strip():
                continue
            all_rows.append(row_line)
            blocks.append(DocumentBlock(
                block_id=f"b{block_counter}",
                block_type="text",
                raw_text=row_line,
                page=0,
            ))
            block_counter += 1

        full_text = "\n".join(all_rows)
        lang, has_rtl = _detect_language(full_text)

        return DocumentRepresentation(
            source_format="csv",
            filename=filename,
            full_text=full_text,
            pages=[full_text],
            blocks=blocks,
            tables=[table],
            all_rows=all_rows,
            coordinates_available=False,
            language_hint=lang,
            has_rtl=has_rtl,
            parse_warnings=warnings,
            page_count=1,
        )
