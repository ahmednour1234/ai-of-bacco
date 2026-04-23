"""
CorrectionExampleRepository
============================
Data-access layer for CorrectionExample.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.correction_example import CorrectionExample
from app.repositories.base import BaseRepository


class CorrectionExampleRepository(
    BaseRepository[CorrectionExample, dict, dict]
):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, CorrectionExample)

    async def get_all_examples(self) -> list[CorrectionExample]:
        """Return every saved correction example (used to seed extraction runs)."""
        stmt = select(CorrectionExample).order_by(
            CorrectionExample.use_count.desc()
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_label(self, label: str) -> list[CorrectionExample]:
        stmt = select(CorrectionExample).where(
            CorrectionExample.correct_label == label
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_similar(
        self,
        raw_text: str,
        threshold: float = 0.5,
        limit: int = 3,
    ) -> list[CorrectionExample]:
        """
        Pure word-overlap similarity search — no ML required.

        Returns up to `limit` examples whose normalised text shares at least
        `threshold` Jaccard overlap with the query text.
        """
        query_words = set(re.findall(r"\b\w{3,}\b", raw_text.lower()))
        if not query_words:
            return []

        all_examples = await self.get_all_examples()
        scored: list[tuple[float, CorrectionExample]] = []

        for ex in all_examples:
            ex_words = set(re.findall(r"\b\w{3,}\b", ex.normalized_text))
            if not ex_words:
                continue
            union = query_words | ex_words
            intersection = query_words & ex_words
            score = len(intersection) / len(union)
            if score >= threshold:
                scored.append((score, ex))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [ex for _, ex in scored[:limit]]

    async def create_from_candidate(
        self,
        raw_text: str,
        correct_label: str,
        correct_name: Optional[str],
        correct_category: Optional[str],
        correct_brand: Optional[str],
        correct_description: Optional[str],
        correct_quantity: Optional[float],
        correct_unit: Optional[str],
        correct_price: Optional[float],
    ) -> CorrectionExample:
        normalized = re.sub(r"\s+", " ", raw_text.strip().lower())
        example = CorrectionExample(
            raw_text=raw_text,
            normalized_text=normalized,
            correct_label=correct_label,
            correct_name=correct_name,
            correct_category=correct_category,
            correct_brand=correct_brand,
            correct_description=correct_description,
            correct_quantity=correct_quantity,
            correct_unit=correct_unit,
            correct_price=correct_price,
            use_count=0,
        )
        self.db.add(example)
        await self.db.flush()
        await self.db.refresh(example)
        return example

    async def increment_use_count(self, example_id) -> None:
        example = await self.get_by_id(example_id)
        if example:
            example.use_count += 1
            self.db.add(example)
            await self.db.flush()
