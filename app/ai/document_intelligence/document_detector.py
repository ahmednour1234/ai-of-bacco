"""
app/ai/document_intelligence/document_detector.py
==================================================
Stage 3 — Document Detection

Answers: does this document contain products?

Primary path  : OpenAI LLM with structured JSON output.
Fallback path : Heuristics (keyword density + numeric column detection).

The two paths return the same DetectionResult dataclass, so callers are
completely unaware of which path was used. The metadata dict always contains
the raw response (LLM JSON or heuristic scores) for auditability.
"""

from __future__ import annotations

import json
import logging
import re

from app.core.config import get_settings
from app.schemas.document_representation import (
    DOCUMENT_TYPE_GUESSES,
    DetectionResult,
    DocumentRepresentation,
)

logger = logging.getLogger(__name__)

# ── Heuristic keyword signals ─────────────────────────────────────────────────

_PRODUCT_SIGNALS_EN = frozenset({
    "qty", "quantity", "unit", "price", "amount", "total", "description",
    "item", "product", "material", "code", "part", "sku", "catalogue",
    "catalog", "specification", "spec", "brand", "model", "ref", "reference",
    "no.", "#", "uom", "rate", "cost", "pcs", "pack",
})

_PRODUCT_SIGNALS_AR = frozenset({
    "كمية", "وحدة", "سعر", "مبلغ", "إجمالي", "وصف", "صنف", "منتج",
    "مادة", "كود", "رقم", "مرجع", "موديل", "ماركة", "تخصص",
})

_DOCUMENT_TYPE_SIGNALS: dict[str, list[str]] = {
    "quotation":       ["quotation", "quote", "offer", "عرض سعر", "عرض", "تسعيرة"],
    "invoice":         ["invoice", "فاتورة", "tax invoice", "فاتورة ضريبية"],
    "price_list":      ["price list", "price sheet", "قائمة أسعار", "كشف أسعار"],
    "catalog":         ["catalogue", "catalog", "كتالوج", "catalog price"],
    "packing_list":    ["packing list", "قائمة التعبئة"],
    "purchase_order":  ["purchase order", "p.o.", "po ", "أمر شراء", "طلب شراء"],
    "delivery_note":   ["delivery note", "delivery order", "مذكرة تسليم"],
    "receipt":         ["receipt", "إيصال"],
}


def _keyword_density(text: str, keywords: frozenset[str]) -> float:
    words = re.findall(r"\w+", text.lower())
    if not words:
        return 0.0
    hits = sum(1 for w in words if w in keywords)
    return hits / len(words)


def _guess_doc_type_heuristic(text: str) -> str:
    text_lower = text.lower()
    best_type = "unknown"
    best_score = 0
    for doc_type, signals in _DOCUMENT_TYPE_SIGNALS.items():
        score = sum(1 for s in signals if s in text_lower)
        if score > best_score:
            best_score = score
            best_type = doc_type
    return best_type


def _heuristic_detect(doc: DocumentRepresentation) -> DetectionResult:
    """
    Rule-based fallback for document detection.
    Checks:
    - Keyword density in full text (EN + AR product signals)
    - Whether any table has columns matching product-table header keywords
    - Total score → contains_products if above threshold
    """
    text = doc.full_text
    en_density = _keyword_density(text, _PRODUCT_SIGNALS_EN)
    ar_density = _keyword_density(text, _PRODUCT_SIGNALS_AR)
    density = max(en_density, ar_density)

    # Check tables for numeric columns (price / qty patterns)
    has_numeric_table = False
    for tbl in doc.tables:
        headers_lower = [h.lower() for h in tbl.headers]
        has_price = any(
            any(sig in h for sig in ("price", "amount", "rate", "total", "سعر", "مبلغ", "إجمالي"))
            for h in headers_lower
        )
        has_qty = any(
            any(sig in h for sig in ("qty", "quantity", "unit", "كمية", "وحدة"))
            for h in headers_lower
        )
        # Or purely check if any column has mostly numeric values
        if not (has_price or has_qty) and tbl.rows:
            for col_idx in range(len(tbl.headers)):
                col_values = [
                    row[col_idx] for row in tbl.rows[:20]
                    if col_idx < len(row) and row[col_idx].strip()
                ]
                numeric_count = sum(
                    1 for v in col_values
                    if re.fullmatch(r"[-+]?\d+([.,/]\d+)?", v.replace(",", "").replace(" ", ""))
                )
                if col_values and numeric_count / len(col_values) > 0.6:
                    has_numeric_table = True
                    break
        if has_price or has_qty:
            has_numeric_table = True
            break

    score = density * 5.0 + (1.0 if has_numeric_table else 0.0)
    contains_products = score > 0.3  # ~6% keyword density in product-signal keywords

    doc_type = _guess_doc_type_heuristic(doc.full_text[:3000])
    confidence = min(0.70, 0.3 + score * 0.15)  # cap at 0.70 for heuristic path

    reasoning = (
        f"Heuristic: EN density={en_density:.3f}, AR density={ar_density:.3f}, "
        f"has_numeric_table={has_numeric_table}, score={score:.3f}"
    )

    return DetectionResult(
        contains_products=contains_products,
        document_type_guess=doc_type,
        confidence=confidence,
        reasoning=reasoning,
        language=doc.language_hint,
        metadata={
            "path": "heuristic",
            "en_density": en_density,
            "ar_density": ar_density,
            "has_numeric_table": has_numeric_table,
            "score": score,
        },
    )


# ── LLM prompt ────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a document classification expert. You will receive a text sample from a business document.

Your task: determine if the document contains a list of products/items for sale or procurement.

Respond ONLY with valid JSON matching this exact schema:
{
  "contains_products": true | false,
  "document_type_guess": "<one of: quotation, invoice, price_list, catalog, packing_list, purchase_order, delivery_note, receipt, unknown>",
  "confidence": <float 0.0 to 1.0>,
  "reasoning": "<brief explanation in 1-2 sentences>",
  "language": "<ar | en | mixed | unknown>"
}

Guidelines:
- contains_products = true if the document has rows/lines describing items with names, quantities, prices, or specifications.
- Even if header words are in Arabic, still classify correctly.
- If the document is a legal contract, letter, or report WITHOUT product rows → contains_products = false.
- confidence should reflect how certain you are.
"""


async def _llm_detect(doc: DocumentRepresentation) -> DetectionResult | None:
    """
    Call OpenAI to classify the document.
    Returns DetectionResult on success, None on any error (caller uses heuristic fallback).
    """
    settings = get_settings()
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    model = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")

    if not api_key or api_key.startswith("sk-placeholder"):
        return None

    try:
        from openai import AsyncOpenAI  # type: ignore
        client = AsyncOpenAI(api_key=api_key)

        snippet = doc.get_llm_context_snippet(max_chars=3000)
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"Document sample:\n\n{snippet}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=256,
        )

        raw_json = response.choices[0].message.content or "{}"
        data = json.loads(raw_json)

        doc_type = data.get("document_type_guess", "unknown")
        if doc_type not in DOCUMENT_TYPE_GUESSES:
            doc_type = "unknown"

        return DetectionResult(
            contains_products=bool(data.get("contains_products", False)),
            document_type_guess=doc_type,
            confidence=float(data.get("confidence", 0.5)),
            reasoning=str(data.get("reasoning", "")),
            language=str(data.get("language", doc.language_hint)),
            metadata={"path": "llm", "model": model, "raw_response": data},
        )
    except Exception as exc:
        logger.warning("LLM document detection failed (%s), falling back to heuristics.", exc)
        return None


# ── Public API ────────────────────────────────────────────────────────────────

class DocumentDetector:
    """
    Stage 3 of the universal extraction pipeline.
    Determines whether a document contains products.
    """

    async def detect(self, doc: DocumentRepresentation) -> DetectionResult:
        """
        Try LLM detection first; fall back to heuristics if unavailable or failed.
        """
        result = await _llm_detect(doc)
        if result is None:
            result = _heuristic_detect(doc)
        return result
