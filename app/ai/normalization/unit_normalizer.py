"""
app/ai/normalization/unit_normalizer.py
=======================================
Maps raw UOM strings (Arabic + English) to a canonical form.

Usage:
    normalizer = UnitNormalizer()
    result = normalizer.normalize("طن")
    # NormalizedUnit(canonical="ton", category="weight", raw="طن")
"""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class NormalizedUnit:
    canonical: str          # e.g. "pc", "kg", "m", "ton"
    category: str           # quantity | weight | length | area | volume | time | energy | other
    raw: str                # original string as found in source


# ─────────────────────────────────────────────────────────────────────────────
# Alias tables: raw_string (lowercased) → (canonical, category)
# ─────────────────────────────────────────────────────────────────────────────

_ALIAS_TABLE: dict[str, tuple[str, str]] = {
    # ── Quantity / Count ──────────────────────────────────────────────────────
    "pc":        ("pc", "quantity"),
    "pcs":       ("pc", "quantity"),
    "piece":     ("pc", "quantity"),
    "pieces":    ("pc", "quantity"),
    "unit":      ("pc", "quantity"),
    "units":     ("pc", "quantity"),
    "no":        ("pc", "quantity"),
    "nos":       ("pc", "quantity"),
    "no.":       ("pc", "quantity"),
    "nos.":      ("pc", "quantity"),
    "number":    ("pc", "quantity"),
    "item":      ("pc", "quantity"),
    "items":     ("pc", "quantity"),
    "عدد":       ("pc", "quantity"),
    "قطعة":      ("pc", "quantity"),
    "قطعه":      ("pc", "quantity"),
    "قطع":       ("pc", "quantity"),
    "حبة":       ("pc", "quantity"),
    "حبه":       ("pc", "quantity"),
    "حبات":      ("pc", "quantity"),
    "وحدة":      ("pc", "quantity"),
    "وحده":      ("pc", "quantity"),
    # ── Sets / Kits ───────────────────────────────────────────────────────────
    "set":       ("set", "quantity"),
    "sets":      ("set", "quantity"),
    "kit":       ("set", "quantity"),
    "kits":      ("set", "quantity"),
    "طقم":       ("set", "quantity"),
    "طقمات":     ("set", "quantity"),
    # ── Box / Carton ──────────────────────────────────────────────────────────
    "box":       ("box", "quantity"),
    "boxes":     ("box", "quantity"),
    "carton":    ("box", "quantity"),
    "cartons":   ("box", "quantity"),
    "ctn":       ("box", "quantity"),
    "ctns":      ("box", "quantity"),
    "علبة":      ("box", "quantity"),
    "علبه":      ("box", "quantity"),
    "كرتون":     ("box", "quantity"),
    "كرتونة":    ("box", "quantity"),
    # ── Bag / Sack ────────────────────────────────────────────────────────────
    "bag":       ("bag", "quantity"),
    "bags":      ("bag", "quantity"),
    "sack":      ("bag", "quantity"),
    "sacks":     ("bag", "quantity"),
    "كيس":       ("bag", "quantity"),
    "أكياس":     ("bag", "quantity"),
    # ── Roll ─────────────────────────────────────────────────────────────────
    "roll":      ("roll", "quantity"),
    "rolls":     ("roll", "quantity"),
    "لفة":       ("roll", "quantity"),
    "لفات":      ("roll", "quantity"),
    # ── Pair ─────────────────────────────────────────────────────────────────
    "pair":      ("pair", "quantity"),
    "pairs":     ("pair", "quantity"),
    "زوج":       ("pair", "quantity"),
    # ── Lot / Bulk ───────────────────────────────────────────────────────────
    "lot":       ("lot", "quantity"),
    "lots":      ("lot", "quantity"),
    "bulk":      ("lot", "quantity"),
    "lump sum":  ("ls", "quantity"),
    "ls":        ("ls", "quantity"),
    "l.s":       ("ls", "quantity"),
    "l.s.":      ("ls", "quantity"),
    "مبلغ مقطوع": ("ls", "quantity"),
    # ── Weight ───────────────────────────────────────────────────────────────
    "kg":        ("kg", "weight"),
    "kgs":       ("kg", "weight"),
    "kilogram":  ("kg", "weight"),
    "kilograms": ("kg", "weight"),
    "كيلو":      ("kg", "weight"),
    "كيلوغرام":  ("kg", "weight"),
    "كلغ":       ("kg", "weight"),
    "g":         ("g", "weight"),
    "gr":        ("g", "weight"),
    "gram":      ("g", "weight"),
    "grams":     ("g", "weight"),
    "غرام":      ("g", "weight"),
    "جرام":      ("g", "weight"),
    "ton":       ("ton", "weight"),
    "tons":      ("ton", "weight"),
    "tonne":     ("ton", "weight"),
    "tonnes":    ("ton", "weight"),
    "mt":        ("ton", "weight"),
    "طن":        ("ton", "weight"),
    "أطنان":     ("ton", "weight"),
    "lb":        ("lb", "weight"),
    "lbs":       ("lb", "weight"),
    "pound":     ("lb", "weight"),
    "pounds":    ("lb", "weight"),
    # ── Length ───────────────────────────────────────────────────────────────
    "m":         ("m", "length"),
    "mtr":       ("m", "length"),
    "mtrs":      ("m", "length"),
    "meter":     ("m", "length"),
    "meters":    ("m", "length"),
    "metre":     ("m", "length"),
    "metres":    ("m", "length"),
    "متر":       ("m", "length"),
    "أمتار":     ("m", "length"),
    "cm":        ("cm", "length"),
    "centimeter": ("cm", "length"),
    "centimetre": ("cm", "length"),
    "mm":        ("mm", "length"),
    "millimeter": ("mm", "length"),
    "millimetre": ("mm", "length"),
    "ft":        ("ft", "length"),
    "feet":      ("ft", "length"),
    "foot":      ("ft", "length"),
    "قدم":       ("ft", "length"),
    "inch":      ("in", "length"),
    "inches":    ("in", "length"),
    "in":        ("in", "length"),
    "بوصة":      ("in", "length"),
    # ── Area ─────────────────────────────────────────────────────────────────
    "m2":        ("m2", "area"),
    "sqm":       ("m2", "area"),
    "sq.m":      ("m2", "area"),
    "sq m":      ("m2", "area"),
    "square meter":   ("m2", "area"),
    "square metre":   ("m2", "area"),
    "square meters":  ("m2", "area"),
    "متر مربع":  ("m2", "area"),
    "م2":        ("m2", "area"),
    "sqft":      ("ft2", "area"),
    "sq.ft":     ("ft2", "area"),
    "square foot":   ("ft2", "area"),
    "square feet":   ("ft2", "area"),
    # ── Volume ───────────────────────────────────────────────────────────────
    "l":         ("l", "volume"),
    "ltr":       ("l", "volume"),
    "ltrs":      ("l", "volume"),
    "liter":     ("l", "volume"),
    "liters":    ("l", "volume"),
    "litre":     ("l", "volume"),
    "litres":    ("l", "volume"),
    "لتر":       ("l", "volume"),
    "ml":        ("ml", "volume"),
    "milliliter": ("ml", "volume"),
    "millilitre": ("ml", "volume"),
    "m3":        ("m3", "volume"),
    "cbm":       ("m3", "volume"),
    "cubic meter":   ("m3", "volume"),
    "cubic metre":   ("m3", "volume"),
    "متر مكعب":  ("m3", "volume"),
    # ── BTU / Energy / Power ─────────────────────────────────────────────────
    "btu":       ("btu", "energy"),
    "btu/hr":    ("btu", "energy"),
    "kw":        ("kw", "energy"),
    "kilowatt":  ("kw", "energy"),
    "hp":        ("hp", "energy"),
    "horsepower": ("hp", "energy"),
    "حصان":      ("hp", "energy"),
    # ── Time ─────────────────────────────────────────────────────────────────
    "day":       ("day", "time"),
    "days":      ("day", "time"),
    "يوم":       ("day", "time"),
    "أيام":      ("day", "time"),
    "month":     ("month", "time"),
    "months":    ("month", "time"),
    "شهر":       ("month", "time"),
    "year":      ("year", "time"),
    "years":     ("year", "time"),
    "سنة":       ("year", "time"),
    # ── Job / Service ─────────────────────────────────────────────────────────
    "job":       ("job", "other"),
    "service":   ("job", "other"),
    "visit":     ("job", "other"),
    "visit(s)":  ("job", "other"),
    "trip":      ("job", "other"),
}

# Pre-normalise keys: lowercase + collapse whitespace
_NORMALISED_ALIAS: dict[str, tuple[str, str]] = {
    re.sub(r"\s+", " ", k.strip().lower()): v
    for k, v in _ALIAS_TABLE.items()
}


class UnitNormalizer:
    """
    Normalizes raw unit strings to their canonical form.

    Strategy:
    1. Exact match (case-insensitive, whitespace-collapsed).
    2. Prefix match for plural/abbreviated variants not in the table.
    3. Returns None if no mapping is found.
    """

    def normalize(self, raw: Optional[str]) -> Optional[NormalizedUnit]:
        if not raw:
            return None
        key = re.sub(r"\s+", " ", raw.strip().lower())
        hit = _NORMALISED_ALIAS.get(key)
        if hit:
            return NormalizedUnit(canonical=hit[0], category=hit[1], raw=raw)
        # Prefix fallback: "pcs." → "pcs"
        stripped = key.rstrip(".")
        hit = _NORMALISED_ALIAS.get(stripped)
        if hit:
            return NormalizedUnit(canonical=hit[0], category=hit[1], raw=raw)
        return None

    def canonical(self, raw: Optional[str]) -> Optional[str]:
        """Return just the canonical string, or None."""
        result = self.normalize(raw)
        return result.canonical if result else None

    def is_weight(self, raw: Optional[str]) -> bool:
        result = self.normalize(raw)
        return result is not None and result.category == "weight"

    def is_length(self, raw: Optional[str]) -> bool:
        result = self.normalize(raw)
        return result is not None and result.category == "length"
