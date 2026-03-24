"""
app/services/extraction_session_service.py
==========================================
Orchestrates a single file-upload extraction job end-to-end using the
UniversalExtractionPipeline (6-stage: parse → detect → regions → classify → extract).

Sync path  : files ≤ EXTRACTION_SYNC_MAX_BYTES and non-image formats
Async path : large files or images → Celery task, returns {job_id, status}

The old ProductExtractionService is no longer used here; it lives on as a
standalone heuristic library available to the pipeline stages.
"""

from __future__ import annotations

import base64
import uuid

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.extraction_session import ExtractionSession
from app.repositories.correction_example_repository import CorrectionExampleRepository
from app.repositories.extraction_candidate_repository import ExtractionCandidateRepository
from app.repositories.extraction_session_repository import ExtractionSessionRepository
from app.repositories.learned_rule_repository import LearnedRuleRepository
from app.schemas.extraction import (
    ApprovedProductSchema,
    CandidateData,
    ExtractionSessionSchema,
    ExtractionSessionSummarySchema,
)
from app.ai.pipelines.universal_extraction_pipeline import UniversalExtractionPipeline

settings = get_settings()

_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "tiff", "tif", "bmp", "webp"}


class ExtractionSessionService:
    """Coordinates file upload → extraction → persistence → review lifecycle."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._session_repo = ExtractionSessionRepository(db)
        self._candidate_repo = ExtractionCandidateRepository(db)
        self._rule_repo = LearnedRuleRepository(db)
        self._example_repo = CorrectionExampleRepository(db)

    # ── Create ────────────────────────────────────────────────────────────────

    async def create_session_from_file(
        self, file: UploadFile
    ) -> ExtractionSessionSchema | dict:
        """
        Route to sync or async pipeline depending on file size and format.

        Returns:
          - ExtractionSessionSchema  when processed synchronously.
          - {"job_id": str, "status": "queued"}  when dispatched to Celery.
        """
        file_bytes = await file.read()
        filename = (file.filename or "upload").strip()
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        is_large = len(file_bytes) > settings.EXTRACTION_SYNC_MAX_BYTES
        is_image = extension in _IMAGE_EXTENSIONS

        if is_large or is_image:
            return await self._create_session_async(file_bytes, filename, extension)

        return await self._run_pipeline_sync(file_bytes, filename, extension)

    async def _run_pipeline_sync(
        self,
        file_bytes: bytes,
        filename: str,
        extension: str,
    ) -> ExtractionSessionSchema:
        """Run the 6-stage pipeline in the current async context and persist."""
        correction_examples = await self._load_correction_examples()

        pipeline = UniversalExtractionPipeline()
        result_dict = pipeline.run({
            "file_bytes": file_bytes,
            "filename": filename,
            "correction_examples": correction_examples,
        })

        candidates: list[CandidateData] = result_dict.get("candidates", [])

        # Persist session with detection metadata
        db_session = await self._session_repo.create_session(
            filename=filename,
            file_type=extension,
            contains_products=result_dict.get("contains_products"),
            document_type_guess=result_dict.get("document_type_guess"),
            detection_confidence=result_dict.get("detection_confidence"),
            detection_metadata=result_dict.get("detection_metadata"),
        )

        await self._candidate_repo.bulk_create(db_session.id, candidates)

        await self._session_repo.update_counts(
            db_session,
            total=len(candidates),
            reviewed=0,
            approved=0,
            rejected=0,
            status="pending",
        )

        full_session = await self._session_repo.get_with_candidates(db_session.id)
        return ExtractionSessionSchema.model_validate(full_session)

    async def _create_session_async(
        self,
        file_bytes: bytes,
        filename: str,
        extension: str,
    ) -> dict:
        """Create a pending AIJob + dispatch Celery task. Return {job_id, status}."""
        from app.models.ai_job import AIJob, AIJobStatus, AIJobType
        from app.tasks.document_tasks import run_extraction_pipeline

        job = AIJob(
            job_type=AIJobType.PRODUCT_EXTRACTION,
            status=AIJobStatus.PENDING,
            payload={"filename": filename, "file_type": extension},
        )
        self._db.add(job)
        await self._db.flush()
        await self._db.refresh(job)

        correction_examples = await self._load_correction_examples()

        run_extraction_pipeline.delay(
            job_id=str(job.id),
            filename=filename,
            file_bytes_b64=base64.b64encode(file_bytes).decode(),
            correction_examples=correction_examples,
        )

        return {"job_id": str(job.id), "status": "queued"}

    async def _load_correction_examples(self) -> list[dict]:
        """Load saved correction examples from DB as lightweight dicts."""
        examples_db = await self._example_repo.get_all_examples()
        return [
            {
                "normalized_text": ex.normalized_text,
                "correct_label": ex.correct_label,
                "correct_name": ex.correct_name,
                "correct_category": ex.correct_category,
                "correct_brand": ex.correct_brand,
            }
            for ex in examples_db
        ]

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_session(self, session_id: uuid.UUID) -> ExtractionSessionSchema | None:
        session = await self._session_repo.get_with_candidates(session_id)
        if session is None:
            return None
        return ExtractionSessionSchema.model_validate(session)

    async def get_approved_products(
        self, session_id: uuid.UUID
    ) -> list[ApprovedProductSchema]:
        candidates = await self._candidate_repo.get_approved_products(session_id)
        return [
            ApprovedProductSchema(
                candidate_id=c.id,
                product_name=c.effective_name or c.raw_text[:120],
                category=c.effective_category,
                brand=c.effective_brand,
                quantity=c.effective_quantity,
                unit=c.effective_unit,
                description=c.effective_description,
                price=c.effective_price,
                source_line=c.raw_text,
            )
            for c in candidates
        ]

    async def refresh_session_counts(
        self, session: ExtractionSession
    ) -> ExtractionSession:
        """Recompute pending/approved/rejected counts from live DB data."""
        counts = await self._candidate_repo.count_by_status(session.id)
        total = sum(counts.values())
        reviewed = counts.get("approved", 0) + counts.get("rejected", 0) + counts.get("corrected", 0)
        approved = counts.get("approved", 0) + counts.get("corrected", 0)
        rejected = counts.get("rejected", 0)
        new_status = "completed" if reviewed == total and total > 0 else "reviewing"
        return await self._session_repo.update_counts(
            session,
            total=total,
            reviewed=reviewed,
            approved=approved,
            rejected=rejected,
            status=new_status,
        )
