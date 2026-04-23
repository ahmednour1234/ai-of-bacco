"""
app/ai/normalization/quantity_parser.py
=======================================
Robust quantity + unit extraction from raw text (Arabic + English).

Parsing chain (each method tried in order, first match wins):
  1. Explicit qty+unit pattern  e.g. "5 pcs", "3 طن"
  2. Fraction pattern           e.g. "1/2 m"
  3. Range pattern              e.g. "2-4 units" → midpoint = 3
  4. Reverse-calculate from qty×price≈total triple
  5. Trailing integer (last standalone integer on the line)
  6. Optional LLM fallback      (only if OpenAI key is configured)

Usage:
    parser = QuantityParser()
    result = parser.parse("مكيف ترين مخفي 5 طن حار وبارد انفيرتر 2 13350 26700")
    # QuantityParseResult(quantity=2.0, unit=None, method="trailing_integer", ...)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional, Any

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Result container
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class QuantityParseResult:
    quantity: Optional[float]
    unit: Optional[str]
    method: str                   # which method produced this result
    confidence: float = 1.0       # 0.0 – 1.0
    raw_qty_string: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Regex definitions
# ─────────────────────────────────────────────────────────────────────────────

# Arabic + English UOM keywords (kept intentionally broad; UnitNormalizer maps them)
_UNIT_WORDS_RE = re.compile(
    r"(?:"
    r"pcs?|pieces?|units?|nos?\.?|sets?|kits?|bags?|rolls?|"
    r"cartons?|ctns?|boxes?|pairs?|lots?|jobs?|visits?|"
    r"kg|kgs|kilogram|grams?|g\b|gr\b|tons?|tonnes?|mt\b|lbs?|pounds?|"
    r"m\b|mtrs?|meters?|metres?|cm|mm|ft|feet|foot|inches?|in\b|"
    r"m2|sqm|m3|cbm|litr?e?s?|ltrs?|l\b|ml\b|"
    r"btu|hp|kw|"
    # Arabic
    r"عدد|قطعة|قطعه|قطع|حبة|حبه|حبات|وحدة|وحده|"
    r"كيلو|كيلوغرام|كلغ|غرام|جرام|طن|أطنان|"
    r"متر|أمتار|متر\s*مربع|متر\s*مكعب|م2|"
    r"لتر|كيس|أكياس|كرتون|كرتونة|لفة|زوج|طقم|"
    r"يوم|أيام|شهر|سنة"
    r")",
    re.IGNORECASE,
)

# Qty immediately followed by unit  e.g. "5 pcs", "3طن", "2.5 kg"
_QTY_UNIT_RE = re.compile(
    r"(?<!\d)"
    r"(?P<qty>\d+(?:[.,]\d+)?)"
    r"\s*"
    r"(?P<unit>" + _UNIT_WORDS_RE.pattern + r")"
    r"(?!\w)",
    re.IGNORECASE,
)

# Fraction  e.g. "1/2 m", "3/4 inch"
_FRACTION_RE = re.compile(
    r"(?P<num>\d+)\s*/\s*(?P<den>\d+)"
    r"\s*"
    r"(?P<unit>" + _UNIT_WORDS_RE.pattern + r")?",
    re.IGNORECASE,
)

# Range  e.g. "2-4 units", "1 - 3 pcs"
_RANGE_RE = re.compile(
    r"(?P<lo>\d+(?:[.,]\d+)?)\s*[-–]\s*(?P<hi>\d+(?:[.,]\d+)?)"
    r"\s*"
    r"(?P<unit>" + _UNIT_WORDS_RE.pattern + r")?",
    re.IGNORECASE,
)

# Bare number at end of text (fallback)
_TRAILING_INT_RE = re.compile(r"(?<!\d)(\d{1,5})(?!\d|[.,]\d)\s*$")

# Extract all plain numbers from a string
_ALL_NUMBERS_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _to_float(s: str) -> float:
    return float(s.replace(",", ""))


def _is_integerish(v: float, tol: float = 0.05) -> bool:
    return abs(v - round(v)) <= tol


# ─────────────────────────────────────────────────────────────────────────────
# Parser
# ─────────────────────────────────────────────────────────────────────────────

class QuantityParser:
    """
    Multi-method quantity extractor.

    Args:
        enable_llm: Try OpenAI as a last resort when all heuristic methods fail.
    """

    def __init__(self, enable_llm: bool = False) -> None:
        self._enable_llm = enable_llm

    # ── Public ─────────────────────────────────────────────────────────────────

    def parse(self, text: str) -> QuantityParseResult:
        """
        Synchronous heuristic parse. Returns QuantityParseResult.
        Tries methods 1-5 in order.
        """
        result = (
            self._method_explicit(text)
            or self._method_fraction(text)
            or self._method_range(text)
            or self._method_reverse_calc(text)
            or self._method_trailing_int(text)
        )
        if result:
            return result
        return QuantityParseResult(
            quantity=None, unit=None, method="none", confidence=0.0
        )

    async def parse_async(
        self, text: str, context: Optional[str] = None
    ) -> QuantityParseResult:
        """
        Async version — falls back to LLM if configured and heuristics fail.
        """
        result = self.parse(text)
        if result.quantity is not None:
            return result
        if self._enable_llm:
            llm_result = await self._method_llm(text, context)
            if llm_result:
                return llm_result
        return result

    # ── Heuristic methods ───────────────────────────────────────────────────────

    def _method_explicit(self, text: str) -> Optional[QuantityParseResult]:
        """Match qty immediately followed by a known unit word."""
        for m in _QTY_UNIT_RE.finditer(text):
            qty = _to_float(m.group("qty"))
            unit = m.group("unit")
            return QuantityParseResult(
                quantity=qty,
                unit=unit,
                method="explicit_unit",
                confidence=0.95,
                raw_qty_string=m.group(0),
            )
        return None

    def _method_fraction(self, text: str) -> Optional[QuantityParseResult]:
        """Match fractions like '1/2 m'."""
        m = _FRACTION_RE.search(text)
        if not m:
            return None
        try:
            num = float(m.group("num"))
            den = float(m.group("den"))
            if den == 0:
                return None
            qty = num / den
            unit = m.group("unit") if m.lastgroup == "unit" else None
            return QuantityParseResult(
                quantity=qty,
                unit=unit,
                method="fraction",
                confidence=0.85,
                raw_qty_string=m.group(0),
            )
        except (ValueError, TypeError):
            return None

    def _method_range(self, text: str) -> Optional[QuantityParseResult]:
        """Match ranges like '2-4 units' → midpoint."""
        m = _RANGE_RE.search(text)
        if not m:
            return None
        try:
            lo = _to_float(m.group("lo"))
            hi = _to_float(m.group("hi"))
            if hi < lo:
                return None
            unit = m.group("unit") if "unit" in m.groupdict() and m.group("unit") else None
            return QuantityParseResult(
                quantity=(lo + hi) / 2,
                unit=unit,
                method="range_midpoint",
                confidence=0.70,
                raw_qty_string=m.group(0),
            )
        except (ValueError, TypeError):
            return None

    def _method_reverse_calc(self, text: str) -> Optional[QuantityParseResult]:
        """
        Given three numbers A B C where B×A≈C, infer qty=A, price=B, total=C.
        Common in Arabic quotations: name  qty  unit_price  total
        """
        nums = [_to_float(t) for t in _ALL_NUMBERS_RE.findall(text)]
        if len(nums) < 3:
            return None
        # Try last-3 first (most common: … qty price total)
        for i in range(len(nums) - 2):
            a, b, c = nums[i], nums[i + 1], nums[i + 2]
            if b > 0 and c > b:
                ratio = c / b
                if _is_integerish(ratio) and abs(ratio - a) < 0.01:
                    return QuantityParseResult(
                        quantity=a,
                        unit=None,
                        method="reverse_calc",
                        confidence=0.80,
                    )
        return None

    def _method_trailing_int(self, text: str) -> Optional[QuantityParseResult]:
        """Last small integer on the line — very low confidence fallback."""
        m = _TRAILING_INT_RE.search(text)
        if not m:
            return None
        qty = float(m.group(1))
        if qty < 1 or qty > 10_000:
            return None
        return QuantityParseResult(
            quantity=qty,
            unit=None,
            method="trailing_integer",
            confidence=0.45,
            raw_qty_string=m.group(1),
        )

    # ── LLM fallback ───────────────────────────────────────────────────────────

    async def _method_llm(
        self, text: str, context: Optional[str]
    ) -> Optional[QuantityParseResult]:
        try:
            from app.core.config import get_settings
            settings = get_settings()
            api_key = getattr(settings, "OPENAI_API_KEY", "")
            model = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")
            if not api_key or api_key.startswith("sk-placeholder"):
                return None

            from openai import AsyncOpenAI  # type: ignore
            client = AsyncOpenAI(api_key=api_key)

            prompt = (
                f"Extract the quantity and unit from this product text.\n"
                f"Text: {text[:300]}\n"
                f"{'Context: ' + context[:200] if context else ''}\n\n"
                f'Respond with ONLY valid JSON: {{"quantity": <number|null>, "unit": "<string|null>"}}'
            )
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=64,
            )
            import json
            data = json.loads(response.choices[0].message.content or "{}")
            qty = data.get("quantity")
            unit = data.get("unit")
            if qty is not None:
                return QuantityParseResult(
                    quantity=float(qty),
                    unit=unit,
                    method="llm",
                    confidence=0.75,
                )
        except Exception as exc:
            logger.debug("LLM quantity parsing failed: %s", exc)
        return None
