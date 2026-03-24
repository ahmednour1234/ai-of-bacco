"""
app/ai/validation/candidate_validator.py
=========================================
Post-extraction validation that:
- Boosts confidence when qty × price ≈ total
- Flags suspicious values (price looks like qty, unit inconsistency, etc.)
- Populates CandidateData.validation_flags list

All modifications are in-place on the CandidateData objects.

Usage:
    validator = CandidateValidator()
    validator.validate_candidates(candidates)
"""

from __future__ import annotations

import math
from typing import Sequence

from app.schemas.extraction import CandidateData


def _is_integerish(v: float, tol: float = 0.05) -> bool:
    return abs(v - round(v)) <= tol


class CandidateValidator:
    """
    Validates and enriches a list of CandidateData in-place.

    Checks:
    1. qty × price ≈ total  → confidence boost
    2. price looks like quantity (very small price, large "qty")
    3. quantity is suspiciously large (> 10 000)
    4. both quantity and price are identical (possible confusion)
    5. unit is present but quantity is None
    """

    # Tolerance for "approximately equal"
    TOTAL_MATCH_TOLERANCE = 0.02   # 2 % relative error
    CONFIDENCE_BOOST = 0.05

    def validate_candidates(
        self, candidates: Sequence[CandidateData]
    ) -> None:
        """Validate and annotate candidates in-place."""
        for cand in candidates:
            if cand.predicted_label != "product":
                continue
            self._check(cand)

    # ── Individual checks ──────────────────────────────────────────────────────

    def _check(self, cand: CandidateData) -> None:
        flags: list[str] = list(cand.validation_flags or [])

        qty = cand.quantity
        price = cand.price
        total = cand.total

        # 1. qty × price ≈ total → confidence boost
        if qty is not None and price is not None and total is not None:
            expected = qty * price
            if expected > 0:
                rel_err = abs(expected - total) / expected
                if rel_err <= self.TOTAL_MATCH_TOLERANCE:
                    cand.confidence = min(
                        1.0, cand.confidence + self.CONFIDENCE_BOOST
                    )
                else:
                    flags.append("total_mismatch")

        # 2. price looks too small AND qty looks too large → likely swapped
        if qty is not None and price is not None:
            if price < 1 and qty > 100:
                flags.append("possible_qty_price_swap")
            if qty > 0 and price > 0 and math.isclose(qty, price, rel_tol=0.001):
                flags.append("qty_equals_price")

        # 3. suspiciously large quantity
        if qty is not None and qty > 10_000:
            flags.append("qty_very_large")

        # 4. unit present but no quantity
        if cand.unit and qty is None:
            flags.append("unit_without_qty")

        # 5. negative values
        if qty is not None and qty < 0:
            flags.append("negative_qty")
        if price is not None and price < 0:
            flags.append("negative_price")

        # Write flags back
        cand.validation_flags = flags

        # Lower confidence if multiple flags
        if len(flags) >= 2:
            cand.confidence = max(0.0, cand.confidence - 0.10)
            cand.needs_review = True
        elif flags:
            cand.needs_review = True
