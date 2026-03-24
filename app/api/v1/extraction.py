"""
app/api/v1/extraction.py
=========================
Feedback-driven extraction API — upload files, review candidates, submit corrections.

Endpoints
─────────
POST   /extraction/sessions                    Upload file → create extraction session (sync)
                                               OR queue async job (large files / images)
GET    /extraction/sessions/{session_id}        Get session + all candidates
GET    /extraction/sessions/job/{job_id}        Poll async job status
POST   /extraction/sessions/{session_id}/feedback          Bulk feedback (approve/reject/correct)
PATCH  /extraction/sessions/{session_id}/candidates/{id}   Single candidate correction
POST   /extraction/sessions/{session_id}/approve-all       Approve all pending
GET    /extraction/sessions/{session_id}/products          Get approved products
GET    /extraction/training-data               Export training data
GET    /extraction/rules                       View learned rules
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.exceptions import NotFoundException
from app.core.response import success_response
from app.repositories.learned_rule_repository import LearnedRuleRepository
from app.schemas.extraction import (
    ApproveAllSchema,
    BulkFeedbackSchema,
    FeedbackItemSchema,
    LearnedRuleSchema,
    TrainingExampleSchema,
)
from app.services.extraction_session_service import ExtractionSessionService
from app.services.feedback_service import FeedbackService
from app.services.learning_service import LearningService

router = APIRouter(prefix="/extraction", tags=["Feedback Extraction"])


# ── Session lifecycle ─────────────────────────────────────────────────────────

@router.post("/sessions")
async def create_extraction_session(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a file and create a new extraction session.

    - Small files (≤ 2 MB, non-image): runs synchronously and returns the full
      ExtractionSessionSchema with all candidates.
    - Large files or images: dispatches to a Celery worker and returns
      ``{"job_id": "...", "status": "queued"}``.  Poll
      ``GET /extraction/sessions/job/{job_id}`` to track progress.
    """
    svc = ExtractionSessionService(db)
    result = await svc.create_session_from_file(file)

    # Async path returns a plain dict; sync path returns a Pydantic schema
    if isinstance(result, dict) and "job_id" in result:
        return success_response(
            data=result,
            message="File queued for processing. Poll job status for completion.",
        )

    return success_response(
        data=result,
        message="Extraction session created. Review the candidates below.",
    )


@router.get("/sessions/job/{job_id}")
async def get_job_status(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Poll the status of an async extraction job.

    Returns the AIJob record including status, progress and the resulting
    session_id once the job is completed.
    """
    from app.models.ai_job import AIJob
    job = await db.get(AIJob, job_id)
    if job is None:
        raise NotFoundException("AIJob", str(job_id))

    data = {
        "job_id": str(job.id),
        "status": job.status.value,
        "job_type": job.job_type.value,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
    }
    if job.result:
        data.update(job.result)
    if job.error_message:
        data["error"] = job.error_message

    return success_response(data=data)


@router.get("/sessions/{session_id}")
async def get_extraction_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a session with all its candidates."""
    svc = ExtractionSessionService(db)
    session = await svc.get_session(session_id)
    if session is None:
        raise NotFoundException("ExtractionSession", str(session_id))
    return success_response(data=session)


# ── Feedback ──────────────────────────────────────────────────────────────────

@router.post("/sessions/{session_id}/feedback")
async def submit_bulk_feedback(
    session_id: uuid.UUID,
    payload: BulkFeedbackSchema,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit approve / reject / correct actions for one or more candidates.
    Triggers the learning pipeline automatically after saving.
    """
    svc = FeedbackService(db)
    session = await svc.submit_bulk_feedback(session_id, payload)
    return success_response(data=session, message="Feedback applied successfully.")


@router.patch("/sessions/{session_id}/candidates/{candidate_id}")
async def correct_single_candidate(
    session_id: uuid.UUID,
    candidate_id: uuid.UUID,
    item: FeedbackItemSchema,
    db: AsyncSession = Depends(get_db),
):
    """Apply feedback to a single candidate."""
    svc = FeedbackService(db)
    session = await svc.submit_single_feedback(session_id, candidate_id, item)
    return success_response(data=session, message="Candidate updated.")


@router.post("/sessions/{session_id}/approve-all")
async def approve_all_pending(
    session_id: uuid.UUID,
    options: ApproveAllSchema = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Approve every pending product candidate in the session."""
    svc = FeedbackService(db)
    session = await svc.approve_all_pending(session_id, options)
    return success_response(data=session, message="All pending candidates approved.")


# ── Approved products view ────────────────────────────────────────────────────

@router.get("/sessions/{session_id}/products")
async def get_approved_products(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Return only approved / corrected product candidates for a session."""
    svc = ExtractionSessionService(db)
    products = await svc.get_approved_products(session_id)
    return success_response(
        data={"session_id": str(session_id), "count": len(products), "products": products}
    )


# ── Knowledge base ────────────────────────────────────────────────────────────

@router.get("/training-data")
async def export_training_data(
    db: AsyncSession = Depends(get_db),
):
    """Export all saved correction examples as training data."""
    svc = LearningService(db)
    data = await svc.export_training_data()
    return success_response(
        data={"count": len(data), "examples": data},
        message="Training data exported.",
    )


@router.get("/rules")
async def list_learned_rules(
    db: AsyncSession = Depends(get_db),
):
    """View all active learned rules ordered by weight descending."""
    repo = LearnedRuleRepository(db)
    rules = await repo.get_active()
    schemas = [LearnedRuleSchema.model_validate(r) for r in rules]
    return success_response(
        data={"count": len(schemas), "rules": schemas},
        message="Learned rules retrieved.",
    )
