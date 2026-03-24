"""
app/ai/document_intelligence/product_extractor.py
=================================================
Stage 6 — Product Extraction

Takes classified product rows (and their adjacent description rows) from a
DocumentRegion and extracts structured product data.

Primary path  : OpenAI LLM with structured JSON output (batch by product rows).
Fallback path : Regex-based field extraction that mirrors the existing
                ProductExtractionService heuristics.

Output: list[CandidateData] — the same dataclass used by the DB persistence
layer (ExtractionCandidateRepository.bulk_create), extended with
region_id, page_number, and coordinates (via metadata field).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.config import get_settings
from app.schemas.document_representation import (
    REVIEW_CONFIDENCE_THRESHOLD,
    ClassifiedRow,
    DocumentRegion,
)
from app.schemas.extraction import CandidateData
from app.ai.normalization import QuantityParser, UnitNormalizer

logger = logging.getLogger(__name__)

# Module-level singletons (stateless, cheap to instantiate)
_unit_normalizer = UnitNormalizer()
_qty_parser = QuantityParser(enable_llm=False)

# ── Heuristic field extraction ────────────────────────────────────────────────

_QUANTITY_RE = re.compile(
    r"(?<!\w)(\d+(?:[.,]\d+)?)\s*"
    r"(pcs?|pieces?|units?|nos?|metres?|mtrs?|m\b|ft\b|kg\b|g\b|ltr?s?|"
    r"قطعة|قطع|متر|كيلو|لتر|عدد)",
    re.IGNORECASE,
)
_PRICE_RE = re.compile(
    r"(?:SAR|AED|USD|EUR|KWD|GBP|ريال|درهم|دولار|€|\$)?\s*"
    r"(\d{1,3}(?:[,\s]\d{3})*(?:\.\d{1,4})?)",
)
_UNIT_WORDS = re.compile(
    r"\b(pcs?|pieces?|units?|nos?|metres?|mtrs?|m\b|ft|kg|g\b|ltr?s?|"
    r"قطعة|قطع|متر|كيلو|لتر|عدد)\b",
    re.IGNORECASE,
)
_CATEGORY_MAP: dict[str, list[str]] = {
    "Plumbing": ["pipe", "valve", "fitting", "coupling", "elbow", "tee", "flange", "أنبوب", "صمام"],
    "Electrical": ["cable", "wire", "switch", "socket", "breaker", "fuse", "relay", "contactor", "كابل", "سلك", "مفتاح"],
    "Mechanical": ["pump", "motor", "bearing", "shaft", "gear", "belt", "fan", "compressor", "مضخة", "محرك"],
    "HVAC": ["chiller", "coil", "duct", "blower", "heat exchanger", "مكيف"],
    "Civil":  ["paint", "primer", "sealant", "adhesive", "beam", "rod", "plate", "دهان", "لحام"],
    "Instrumentation": ["sensor", "controller", "transmitter", "gauge", "حساس", "تحكم"],
    "Safety": ["fire", "extinguisher", "alarm", "detector", "حريق", "إنذار"],
}


def _guess_category(text: str) -> str | None:
    lower = text.lower()
    for category, keywords in _CATEGORY_MAP.items():
        if any(kw in lower for kw in keywords):
            return category
    return None


def _extract_quantity(text: str) -> tuple[float | None, str | None]:
    m = _QUANTITY_RE.search(text)
    if m:
        try:
            qty = float(m.group(1).replace(",", "."))
            unit = m.group(2)
            return qty, unit
        except ValueError:
            pass
    # Try standalone number at end of text
    m2 = re.search(r"(?<!\d)(\d+(?:\.\d+)?)\s*$", text)
    if m2:
        try:
            return float(m2.group(1)), None
        except ValueError:
            pass
    return None, None


def _extract_price(text: str) -> float | None:
    # Find last numeric-looking value (most likely the price in tabular rows)
    matches = _PRICE_RE.findall(text)
    if not matches:
        return None
    for raw in reversed(matches):
        cleaned = raw.replace(",", "").replace(" ", "")
        try:
            value = float(cleaned)
            if value > 0:
                return value
        except ValueError:
            continue
    return None


def _extract_unit(text: str) -> str | None:
    m = _UNIT_WORDS.search(text)
    return m.group(1) if m else None


def _heuristic_extract(row_text: str, description_text: str | None) -> dict[str, Any]:
    # Try QuantityParser first (more robust than the bare regex)
    qr = _qty_parser.parse(row_text)
    qty = qr.quantity
    raw_unit = qr.unit
    if qty is None:
        qty, raw_unit = _extract_quantity(row_text)

    normalized_unit = _unit_normalizer.canonical(raw_unit)
    price = _extract_price(row_text)
    if raw_unit is None:
        raw_unit = _extract_unit(row_text)
        if raw_unit is not None:
            normalized_unit = _unit_normalizer.canonical(raw_unit)

    category = _guess_category(row_text)

    # Total: try to compute if we have both qty and price
    total: float | None = None
    if qty is not None and price is not None:
        total = round(qty * price, 4)

    # Product name: remove known numeric / unit / price tokens to get name fragment
    name = re.sub(r"^\d+[\.\)]\s*", "", row_text.strip())  # remove leading index
    name = re.sub(_QUANTITY_RE, "", name).strip()
    name = re.sub(_PRICE_RE, "", name).strip()
    name = re.sub(r"\s{2,}", " ", name).strip(" |,;")

    if len(name) > 255:
        name = name[:252] + "..."

    # Extract model code
    model_code: str | None = None
    _model_re = re.compile(r"\b[A-Z0-9]{3,}(?:[-/][A-Z0-9]+)*\b")
    m_code = _model_re.search(row_text)
    if m_code:
        model_code = m_code.group(0)

    return {
        "product_name": name or row_text[:120],
        "description": description_text,
        "quantity": qty,
        "unit": normalized_unit or raw_unit,
        "raw_unit": raw_unit,
        "normalized_unit": normalized_unit,
        "price": price,
        "brand": None,
        "category": category,
        "model_code": model_code,
        "total": total,
    }


# ── LLM extraction ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a product data extraction expert. Given product rows from a business document,
extract structured product information.

For each product, return:
{
  "row_index": <int>,
  "product_name": "<name as written in document, preserve Arabic if present>",
  "description": "<additional description, null if none>",
  "quantity": <number or null>,
  "unit": "<unit string or null>",
  "price": <number or null>,
  "brand": "<brand/manufacturer or null>",
  "category": "<product category or null>",
  "confidence": <0.0-1.0>
}

Rules:
- Preserve Arabic product names exactly as written; do not translate.
- Do not invent data. If a field is not present, set null.
- quantity and price must be numbers, not strings.
- If a row is a continuation description of the previous product, return description only.
- Table header rows should be skipped (do not include in output).

Respond ONLY with valid JSON:
{"products": [ ... ]}
"""

_EXTRACT_BATCH_SIZE = 30  # product rows per LLM call


async def _llm_extract(
    product_rows: list[tuple[int, str]],         # (original_row_index, text)
    description_map: dict[int, str],             # row_index → merged description text
    few_shot_examples: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]] | None:
    settings = get_settings()
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    model = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")

    if not api_key or api_key.startswith("sk-placeholder"):
        return None

    try:
        from openai import AsyncOpenAI  # type: ignore
        client = AsyncOpenAI(api_key=api_key)

        rows_text = "\n".join(
            f'{i}: {text[:300]}' + (f' [desc: {description_map[idx][:100]}]' if idx in description_map else "")
            for i, (idx, text) in enumerate(product_rows)
        )

        messages: list[dict[str, str]] = [{"role": "system", "content": _SYSTEM_PROMPT}]

        # Add few-shot correction examples if available
        if few_shot_examples:
            example_text = "\n".join(
                f'Input: {ex["normalized_text"]}\n'
                f'Output: name={ex.get("correct_name","")}, '
                f'category={ex.get("correct_category","")}, '
                f'brand={ex.get("correct_brand","")}'
                for ex in few_shot_examples[:5]
            )
            messages.append({
                "role": "user",
                "content": f"Here are some correction examples to guide extraction:\n{example_text}",
            })
            messages.append({"role": "assistant", "content": "Understood. I will apply these patterns."})

        messages.append({"role": "user", "content": f"Product rows:\n{rows_text}"})

        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=2048,
        )

        raw_json = response.choices[0].message.content or "{}"
        data = json.loads(raw_json)
        return data.get("products", [])

    except Exception as exc:
        logger.warning("LLM product extraction failed (%s), falling back to heuristics.", exc)
        return None


# ── Public API ────────────────────────────────────────────────────────────────

class ProductExtractor:
    """
    Stage 6 of the universal extraction pipeline.
    Extracts structured products from classified rows in a product region.
    """

    def __init__(
        self,
        correction_examples: list[dict[str, Any]] | None = None,
    ) -> None:
        self._correction_examples = correction_examples or []

    async def extract(
        self,
        region: DocumentRegion,
        classified_rows: list[ClassifiedRow],
    ) -> list[CandidateData]:
        """
        Extract CandidateData from product_row entries in classified_rows.
        Adjacent product_description rows are merged into the preceding product.
        """
        # Separate product rows and description rows
        product_row_indices: list[int] = []
        description_row_indices: list[int] = []

        for cr in classified_rows:
            if cr.label == "product_row":
                product_row_indices.append(cr.row_index)
            elif cr.label == "product_description":
                description_row_indices.append(cr.row_index)

        if not product_row_indices:
            return []

        # Map row_index → ClassifiedRow for quick lookup
        row_lookup: dict[int, ClassifiedRow] = {cr.row_index: cr for cr in classified_rows}

        # Merge description rows: each description attaches to the nearest preceding product_row
        description_map: dict[int, str] = {}
        for desc_idx in description_row_indices:
            # Find the closest preceding product row
            preceding = max(
                (pi for pi in product_row_indices if pi < desc_idx),
                default=None,
            )
            if preceding is not None:
                text = row_lookup[desc_idx].raw_text
                description_map[preceding] = (
                    description_map.get(preceding, "") + " " + text
                ).strip()

        product_rows = [
            (idx, row_lookup[idx].raw_text)
            for idx in product_row_indices
            if idx in row_lookup
        ]

        # Get coordinates JSONB from region blocks/tables (if available)
        # We build a position->bbox mapping via block text matching (best effort)
        bbox_map: dict[int, dict | None] = self._build_bbox_map(region, classified_rows)

        # Process in batches
        candidates: list[CandidateData] = []
        global_position = 0

        for batch_start in range(0, len(product_rows), _EXTRACT_BATCH_SIZE):
            batch = product_rows[batch_start: batch_start + _EXTRACT_BATCH_SIZE]
            batch_descs = {idx: description_map[idx] for idx, _ in batch if idx in description_map}

            llm_results = await _llm_extract(batch, batch_descs, self._correction_examples)

            for local_i, (row_idx, row_text) in enumerate(batch):
                if llm_results is not None and local_i < len(llm_results):
                    data = llm_results[local_i]
                    confidence = float(data.get("confidence", 0.8))
                    source = "llm"
                else:
                    data = _heuristic_extract(row_text, batch_descs.get(row_idx))
                    confidence = 0.60
                    source = "heuristic"

                needs_review = confidence < REVIEW_CONFIDENCE_THRESHOLD

                # Build metadata dict with region/coordinate info
                meta: dict[str, Any] = {
                    "region_id": region.region_id,
                    "region_type": region.region_type,
                    "page_number": region.page,
                    "classification_source": source,
                }
                if bbox_map.get(row_idx):
                    meta["coordinates"] = bbox_map[row_idx]

                candidate = CandidateData(
                    raw_text=row_text,
                    predicted_label="product",
                    confidence=confidence,
                    position=global_position,
                    product_name=_safe_str(data.get("product_name")),
                    description=_safe_str(data.get("description") or batch_descs.get(row_idx)),
                    quantity=_safe_float(data.get("quantity")),
                    unit=_safe_str(data.get("unit")),
                    brand=_safe_str(data.get("brand")),
                    category=_safe_str(data.get("category")),
                    price=_safe_float(data.get("price")),
                    needs_review=needs_review,
                    # Store region/coord metadata in the extra field
                    extra_metadata=meta,
                    # Extended normalization fields
                    raw_unit=_safe_str(data.get("raw_unit")),
                    normalized_unit=_safe_str(data.get("normalized_unit")),
                    model_code=_safe_str(data.get("model_code")),
                    total=_safe_float(data.get("total")),
                )
                candidates.append(candidate)
                global_position += 1

        return candidates

    @staticmethod
    def _build_bbox_map(
        region: DocumentRegion,
        classified_rows: list[ClassifiedRow],
    ) -> dict[int, dict | None]:
        """
        Best-effort: map row_index → BoundingBox dict.
        Matches classified row text to block bboxes via equality.
        """
        # Build text → bbox mapping from blocks
        text_to_bbox: dict[str, dict] = {}
        for block in region.blocks:
            if block.bbox is not None:
                text_to_bbox[block.raw_text.strip()] = block.bbox.to_dict()

        result: dict[int, dict | None] = {}
        for cr in classified_rows:
            result[cr.row_index] = text_to_bbox.get(cr.raw_text.strip())
        return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_str(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return None
