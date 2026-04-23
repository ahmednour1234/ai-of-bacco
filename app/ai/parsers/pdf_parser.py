"""
app/ai/parsers/pdf_parser.py
============================
PDF → DocumentRepresentation

Strategy:
1. Try pdfplumber for layout-aware extraction (tables + blocks + bboxes).
2. Fall back to pypdf for text-only extraction if pdfplumber is unavailable.

Arabic detection: unicode range 0x0600–0x06FF.
"""

from __future__ import annotations

import io
import re
import unicodedata
from typing import Optional, TYPE_CHECKING

from app.ai.interfaces.base_parser import BaseParser
from app.schemas.document_representation import (
    BoundingBox,
    DocumentBlock,
    DocumentRepresentation,
    DocumentTable,
)

if TYPE_CHECKING:
    pass

# These are optional dependencies — handle gracefully if not installed
try:
    import pdfplumber  # type: ignore
    _PDFPLUMBER_AVAILABLE = True
except ImportError:
    _PDFPLUMBER_AVAILABLE = False

try:
    from pypdf import PdfReader  # type: ignore
    _PYPDF_AVAILABLE = True
except ImportError:
    _PYPDF_AVAILABLE = False

# Arabic unicode block
_ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")


def _detect_language(text: str) -> tuple[str, bool]:
    """
    Return (language_hint, has_rtl).
    language_hint: "ar" | "en" | "mixed" | "unknown"
    """
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


def _clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    # Normalize unicode, collapse whitespace
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


class PDFParser(BaseParser):
    """
    Parse a PDF file into a DocumentRepresentation.
    Uses pdfplumber when available (preferred for layout extraction),
    falls back to pypdf (text only).
    """

    async def parse(self, file_bytes: bytes, filename: str) -> dict:
        """
        Returns a dict with key "representation" → DocumentRepresentation.
        Shape matches DocumentRepresentation attributes for easy unpacking.
        """
        rep = await self._parse_to_representation(file_bytes, filename)
        return {"representation": rep}

    async def _parse_to_representation(
        self, file_bytes: bytes, filename: str
    ) -> DocumentRepresentation:
        if _PDFPLUMBER_AVAILABLE:
            try:
                return self._parse_with_pdfplumber(file_bytes, filename)
            except Exception:
                pass  # fall through to pypdf
        if _PYPDF_AVAILABLE:
            return self._parse_with_pypdf(file_bytes, filename)
        raise RuntimeError(
            "Neither pdfplumber nor pypdf is available. "
            "Install at least one: pip install pdfplumber or pypdf"
        )

    # ── pdfplumber path ───────────────────────────────────────────────────────

    def _parse_with_pdfplumber(
        self, file_bytes: bytes, filename: str
    ) -> DocumentRepresentation:
        import pdfplumber  # type: ignore  # noqa: F811

        pages_text: list[str] = []
        blocks: list[DocumentBlock] = []
        tables: list[DocumentTable] = []
        all_rows: list[str] = []
        warnings: list[str] = []
        block_counter = 0
        table_counter = 0

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            page_count = len(pdf.pages)
            for page_idx, page in enumerate(pdf.pages):
                page_tables = page.find_tables()
                extracted_table_bboxes: list[tuple[float, float, float, float]] = []

                # ── Tables first ──────────────────────────────────────────
                for tbl in page_tables:
                    raw_data = tbl.extract()
                    if not raw_data:
                        continue

                    tbl_bbox = tbl.bbox  # (x0, top, x1, bottom)
                    extracted_table_bboxes.append(tbl_bbox)

                    # Determine header row: first non-empty row
                    headers: list[str] = []
                    data_rows: list[list[str]] = []
                    for i, row in enumerate(raw_data):
                        cleaned = [_clean_text(str(c) if c is not None else "") for c in row]
                        if not any(cleaned):
                            continue
                        if not headers:
                            headers = cleaned
                        else:
                            data_rows.append(cleaned)
                        all_rows.append(" | ".join(c for c in cleaned if c))

                    tables.append(DocumentTable(
                        table_id=f"t{table_counter}",
                        page=page_idx,
                        headers=headers,
                        rows=data_rows,
                        raw_rows=raw_data,
                        bbox=BoundingBox(
                            x0=tbl_bbox[0], y0=tbl_bbox[1],
                            x1=tbl_bbox[2], y1=tbl_bbox[3],
                            page=page_idx,
                        ),
                        confidence=1.0,
                    ))
                    table_counter += 1

                # ── Non-table text blocks ─────────────────────────────────
                page_text_parts: list[str] = []
                try:
                    words = page.extract_words(keep_blank_chars=False, x_tolerance=3, y_tolerance=3)
                except Exception:
                    words = []

                # Group words into lines by y-coordinate
                lines_by_y: dict[int, list[dict]] = {}
                for w in words:
                    # Check if this word falls inside a table bbox
                    in_table = any(
                        tb[0] <= w["x0"] <= tb[2] and tb[1] <= w["top"] <= tb[3]
                        for tb in extracted_table_bboxes
                    )
                    if in_table:
                        continue
                    y_key = round(w["top"] / 5) * 5  # 5-pt buckets
                    lines_by_y.setdefault(y_key, []).append(w)

                for y_key in sorted(lines_by_y):
                    line_words = sorted(lines_by_y[y_key], key=lambda w: w["x0"])
                    line_text = _clean_text(" ".join(w["text"] for w in line_words))
                    if not line_text:
                        continue
                    first_word = line_words[0]
                    last_word = line_words[-1]
                    bbox = BoundingBox(
                        x0=first_word["x0"], y0=first_word["top"],
                        x1=last_word["x1"], y1=last_word["bottom"],
                        page=page_idx,
                    )
                    blocks.append(DocumentBlock(
                        block_id=f"b{block_counter}",
                        block_type="text",
                        raw_text=line_text,
                        page=page_idx,
                        bbox=bbox,
                    ))
                    block_counter += 1
                    page_text_parts.append(line_text)
                    all_rows.append(line_text)

                page_text = "\n".join(page_text_parts)
                pages_text.append(page_text)

                if not page_text and not any(t.page == page_idx for t in tables):
                    warnings.append(f"Page {page_idx + 1}: no extractable text found.")

        full_text = "\n\n".join(p for p in pages_text if p)
        lang, has_rtl = _detect_language(full_text)

        return DocumentRepresentation(
            source_format="pdf",
            filename=filename,
            full_text=full_text,
            pages=pages_text,
            blocks=blocks,
            tables=tables,
            all_rows=all_rows,
            coordinates_available=True,
            language_hint=lang,
            has_rtl=has_rtl,
            parse_warnings=warnings,
            page_count=page_count,
        )

    # ── pypdf fallback path ───────────────────────────────────────────────────

    def _parse_with_pypdf(
        self, file_bytes: bytes, filename: str
    ) -> DocumentRepresentation:
        from pypdf import PdfReader  # type: ignore  # noqa: F811

        warnings: list[str] = ["Parsed with pypdf (text-only, no layout information)."]
        reader = PdfReader(io.BytesIO(file_bytes))
        pages_text: list[str] = []
        all_rows: list[str] = []
        blocks: list[DocumentBlock] = []
        block_counter = 0

        for page_idx, page in enumerate(reader.pages):
            try:
                raw = page.extract_text() or ""
            except Exception:
                raw = ""
                warnings.append(f"Page {page_idx + 1}: text extraction failed.")

            page_text = _clean_text(raw)
            pages_text.append(page_text)

            for line in page_text.splitlines():
                line = line.strip()
                if line:
                    all_rows.append(line)
                    blocks.append(DocumentBlock(
                        block_id=f"b{block_counter}",
                        block_type="text",
                        raw_text=line,
                        page=page_idx,
                    ))
                    block_counter += 1

        full_text = "\n\n".join(p for p in pages_text if p)
        lang, has_rtl = _detect_language(full_text)

        return DocumentRepresentation(
            source_format="pdf",
            filename=filename,
            full_text=full_text,
            pages=pages_text,
            blocks=blocks,
            tables=[],
            all_rows=all_rows,
            coordinates_available=False,
            language_hint=lang,
            has_rtl=has_rtl,
            parse_warnings=warnings,
            page_count=len(reader.pages),
        )
