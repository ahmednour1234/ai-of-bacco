"""
app/ai/parsers/universal_document_parser.py
===========================================
Format-agnostic entry point for document parsing.

Detection strategy:
1. Extension-based routing (primary).
2. Magic-bytes sniffing as confirmation / override for ambiguous extensions.

Supported formats:
  PDF   → PDFParser
  Image → ImageParser  (jpg, jpeg, png, gif, bmp, tiff, tif, webp)
  Excel → ExcelParser  (xlsx, xlsm, xls)
  CSV   → CSVParser    (csv, tsv, txt when delimiters are detected)

Raises UnprocessableException for truly unknown / unsupported types rather
than silently failing.
"""

from __future__ import annotations

from app.ai.interfaces.base_parser import BaseParser
from app.ai.parsers.csv_parser import CSVParser
from app.ai.parsers.excel_parser import ExcelParser
from app.ai.parsers.image_parser import ImageParser
from app.ai.parsers.pdf_parser import PDFParser
from app.core.exceptions import UnprocessableException
from app.schemas.document_representation import DocumentRepresentation

# Magic byte signatures (first N bytes of a file)
_MAGIC_PDF = b"%PDF"
_MAGIC_ZIP = b"PK\x03\x04"       # ZIP-based: xlsx, xlsm, docx, pptx …
_MAGIC_XLS_OLD = b"\xd0\xcf\x11\xe0"  # Compound Document (old .xls)

# Extension mappings
_PDF_EXTS = frozenset({"pdf"})
_IMAGE_EXTS = frozenset({"jpg", "jpeg", "png", "gif", "bmp", "tiff", "tif", "webp"})
_EXCEL_EXTS = frozenset({"xlsx", "xlsm", "xls"})
_CSV_EXTS = frozenset({"csv", "tsv"})
# .txt might be CSV-like — we probe content to decide
_TEXT_EXTS = frozenset({"txt"})


def _sniff_format(file_bytes: bytes) -> Optional[str]:
    """
    Return format hint from magic bytes: "pdf" | "excel" | "excel_old" | None.
    """
    if file_bytes[:4] == _MAGIC_PDF:
        return "pdf"
    if file_bytes[:4] == _MAGIC_ZIP:
        return "excel"          # xlsx / xlsm; could also be docx — extension still disambiguates
    if file_bytes[:4] == _MAGIC_XLS_OLD:
        return "excel_old"
    return None


class UniversalDocumentParser(BaseParser):
    """
    Route any uploaded document to the appropriate sub-parser based on
    filename extension + magic bytes confirmation.

    Returns a dict with key "representation" → DocumentRepresentation.
    """

    async def parse(self, file_bytes: bytes, filename: str) -> dict:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        magic = _sniff_format(file_bytes)

        representation = await self._route(file_bytes, filename, ext, magic)
        return {"representation": representation}

    async def _route(
        self,
        file_bytes: bytes,
        filename: str,
        ext: str,
        magic: Optional[str],
    ) -> DocumentRepresentation:
        # ── PDF ───────────────────────────────────────────────────────────────
        if ext in _PDF_EXTS or magic == "pdf":
            return await self._parse_pdf(file_bytes, filename)

        # ── Image ─────────────────────────────────────────────────────────────
        if ext in _IMAGE_EXTS:
            return await self._parse_image(file_bytes, filename)

        # ── Excel ─────────────────────────────────────────────────────────────
        if ext in _EXCEL_EXTS or magic in ("excel", "excel_old"):
            return await self._parse_excel(file_bytes, filename)

        # ── CSV / TSV ─────────────────────────────────────────────────────────
        if ext in _CSV_EXTS:
            return await self._parse_csv(file_bytes, filename)

        # ── Plain text — probe whether it looks like CSV or plain prose ───────
        if ext in _TEXT_EXTS:
            return await self._detect_and_parse_text(file_bytes, filename)

        # ── Unknown — try magic-bytes as last resort ──────────────────────────
        if magic == "pdf":
            return await self._parse_pdf(file_bytes, filename)
        if magic in ("excel", "excel_old"):
            return await self._parse_excel(file_bytes, filename)

        raise UnprocessableException(
            f"Unsupported file type '{ext or 'unknown'}'. "
            f"Accepted: PDF, JPEG, PNG, TIFF, WEBP, XLSX, XLS, CSV, TSV."
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    async def _parse_pdf(file_bytes: bytes, filename: str) -> DocumentRepresentation:
        result = await PDFParser().parse(file_bytes, filename)
        return result["representation"]

    @staticmethod
    async def _parse_image(file_bytes: bytes, filename: str) -> DocumentRepresentation:
        result = await ImageParser().parse(file_bytes, filename)
        return result["representation"]

    @staticmethod
    async def _parse_excel(file_bytes: bytes, filename: str) -> DocumentRepresentation:
        result = await ExcelParser().parse(file_bytes, filename)
        return result["representation"]

    @staticmethod
    async def _parse_csv(file_bytes: bytes, filename: str) -> DocumentRepresentation:
        result = await CSVParser().parse(file_bytes, filename)
        return result["representation"]

    async def _detect_and_parse_text(
        self, file_bytes: bytes, filename: str
    ) -> DocumentRepresentation:
        """
        For .txt files: try CSV parsing if the content looks tabular
        (multiple lines with a consistent delimiter); otherwise treat as plain text.
        """
        import csv as _csv

        try:
            text = file_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = file_bytes.decode("latin-1", errors="replace")

        sample = text[:4096]
        try:
            dialect = _csv.Sniffer().sniff(sample)
            # If sniff succeeded and delimiter is a printable char → treat as CSV
            if dialect.delimiter and dialect.delimiter.isprintable():
                return await self._parse_csv(file_bytes, filename)
        except _csv.Error:
            pass

        # Plain text fallback: import as a single-table CSV with one column
        return await self._parse_csv(file_bytes, filename)
