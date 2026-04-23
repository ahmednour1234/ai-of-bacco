"""
app/ai/document_intelligence/region_detector.py
===============================================
Stage 4 — Region Detection

Splits the document into labelled regions:
  product_table   → a table containing product rows
  product_list    → a non-tabular block with product-like lines
  document_header → title / company info at the top
  section_header  → sub-section headings
  totals_block    → subtotals, VAT, grand total
  payment_info    → payment terms / due date / bank transfer instructions
  bank_info       → IBAN, account number, SWIFT codes
  notes           → free-text notes / terms & conditions
  metadata        → document date, reference, customer info
  ignore          → blank lines, page numbers, watermarks

Primary path  : OpenAI LLM receiving block/table summaries.
Fallback path : Heuristics using pattern matching.
"""

from __future__ import annotations

import json
import logging
import re
import uuid

from app.core.config import get_settings
from app.schemas.document_representation import (
    REGION_TYPE_LABELS,
    DetectionResult,
    DocumentBlock,
    DocumentRegion,
    DocumentRepresentation,
    DocumentTable,
)

logger = logging.getLogger(__name__)

# ── Heuristic patterns ────────────────────────────────────────────────────────

_TOTALS_PATTERNS = re.compile(
    r"(grand\s*total|sub\s*total|subtotal|vat|gst|tax|discount|الإجمالي|"
    r"مجموع|ضريبة|خصم|صافي)",
    re.IGNORECASE,
)
_PAYMENT_PATTERNS = re.compile(
    r"(payment\s*term|due\s*date|bank\s*transfer|شروط\s*الدفع|تاريخ\s*الاستحقاق|"
    r"تحويل\s*بنكي|cheque|check|wire\s*transfer)",
    re.IGNORECASE,
)
_BANK_PATTERNS = re.compile(
    r"(iban|swift|account\s*no|account\s*number|رقم\s*الحساب|آيبان|"
    r"رمز\s*السويفت|bic\b|sort\s*code)",
    re.IGNORECASE,
)
_NOTES_PATTERNS = re.compile(
    r"(note[s]?|terms?\s*(and|&)\s*conditions?|disclaimer|warranty|ملاحظ|"
    r"شروط|ضمان|تنبيه)",
    re.IGNORECASE,
)
_HEADER_PATTERNS = re.compile(
    r"(invoice|quotation|price\s*list|purchase\s*order|receipt|delivery|"
    r"فاتورة|عرض\s*سعر|قائمة|أمر\s*شراء)",
    re.IGNORECASE,
)
_PRODUCT_HEADER_WORDS = frozenset({
    "description", "item", "product", "material", "code", "qty", "quantity",
    "unit", "price", "amount", "rate", "total", "no", "ref", "model", "brand",
    "وصف", "صنف", "منتج", "كمية", "وحدة", "سعر", "مبلغ", "إجمالي", "رقم",
})


def _table_looks_like_products(table: DocumentTable) -> bool:
    """Return True if this table's headers suggest it holds product rows."""
    headers_lower = " ".join(h.lower() for h in table.headers)
    hit_count = sum(1 for w in _PRODUCT_HEADER_WORDS if w in headers_lower)
    if hit_count >= 2:
        return True
    # Fallback: does any column in first 5 rows have numeric values?
    if table.rows:
        for col_idx in range(len(table.headers)):
            col_vals = [
                row[col_idx] for row in table.rows[:5]
                if col_idx < len(row) and row[col_idx].strip()
            ]
            numeric = sum(
                1 for v in col_vals
                if re.fullmatch(r"[-+]?\d+([.,/]\d+)?", v.replace(",", "").replace(" ", ""))
            )
            if col_vals and numeric / len(col_vals) > 0.5:
                return True
    return False


def _heuristic_detect_regions(
    doc: DocumentRepresentation,
    detection: DetectionResult,
) -> list[DocumentRegion]:
    regions: list[DocumentRegion] = []
    region_counter = 0

    def _new_region_id() -> str:
        nonlocal region_counter
        rid = f"r{region_counter}"
        region_counter += 1
        return rid

    # ── Classify tables ──────────────────────────────────────────────────────
    for table in doc.tables:
        if _table_looks_like_products(table):
            region_type = "product_table"
        else:
            # Check if totals or metadata table
            combined = " | ".join(table.headers) + " " + " ".join(
                " | ".join(row) for row in table.rows[:3]
            )
            if _TOTALS_PATTERNS.search(combined):
                region_type = "totals_block"
            elif _BANK_PATTERNS.search(combined):
                region_type = "bank_info"
            elif _PAYMENT_PATTERNS.search(combined):
                region_type = "payment_info"
            else:
                region_type = "metadata"

        raw_text = " | ".join(table.headers) + "\n" + "\n".join(
            " | ".join(row) for row in table.rows
        )
        regions.append(DocumentRegion(
            region_id=_new_region_id(),
            region_type=region_type,
            tables=[table],
            raw_text=raw_text,
            page=table.page,
            confidence=0.75,
        ))

    # ── Classify blocks ──────────────────────────────────────────────────────
    # Group consecutive blocks with same classification into one region
    current_type: Optional[str] = None
    current_blocks: list[DocumentBlock] = []
    current_text_parts: list[str] = []

    def _flush_blocks() -> None:
        if not current_blocks or current_type is None:
            return
        regions.append(DocumentRegion(
            region_id=_new_region_id(),
            region_type=current_type,
            blocks=list(current_blocks),
            raw_text="\n".join(current_text_parts),
            page=current_blocks[0].page,
            confidence=0.65,
        ))

    for i, block in enumerate(doc.blocks):
        text = block.raw_text.strip()
        if not text:
            continue

        # Classify block
        if i == 0 or (i < 3 and _HEADER_PATTERNS.search(text)):
            btype = "document_header"
        elif _BANK_PATTERNS.search(text):
            btype = "bank_info"
        elif _PAYMENT_PATTERNS.search(text):
            btype = "payment_info"
        elif _TOTALS_PATTERNS.search(text):
            btype = "totals_block"
        elif _NOTES_PATTERNS.search(text):
            btype = "notes"
        else:
            btype = "product_list"  # assume product-like by default

        if btype != current_type:
            _flush_blocks()
            current_type = btype
            current_blocks.clear()
            current_text_parts.clear()

        current_blocks.append(block)
        current_text_parts.append(text)

    _flush_blocks()

    # If no product regions at all but document has products, mark first region
    if detection.contains_products and not any(r.is_product_region for r in regions):
        if regions:
            regions[0].region_type = "product_list"

    return regions


# ── LLM prompt ────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a document structure analyst. Given summaries of document blocks/tables, label each one.

Valid region types:
  product_table, product_list, document_header, section_header,
  totals_block, payment_info, bank_info, notes, metadata, ignore

Respond ONLY with valid JSON:
{
  "regions": [
    {"block_id": "...", "region_type": "...", "confidence": 0.0-1.0}
  ]
}

Rules:
- A table with columns like description/qty/price/amount → product_table
- A block listing product names with codes → product_list
- Company name, document title, document number, date → document_header or metadata
- Lines with "Total", "VAT", "Subtotal" → totals_block
- Bank account, IBAN, SWIFT → bank_info
- Payment terms, due date → payment_info
- Free text notes, disclaimers → notes
- Page numbers, watermarks → ignore
"""


async def _llm_detect_regions(
    doc: DocumentRepresentation,
    detection: DetectionResult,
) -> Optional[list[DocumentRegion]]:
    settings = get_settings()
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    model = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")

    if not api_key or api_key.startswith("sk-placeholder"):
        return None

    try:
        from openai import AsyncOpenAI  # type: ignore
        client = AsyncOpenAI(api_key=api_key)

        # Build a compact summary of all blocks and tables
        summary_parts: list[str] = []
        for tbl in doc.tables:
            summary_parts.append(
                f'[TABLE id={tbl.table_id} page={tbl.page}] headers={tbl.headers[:8]} '
                f'rows_preview={tbl.rows[:2]}'
            )
        for block in doc.blocks[:60]:  # limit to first 60 blocks
            summary_parts.append(f'[BLOCK id={block.block_id} page={block.page}] {block.raw_text[:120]}')

        summary = "\n".join(summary_parts)[:4000]

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"Document type: {detection.document_type_guess}\n\n{summary}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=1024,
        )

        raw_json = response.choices[0].message.content or "{}"
        data = json.loads(raw_json)

        # Build a lookup: block_id / table_id → region_type
        label_map: dict[str, tuple[str, float]] = {}
        for item in data.get("regions", []):
            bid = str(item.get("block_id", ""))
            region_type = item.get("region_type", "ignore")
            if region_type not in REGION_TYPE_LABELS:
                region_type = "ignore"
            confidence = float(item.get("confidence", 0.8))
            label_map[bid] = (region_type, confidence)

        # ── Build DocumentRegion objects ──────────────────────────────────────
        regions: list[DocumentRegion] = []
        region_counter = 0

        # Tables
        for tbl in doc.tables:
            rtype, conf = label_map.get(tbl.table_id, ("product_table", 0.7))
            raw_text = " | ".join(tbl.headers) + "\n" + "\n".join(
                " | ".join(row) for row in tbl.rows
            )
            regions.append(DocumentRegion(
                region_id=f"r{region_counter}",
                region_type=rtype,
                tables=[tbl],
                raw_text=raw_text,
                page=tbl.page,
                confidence=conf,
                metadata={"source": "llm", "model": model},
            ))
            region_counter += 1

        # Group blocks by LLM-assigned type
        current_type: Optional[str] = None
        current_blocks: list[DocumentBlock] = []
        current_text: list[str] = []
        current_conf: float = 0.8

        def _flush() -> None:
            nonlocal region_counter
            if current_blocks and current_type:
                regions.append(DocumentRegion(
                    region_id=f"r{region_counter}",
                    region_type=current_type,
                    blocks=list(current_blocks),
                    raw_text="\n".join(current_text),
                    page=current_blocks[0].page,
                    confidence=current_conf,
                    metadata={"source": "llm", "model": model},
                ))
                region_counter += 1

        for block in doc.blocks:
            btype, bconf = label_map.get(block.block_id, ("product_list", 0.65))
            if btype != current_type:
                _flush()
                current_type = btype
                current_blocks.clear()
                current_text.clear()
                current_conf = bconf
            current_blocks.append(block)
            current_text.append(block.raw_text)

        _flush()
        return regions

    except Exception as exc:
        logger.warning("LLM region detection failed (%s), falling back to heuristics.", exc)
        return None


# ── Public API ────────────────────────────────────────────────────────────────

class RegionDetector:
    """
    Stage 4 of the universal extraction pipeline.
    Divides the document into labelled regions.
    """

    async def detect(
        self,
        doc: DocumentRepresentation,
        detection: DetectionResult,
    ) -> list[DocumentRegion]:
        result = await _llm_detect_regions(doc, detection)
        if result is None:
            result = _heuristic_detect_regions(doc, detection)
        return result
