"""
app/schemas/document_representation.py
=======================================
In-memory intermediate representation produced by the universal parsers.
Nothing in here is persisted to the database directly; the pipeline maps
these structures to ExtractionCandidate rows.

Hierarchy:
  DocumentRepresentation
    └─ pages: list[str]                  (raw text per page)
    └─ blocks: list[DocumentBlock]       (paragraphs, images, misc regions)
    └─ tables: list[DocumentTable]       (detected tabular data)
    └─ all_rows: list[str]               (flat line list, in reading order)

After detection / classification stages:
  DetectionResult       → Stage 3 output  (contains_products, type, language)
  DocumentRegion        → Stage 4 output  (labelled region of the document)
  ClassifiedRow         → Stage 5 output  (per-row label + confidence)
  ExtractionPipelineResult → final output of the universal pipeline
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Any


# ─────────────────────────────────────────────────────────────────────────────
# Low-level primitives produced by parsers
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class BoundingBox:
    """Normalized page coordinates (0-based, in points or pixels)."""
    x0: float
    y0: float
    x1: float
    y1: float
    page: int = 0

    def to_dict(self) -> dict[str, float | int]:
        return {"x0": self.x0, "y0": self.y0, "x1": self.x1, "y1": self.y1, "page": self.page}


@dataclass
class DocumentBlock:
    """
    A contiguous region of text in the document (paragraph, heading, caption …).
    For table cells: a DocumentTable is preferred; blocks are non-tabular regions.
    """
    block_id: str                          # stable identifier within the document
    block_type: str                        # "text" | "heading" | "image" | "table_caption" | "footer"
    raw_text: str
    page: int = 0
    bbox: Optional[BoundingBox] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentTable:
    """A detected table with header row(s) and data rows."""
    table_id: str
    page: int = 0
    headers: list[str] = field(default_factory=list)     # normalised column names
    rows: list[list[str]] = field(default_factory=list)  # data rows as list of strings
    raw_rows: list[list[Any]] = field(default_factory=list)  # raw cell values
    bbox: Optional[BoundingBox] = None
    confidence: float = 1.0
    sheet_name: Optional[str] = None   # for Excel multi-sheet documents


@dataclass
class DocumentRepresentation:
    """
    Normalised, format-agnostic view of an uploaded document.
    All parsers must produce this; downstream AI stages only consume this.
    """
    # --- Origin metadata ---
    source_format: str              # "pdf" | "image" | "excel" | "csv"
    filename: str

    # --- Content layers ---
    full_text: str                  # entire document text concatenated (for LLM context)
    pages: list[str] = field(default_factory=list)     # text per page (single-item list for images/excel)
    blocks: list[DocumentBlock] = field(default_factory=list)
    tables: list[DocumentTable] = field(default_factory=list)
    all_rows: list[str] = field(default_factory=list)  # flat, reading-order lines

    # --- Layout availability ---
    coordinates_available: bool = False

    # --- Language hints ---
    language_hint: str = "unknown"   # "ar" | "en" | "mixed" | "unknown"
    has_rtl: bool = False

    # --- Parser diagnostics ---
    parse_warnings: list[str] = field(default_factory=list)
    page_count: int = 1

    # ── convenience helpers ───────────────────────────────────────────────────

    def get_table_headers_summary(self, max_tables: int = 10) -> str:
        """Return a compact string of all tables' headers for LLM context."""
        parts: list[str] = []
        for t in self.tables[:max_tables]:
            if t.headers:
                parts.append(f"Table {t.table_id}: [{', '.join(t.headers[:10])}]")
        return "\n".join(parts) if parts else "(no structured tables detected)"

    def get_llm_context_snippet(self, max_chars: int = 3000) -> str:
        """
        Return a representative text sample for document-level LLM prompts.
        Prefers the first page + all table headers to stay within token budget.
        """
        first_page = self.pages[0] if self.pages else self.full_text[:1500]
        header_summary = self.get_table_headers_summary()
        snippet = f"[First page / beginning]\n{first_page[:2000]}\n\n[Table headers]\n{header_summary}"
        return snippet[:max_chars]


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3 – Document Detection output
# ─────────────────────────────────────────────────────────────────────────────

# Valid document type guesses returned by DocumentDetector
DOCUMENT_TYPE_GUESSES = frozenset({
    "quotation",
    "invoice",
    "price_list",
    "catalog",
    "packing_list",
    "purchase_order",
    "delivery_note",
    "receipt",
    "unknown",
})


@dataclass
class DetectionResult:
    """
    Output of DocumentDetector (Stage 3).
    Answers: does this document contain products?
    """
    contains_products: bool
    document_type_guess: str      # one of DOCUMENT_TYPE_GUESSES
    confidence: float             # 0.0 – 1.0
    reasoning: str                # natural-language explanation for auditability
    language: str                 # "ar" | "en" | "mixed" | "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)  # raw LLM response for debugging


# ─────────────────────────────────────────────────────────────────────────────
# Stage 4 – Region Detection output
# ─────────────────────────────────────────────────────────────────────────────

# All valid region type labels
REGION_TYPE_LABELS = frozenset({
    "product_table",
    "product_list",
    "document_header",
    "section_header",
    "totals_block",
    "payment_info",
    "bank_info",
    "notes",
    "metadata",
    "ignore",
})


@dataclass
class DocumentRegion:
    """
    Output of RegionDetector (Stage 4).
    A labelled area of the document containing one or more blocks/tables.
    """
    region_id: str
    region_type: str              # one of REGION_TYPE_LABELS
    blocks: list[DocumentBlock] = field(default_factory=list)
    tables: list[DocumentTable] = field(default_factory=list)
    confidence: float = 1.0
    raw_text: str = ""            # merged text from all blocks/tables in region
    page: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_product_region(self) -> bool:
        return self.region_type in {"product_table", "product_list"}


# ─────────────────────────────────────────────────────────────────────────────
# Stage 5 – Row Classification output
# ─────────────────────────────────────────────────────────────────────────────

# All valid row-level class labels
ROW_CLASS_LABELS = frozenset({
    "product_row",
    "product_description",
    "table_header",
    "metadata",
    "total",
    "payment_info",
    "bank_info",
    "notes",
    "ignore",
})

REVIEW_CONFIDENCE_THRESHOLD = 0.65  # rows below this are flagged for manual review


@dataclass
class ClassifiedRow:
    """
    Output of RowClassifier (Stage 5) per document row.
    """
    row_index: int
    raw_text: str
    label: str            # one of ROW_CLASS_LABELS
    confidence: float     # 0.0 – 1.0
    needs_review: bool = False
    source: str = "llm"   # "llm" | "heuristic"
    metadata: dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Final pipeline result
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ExtractionPipelineResult:
    """
    Final output of UniversalExtractionPipeline.
    Maps to ExtractionSession (session-level) + list[CandidateData] (row-level).
    """
    # Detection
    contains_products: bool
    document_type_guess: str
    detection_confidence: float
    language: str

    # Regions
    product_regions: list[DocumentRegion] = field(default_factory=list)
    ignored_regions: list[DocumentRegion] = field(default_factory=list)

    # Candidates (populated by ProductExtractor, same dataclass used by DB layer)
    # Type annotation kept as Any to avoid circular import with extraction.py
    candidates: list[Any] = field(default_factory=list)

    # Overall pipeline confidence (average of product candidates)
    overall_confidence: float = 0.0

    # Raw LLM responses stored for auditability and future fine-tuning
    detection_metadata: dict[str, Any] = field(default_factory=dict)
