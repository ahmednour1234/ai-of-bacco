"""
app/services/learning_service.py
=================================
Updates the learned-rule dictionary and correction-example store based on
approved / rejected / corrected candidates.

Three mechanisms:
  1. **Keyword promotion** — keywords from approved product names are upserted
     into `learned_rules` with type=product_keyword and weight increased.
  2. **Keyword demotion** — keywords from rejected products (false positives)
     are downgraded; rules that hit 0 weight are disabled.
  3. **Correction example storage** — approved/corrected products become
     CorrectionExample rows used by the similarity override in future runs.
"""

from __future__ import annotations

import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction_candidate import ExtractionCandidate
from app.repositories.correction_example_repository import CorrectionExampleRepository
from app.repositories.learned_rule_repository import LearnedRuleRepository
from app.schemas.extraction import TrainingExampleSchema


# Minimum word length to consider as a learnable keyword
_MIN_KEYWORD_LEN = 4

# Stopwords to skip when extracting keywords from product names
_STOPWORDS: frozenset[str] = frozenset({
    "the", "and", "for", "with", "this", "that", "from", "into", "over",
    "under", "each", "inch", "size", "type", "pack", "lot", "set", "box",
    "bag",
})


class LearningService:
    """Extracts signals from user corrections and improves stored rules."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._rule_repo = LearnedRuleRepository(db)
        self._example_repo = CorrectionExampleRepository(db)

    # ── Main entry point ──────────────────────────────────────────────────────

    async def apply_corrections(
        self, candidates: list[ExtractionCandidate]
    ) -> None:
        """
        Process a batch of just-reviewed candidates:
          - approved/corrected → promote keywords, save example
          - rejected           → demote keywords
        """
        for candidate in candidates:
            status = candidate.status  # approved | rejected | corrected

            if status in ("approved", "corrected"):
                await self._learn_from_approval(candidate)
            elif status == "rejected":
                await self._learn_from_rejection(candidate)

    # ── Training data export ──────────────────────────────────────────────────

    async def export_training_data(self) -> list[TrainingExampleSchema]:
        """Return all saved correction examples as training-data records."""
        examples = await self._example_repo.get_all_examples()
        return [
            TrainingExampleSchema(
                raw_text=ex.raw_text,
                correct_label=ex.correct_label,
                correct_name=ex.correct_name,
                correct_category=ex.correct_category,
                correct_brand=ex.correct_brand,
                correct_description=ex.correct_description,
                correct_quantity=ex.correct_quantity,
                correct_unit=ex.correct_unit,
                correct_price=ex.correct_price,
            )
            for ex in examples
        ]

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _learn_from_approval(
        self, candidate: ExtractionCandidate
    ) -> None:
        effective_name = candidate.effective_name
        effective_category = candidate.effective_category
        effective_label = candidate.effective_label

        # Only save examples that ended up as product labels
        if effective_label != "product" or not effective_name:
            return

        # 1. Keyword promotion
        keywords = self._extract_keywords(effective_name)
        for kw in keywords:
            await self._rule_repo.upsert_keyword(
                rule_type="product_keyword",
                rule_value=kw,
                weight_delta=0.5,
                category_hint=effective_category,
            )

        # 2. Save / update correction example
        await self._example_repo.create_from_candidate(
            raw_text=candidate.raw_text,
            correct_label=effective_label,
            correct_name=candidate.effective_name,
            correct_category=effective_category,
            correct_brand=candidate.effective_brand,
            correct_description=candidate.effective_description,
            correct_quantity=candidate.effective_quantity,
            correct_unit=candidate.effective_unit,
            correct_price=candidate.effective_price,
        )

    async def _learn_from_rejection(
        self, candidate: ExtractionCandidate
    ) -> None:
        """
        Demote keywords extracted from a rejected product candidate.
        Only fires when the original prediction was 'product' (false positive).
        """
        if candidate.predicted_label != "product":
            return

        name_to_demote = candidate.product_name or candidate.raw_text
        keywords = self._extract_keywords(name_to_demote)
        for kw in keywords:
            await self._rule_repo.demote_keyword(rule_value=kw, weight_delta=0.3)

    # ── Keyword extraction ────────────────────────────────────────────────────

    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
        """
        Extract meaningful single words (>= 4 chars, not stopwords, not pure digits)
        from a product name or description.
        """
        words = re.findall(r"\b[a-zA-Z\u0600-\u06FF]{4,}\b", text.lower())
        return [
            w for w in words
            if w not in _STOPWORDS and not w.isdigit()
        ]
