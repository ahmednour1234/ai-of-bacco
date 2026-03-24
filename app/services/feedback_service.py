"""
app/services/feedback_service.py
=================================
Processes user corrections (approve / reject / correct) for extraction candidates.

Responsibilities:
  - Apply feedback actions to ExtractionCandidate rows
  - Write ExtractionFeedbackEvent audit log entries
  - Update session review counters
  - Trigger LearningService to update learned rules + correction examples
  - Export labeled training datasets (JSON / CSV) from CorrectionExample history
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ValidationException
from app.models.correction_example import CorrectionExample
from app.models.extraction_candidate import ExtractionCandidate
from app.models.extraction_feedback_event import ExtractionFeedbackEvent
from app.models.learned_rule import LearnedRule
from app.repositories.extraction_candidate_repository import ExtractionCandidateRepository
from app.repositories.extraction_session_repository import ExtractionSessionRepository
from app.schemas.extraction import (
    ApproveAllSchema,
    BulkFeedbackSchema,
    ExtractionSessionSchema,
    FeedbackItemSchema,
)
from app.services.extraction_session_service import ExtractionSessionService

logger = logging.getLogger(__name__)


class FeedbackService:
    """Processes bulk or individual candidate feedback for a session."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._session_repo = ExtractionSessionRepository(db)
        self._candidate_repo = ExtractionCandidateRepository(db)
        self._session_svc = ExtractionSessionService(db)

    # ── Bulk feedback ─────────────────────────────────────────────────────────

    async def submit_bulk_feedback(
        self,
        session_id: uuid.UUID,
        payload: BulkFeedbackSchema,
    ) -> ExtractionSessionSchema:
        """
        Apply a batch of feedback items (approve/reject/correct) in one call.
        Updates session counts afterwards and triggers the learning pipeline.
        """
        db_session = await self._session_repo.get_by_id(session_id)
        if db_session is None:
            raise NotFoundException("ExtractionSession", str(session_id))

        candidate_ids = [item.candidate_id for item in payload.feedbacks]
        candidates_by_id: dict[uuid.UUID, ExtractionCandidate] = {
            c.id: c for c in await self._candidate_repo.get_by_ids(candidate_ids)
        }

        corrected_candidates: list[ExtractionCandidate] = []

        for item in payload.feedbacks:
            candidate = candidates_by_id.get(item.candidate_id)
            if candidate is None:
                continue
            if candidate.session_id != session_id:
                raise ValidationException(
                    {"candidate_id": [f"Candidate {item.candidate_id} does not belong to session {session_id}."]}
                )
            updated = await self._apply_feedback_item(candidate, item)
            corrected_candidates.append(updated)

        # Refresh session review counts
        session = await self._session_svc.refresh_session_counts(db_session)

        # Trigger learning from corrections (fire-and-forget within same tx)
        if corrected_candidates:
            from app.services.learning_service import LearningService
            learning = LearningService(self._db)
            await learning.apply_corrections(corrected_candidates)

        full_session = await self._session_repo.get_with_candidates(session.id)
        return ExtractionSessionSchema.model_validate(full_session)

    # ── Single feedback ───────────────────────────────────────────────────────

    async def submit_single_feedback(
        self,
        session_id: uuid.UUID,
        candidate_id: uuid.UUID,
        item: FeedbackItemSchema,
    ) -> ExtractionSessionSchema:
        """Apply feedback to a single candidate and refresh session counts."""
        db_session = await self._session_repo.get_by_id(session_id)
        if db_session is None:
            raise NotFoundException("ExtractionSession", str(session_id))

        candidate = await self._candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise NotFoundException("ExtractionCandidate", str(candidate_id))
        if candidate.session_id != session_id:
            raise ValidationException(
                {"candidate_id": ["Candidate does not belong to this session."]}
            )

        updated = await self._apply_feedback_item(candidate, item)
        session = await self._session_svc.refresh_session_counts(db_session)

        from app.services.learning_service import LearningService
        learning = LearningService(self._db)
        await learning.apply_corrections([updated])

        full_session = await self._session_repo.get_with_candidates(session.id)
        return ExtractionSessionSchema.model_validate(full_session)

    # ── Approve all ───────────────────────────────────────────────────────────

    async def approve_all_pending(
        self,
        session_id: uuid.UUID,
        options: ApproveAllSchema,
    ) -> ExtractionSessionSchema:
        """
        Approve every pending candidate in the session.
        If options.only_products is True (default), only approve candidates
        predicted as 'product'.
        """
        db_session = await self._session_repo.get_by_id(session_id)
        if db_session is None:
            raise NotFoundException("ExtractionSession", str(session_id))

        all_candidates = await self._candidate_repo.get_by_session(session_id)
        approved: list[ExtractionCandidate] = []

        for candidate in all_candidates:
            if candidate.status != "pending":
                continue
            if options.only_products and candidate.predicted_label != "product":
                continue
            updated = await self._candidate_repo.apply_correction(
                candidate, action="approve"
            )
            approved.append(updated)

        session = await self._session_svc.refresh_session_counts(db_session)

        if approved:
            from app.services.learning_service import LearningService
            learning = LearningService(self._db)
            await learning.apply_corrections(approved)

        full_session = await self._session_repo.get_with_candidates(session.id)
        return ExtractionSessionSchema.model_validate(full_session)

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _apply_feedback_item(
        self,
        candidate: ExtractionCandidate,
        item: FeedbackItemSchema,
    ) -> ExtractionCandidate:
        old_snapshot = self._snapshot_candidate(candidate)
        fields: dict = {"action": item.action}

        if item.action == "correct":
            if item.corrected_label is not None:
                fields["corrected_label"] = item.corrected_label
            if item.corrected_name is not None:
                fields["corrected_name"] = item.corrected_name
            if item.corrected_description is not None:
                fields["corrected_description"] = item.corrected_description
            if item.corrected_quantity is not None:
                fields["corrected_quantity"] = item.corrected_quantity
            if item.corrected_unit is not None:
                fields["corrected_unit"] = item.corrected_unit
            if item.corrected_brand is not None:
                fields["corrected_brand"] = item.corrected_brand
            if item.corrected_category is not None:
                fields["corrected_category"] = item.corrected_category
            if item.corrected_price is not None:
                fields["corrected_price"] = item.corrected_price
            if item.correction_note is not None:
                fields["correction_note"] = item.correction_note

        updated = await self._candidate_repo.apply_correction(candidate, **fields)

        # Write audit event
        changed_fields = [
            k for k, v in fields.items()
            if k != "action" and old_snapshot.get(k) != v
        ]
        new_values = {k: v for k, v in fields.items() if k != "action"}
        event = ExtractionFeedbackEvent(
            candidate_id=updated.id,
            session_id=updated.session_id,
            user_id=None,   # caller may set via direct construction if user_id is available
            event_type=item.action,
            note=item.correction_note,
            changed_fields=changed_fields or None,
            old_values={k: old_snapshot.get(k) for k in changed_fields} if changed_fields else None,
            new_values=new_values if changed_fields else None,
        )
        self._db.add(event)

        return updated

    # ── Training dataset export ────────────────────────────────────────────────

    async def export_training_dataset(self, fmt: str = "json") -> str:
        """
        Export all CorrectionExample rows as a labeled training dataset.

        Args:
            fmt: "json" or "csv"

        Returns:
            String content of the exported dataset.
        """
        stmt = select(CorrectionExample).order_by(CorrectionExample.created_at)  # type: ignore[attr-defined]
        result = await self._db.scalars(stmt)
        examples = list(result.all())
        rows = [
            {
                "raw_text": ex.raw_text,
                "label": ex.correct_label,
                "product_name": ex.correct_name,
                "quantity": ex.correct_quantity,
                "unit": ex.correct_unit,
                "price": ex.correct_price,
                "brand": ex.correct_brand,
                "category": ex.correct_category,
                "use_count": ex.use_count,
            }
            for ex in examples
        ]

        if fmt == "json":
            return json.dumps(rows, ensure_ascii=False, indent=2)

        if fmt == "csv":
            if not rows:
                return ""
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
            return buf.getvalue()

        raise ValueError(f"Unsupported format: {fmt!r}. Use 'json' or 'csv'.")

    # ── Learned rules ──────────────────────────────────────────────────────────

    async def list_learned_rules(self, active_only: bool = True) -> list[LearnedRule]:
        """Return learned rules, sorted by weight descending."""
        stmt = select(LearnedRule)
        if active_only:
            stmt = stmt.where(LearnedRule.is_active == True)  # noqa: E712
        stmt = stmt.order_by(LearnedRule.weight.desc())
        result = await self._db.scalars(stmt)
        return list(result.all())

    # ── Snapshot helper ────────────────────────────────────────────────────────

    @staticmethod
    def _snapshot_candidate(candidate: ExtractionCandidate) -> dict[str, Any]:
        return {
            "predicted_label": candidate.predicted_label,
            "product_name": candidate.product_name,
            "description": candidate.description,
            "quantity": candidate.quantity,
            "unit": candidate.unit,
            "brand": candidate.brand,
            "category": candidate.category,
            "price": candidate.price,
            "status": candidate.status,
        }
