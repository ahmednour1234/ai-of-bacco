"""
ExtractionCandidateRepository
==============================
Data-access layer for ExtractionCandidate.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction_candidate import ExtractionCandidate
from app.repositories.base import BaseRepository
from app.schemas.extraction import CandidateData


class ExtractionCandidateRepository(
    BaseRepository[ExtractionCandidate, dict, dict]
):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, ExtractionCandidate)

    async def bulk_create(
        self,
        session_id: uuid.UUID,
        candidates: list[CandidateData],
    ) -> list[ExtractionCandidate]:
        """Insert all candidates for a session in a single flush."""
        rows: list[ExtractionCandidate] = []
        for c in candidates:
            meta = c.extra_metadata or {}
            row = ExtractionCandidate(
                session_id=session_id,
                position=c.position,
                raw_text=c.raw_text,
                predicted_label=c.predicted_label,
                confidence=c.confidence,
                product_name=c.product_name,
                description=c.description,
                quantity=c.quantity,
                unit=c.unit,
                brand=c.brand,
                category=c.category,
                price=c.price,
                needs_review=c.needs_review,
                status="pending",
                # Universal pipeline provenance
                region_id=meta.get("region_id"),
                region_type=meta.get("region_type"),
                page_number=meta.get("page_number"),
                coordinates=meta.get("coordinates"),
                classification_source=meta.get("classification_source"),
            )
            self.db.add(row)
            rows.append(row)
        await self.db.flush()
        return rows

    async def get_by_session(
        self, session_id: uuid.UUID
    ) -> list[ExtractionCandidate]:
        stmt = (
            select(ExtractionCandidate)
            .where(ExtractionCandidate.session_id == session_id)
            .order_by(ExtractionCandidate.position)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_ids(
        self, candidate_ids: list[uuid.UUID]
    ) -> list[ExtractionCandidate]:
        stmt = select(ExtractionCandidate).where(
            ExtractionCandidate.id.in_(candidate_ids)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def apply_correction(
        self,
        candidate: ExtractionCandidate,
        **fields: Any,
    ) -> ExtractionCandidate:
        """Update correction fields and mark status accordingly."""
        action = fields.pop("action", None)
        if action == "approve":
            candidate.status = "approved"
        elif action == "reject":
            candidate.status = "rejected"
        elif action == "correct":
            candidate.status = "corrected"

        for key, value in fields.items():
            setattr(candidate, key, value)

        self.db.add(candidate)
        await self.db.flush()
        await self.db.refresh(candidate)
        return candidate

    async def get_approved_products(
        self, session_id: uuid.UUID
    ) -> list[ExtractionCandidate]:
        """Return candidates that were approved or corrected as 'product'."""
        stmt = (
            select(ExtractionCandidate)
            .where(
                ExtractionCandidate.session_id == session_id,
                ExtractionCandidate.status.in_(["approved", "corrected"]),
            )
            .order_by(ExtractionCandidate.position)
        )
        result = await self.db.execute(stmt)
        rows = list(result.scalars().all())
        # Filter to rows whose effective label is 'product'
        return [
            r for r in rows
            if (r.corrected_label or r.predicted_label) == "product"
        ]

    async def count_by_status(
        self, session_id: uuid.UUID
    ) -> dict[str, int]:
        """Return {pending, approved, rejected, corrected} counts."""
        from sqlalchemy import func
        stmt = (
            select(ExtractionCandidate.status, func.count())
            .where(ExtractionCandidate.session_id == session_id)
            .group_by(ExtractionCandidate.status)
        )
        result = await self.db.execute(stmt)
        return {row[0]: row[1] for row in result.all()}
