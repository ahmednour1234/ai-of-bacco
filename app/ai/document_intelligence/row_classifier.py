"""
app/ai/document_intelligence/row_classifier.py
==============================================
Stage 5 — Row Classification

Classifies each row inside a product region into one of the nine labels:
  product_row | product_description | table_header | metadata |
  total | payment_info | bank_info | notes | ignore

Primary path  : OpenAI LLM, batched (up to 50 rows per request).
Fallback path : Heuristic rules derived from existing ProductExtractionService
                logic (keyword scoring + numeric pattern detection).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.config import get_settings
from app.schemas.document_representation import (
    ROW_CLASS_LABELS,
    REVIEW_CONFIDENCE_THRESHOLD,
    ClassifiedRow,
    DocumentRegion,
)

logger = logging.getLogger(__name__)

# ── Heuristic patterns (mirrors ProductExtractionService heuristics) ──────────

_TOTAL_RE = re.compile(
    r"(total|sub\s*total|grand\s*total|vat|gst|tax|discount|net\s*amount|"
    r"إجمالي|مجموع|ضريبة|خصم|صافي|المجموع)",
    re.IGNORECASE,
)
_PAYMENT_RE = re.compile(
    r"(payment\s*term|due\s*date|bank\s+|شروط\s*الدفع|تاريخ\s*الاستحقاق|"
    r"تحويل\s*بنكي)",
    re.IGNORECASE,
)
_BANK_RE = re.compile(
    r"(iban|swift|account\s*(no|number)|رقم\s*الحساب|آيبان|سويفت)",
    re.IGNORECASE,
)
_NOTES_RE = re.compile(
    r"^(note[s]?|terms?|conditions?|remarks?|ملاحظ|شروط])\b",
    re.IGNORECASE,
)
_HEADER_WORDS = frozenset({
    "description", "item", "product", "qty", "quantity", "unit", "price",
    "amount", "total", "no", "ref", "code", "part", "model", "brand",
    "وصف", "صنف", "منتج", "كمية", "وحدة", "سعر", "مبلغ", "إجمالي", "رقم",
})
_NUMBER_RE = re.compile(r"\b\d+([.,/]\d+)?\s*(mm|cm|m|kg|g|pcs|units?|pc|nos?|مل|سم|كج|قطعة)?\b", re.IGNORECASE)
_PRICE_RE = re.compile(r"(SAR|AED|USD|EUR|KWD|ريال|درهم|دولار|€|\$)?\s*\d+([.,]\d+)?", re.IGNORECASE)

_PRODUCT_KEYWORDS = frozenset({
    "pipe", "valve", "fitting", "cable", "wire", "pump", "motor", "panel",
    "switch", "socket", "bolt", "nut", "screw", "bracket", "filter", "sensor",
    "controller", "relay", "breaker", "conduit", "tray", "duct", "joint",
    "coupling", "adapter", "reducer", "elbow", "tee", "flange", "gasket",
    "seal", "bearing", "shaft", "gear", "belt", "pulley", "sprocket",
    "conveyor", "tank", "vessel", "heat", "exchanger", "compressor",
    "fan", "blower", "separator", "dryer", "boiler", "burner", "chiller",
    "coil", "transformer", "capacitor", "resistor", "fuse", "contactor",
    "inverter", "rectifier", "battery", "charger", "ups", "light", "lamp",
    "tube", "rod", "sheet", "plate", "bar", "beam", "angle", "channel",
    "roof", "floor", "wall", "door", "window", "paint", "primer", "sealant",
    "adhesive", "grease", "oil", "lubricant",
    # Arabic
    "أنبوب", "صمام", "كابل", "سلك", "مضخة", "محرك", "لوحة", "مفتاح",
    "برغي", "صمولة", "مرشح", "حساس", "تحكم", "مكثف", "خزان", "مبادل",
    "ضاغط", "مروحة", "محول", "بطارية", "لمبة", "أنبوبة", "لوح", "دهان",
})


def _heuristic_classify_row(text: str, position: int, region_type: str) -> tuple[str, float]:
    """
    Classify a single row text using heuristics.
    Returns (label, confidence).
    """
    stripped = text.strip()
    lower = stripped.lower()
    words = re.findall(r"\w+", lower)

    if not stripped:
        return "ignore", 1.0

    # Header detection: mostly known header words, low numeric content
    header_word_count = sum(1 for w in words if w in _HEADER_WORDS)
    numeric_count = len(re.findall(r"\b\d+\b", stripped))

    if header_word_count >= 2 and numeric_count <= 1 and len(words) <= 12:
        return "table_header", 0.85

    # Total / subtotal
    if _TOTAL_RE.search(stripped):
        return "total", 0.85

    # Bank info
    if _BANK_RE.search(stripped):
        return "bank_info", 0.88

    # Payment info
    if _PAYMENT_RE.search(stripped):
        return "payment_info", 0.82

    # Notes
    if _NOTES_RE.match(stripped):
        return "notes", 0.78

    # Product row scoring
    score = 0

    # Item number prefix pattern: "17 ITEM NAME ..."
    if re.match(r"^\d+\s+\w", stripped):
        score += 3

    # Product keyword hits
    product_kw_hits = sum(1 for w in words if w in _PRODUCT_KEYWORDS)
    if product_kw_hits >= 2:
        score += 3
    elif product_kw_hits == 1:
        score += 1

    # Dimension/spec patterns
    if _NUMBER_RE.search(stripped):
        score += 2

    # Price pattern
    if _PRICE_RE.search(stripped):
        score += 1

    # Length signal: short lines (<3 words) are likely meta or description
    if len(words) < 3 and not re.search(r"\d", stripped):
        return "metadata", 0.60

    PRODUCT_THRESHOLD = 3
    if score >= PRODUCT_THRESHOLD:
        confidence = min(0.99, 0.55 + score * 0.08)
        return "product_row", confidence

    # Short descriptive text following a product row might be product_description
    if region_type in ("product_table", "product_list") and len(words) >= 2:
        return "product_description", 0.55

    return "ignore", 0.60


# ── LLM prompt ────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a document row classifier. Classify each row into one of these labels:
  product_row, product_description, table_header, metadata, total, payment_info, bank_info, notes, ignore

- product_row: a line describing an item/product/material with code/name/spec (often has qty, price, unit)
- product_description: a continuation line describing the product above it (no price/qty)
- table_header: column header row (Description, Qty, Unit, Price, etc.)
- metadata: document reference, date, customer name, project name
- total: subtotal, total, VAT, discount, net amounts
- payment_info: payment terms, due dates, bank transfer instructions
- bank_info: IBAN, SWIFT, account numbers
- notes: free text remarks, disclaimers, warranty, terms & conditions
- ignore: blank, page number, separator, watermark

Respond ONLY with valid JSON:
{
  "rows": [
    {"row_index": 0, "label": "...", "confidence": 0.0-1.0}
  ]
}
"""

_LLM_BATCH_SIZE = 50  # max rows per LLM call


async def _llm_classify_rows(
    rows: list[str],
    region_type: str,
) -> list[tuple[str, float]] | None:
    """
    Classify rows using LLM.
    Returns list of (label, confidence) per row, or None on failure.
    """
    settings = get_settings()
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    model = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")

    if not api_key or api_key.startswith("sk-placeholder"):
        return None

    try:
        from openai import AsyncOpenAI  # type: ignore
        client = AsyncOpenAI(api_key=api_key)

        # Build numbered row list
        numbered = "\n".join(f"{i}: {row[:200]}" for i, row in enumerate(rows))
        user_content = f"Region type: {region_type}\n\nRows:\n{numbered}"

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=1024,
        )

        raw_json = response.choices[0].message.content or "{}"
        data = json.loads(raw_json)

        results: dict[int, tuple[str, float]] = {}
        for item in data.get("rows", []):
            idx = int(item.get("row_index", -1))
            label = item.get("label", "ignore")
            if label not in ROW_CLASS_LABELS:
                label = "ignore"
            conf = float(item.get("confidence", 0.7))
            if 0 <= idx < len(rows):
                results[idx] = (label, conf)

        return [(results.get(i, ("ignore", 0.6))) for i in range(len(rows))]

    except Exception as exc:
        logger.warning("LLM row classification failed (%s), falling back to heuristics.", exc)
        return None


# ── Public API ────────────────────────────────────────────────────────────────

class RowClassifier:
    """
    Stage 5 of the universal extraction pipeline.
    Classifies rows within a product region into granular labels.
    """

    async def classify(self, region: DocumentRegion) -> list[ClassifiedRow]:
        """
        Classify all rows in the region text.
        Collects rows from tables (joined cells) and blocks.
        """
        rows: list[str] = []

        # Flatten tables
        for tbl in region.tables:
            if tbl.headers:
                rows.append(" | ".join(tbl.headers))
            for row in tbl.rows:
                rows.append(" | ".join(cell for cell in row if cell))

        # Flatten blocks
        for block in region.blocks:
            for line in block.raw_text.splitlines():
                line = line.strip()
                if line:
                    rows.append(line)

        if not rows:
            return []

        return await self._classify_rows(rows, region.region_type)

    async def _classify_rows(
        self, rows: list[str], region_type: str
    ) -> list[ClassifiedRow]:
        classified: list[ClassifiedRow] = []

        # Process in batches (LLM has token limits)
        for batch_start in range(0, len(rows), _LLM_BATCH_SIZE):
            batch = rows[batch_start: batch_start + _LLM_BATCH_SIZE]

            llm_results = await _llm_classify_rows(batch, region_type)
            source = "llm" if llm_results is not None else "heuristic"

            for i, row_text in enumerate(batch):
                global_idx = batch_start + i
                if llm_results is not None:
                    label, confidence = llm_results[i]
                else:
                    label, confidence = _heuristic_classify_row(
                        row_text, global_idx, region_type
                    )

                needs_review = confidence < REVIEW_CONFIDENCE_THRESHOLD
                classified.append(ClassifiedRow(
                    row_index=global_idx,
                    raw_text=row_text,
                    label=label,
                    confidence=confidence,
                    needs_review=needs_review,
                    source=source,
                ))

        return classified
