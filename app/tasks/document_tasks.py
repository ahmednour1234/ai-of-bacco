"""
app/tasks/document_tasks.py
-----------------------------
Celery tasks for document processing (parse → extract → match).
"""

from __future__ import annotations

import asyncio
import base64
import uuid
from typing import Optional, Any

from app.tasks.celery_app import celery_app


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, name="tasks.process_document", max_retries=3)
def process_document(self, document_id: str, org_id: str) -> dict:
    """
    Legacy stub kept for backwards compatibility.
    New code should use run_extraction_pipeline instead.
    """
    return {
        "document_id": document_id,
        "status": "queued",
        "message": "Use run_extraction_pipeline task for new extractions.",
    }


@celery_app.task(bind=True, name="tasks.run_extraction_pipeline", max_retries=3)
def run_extraction_pipeline(
    self,
    job_id: str,
    filename: str,
    file_bytes_b64: str,
    correction_examples: Optional[list[dict]] = None,
) -> dict:
    """
    Execute the UniversalExtractionPipeline and persist results.

    Called by ExtractionSessionService._create_session_async() for large files
    and image uploads that should not block the HTTP request.

    Flow:
      1. Decode file bytes
      2. Run pipeline synchronously (no async DB here)
      3. Persist session + candidates via a dedicated async runner
      4. Update AIJob status
    """
    async def _run() -> dict:
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

        from app.core.config import get_settings
        from app.models.ai_job import AIJob, AIJobStatus
        from app.ai.pipelines.universal_extraction_pipeline import UniversalExtractionPipeline
        from app.repositories.extraction_session_repository import ExtractionSessionRepository
        from app.repositories.extraction_candidate_repository import ExtractionCandidateRepository
        from app.repositories.ai_job_repository import AIJobRepository

        settings = get_settings()

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        Session = async_sessionmaker(engine, expire_on_commit=False)

        async with Session() as db:
            job_uuid = uuid.UUID(job_id)
            job_repo = AIJobRepository(db)
            job = await db.get(AIJob, job_uuid)

            try:
                if job:
                    job.status = AIJobStatus.RUNNING
                    db.add(job)
                    await db.flush()

                file_bytes = base64.b64decode(file_bytes_b64)

                pipeline = UniversalExtractionPipeline()
                result_dict = pipeline.run({
                    "file_bytes": file_bytes,
                    "filename": filename,
                    "correction_examples": correction_examples or [],
                })

                candidates = result_dict.get("candidates", [])

                extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

                session_repo = ExtractionSessionRepository(db)
                candidate_repo = ExtractionCandidateRepository(db)

                db_session = await session_repo.create_session(
                    filename=filename,
                    file_type=extension,
                    contains_products=result_dict.get("contains_products"),
                    document_type_guess=result_dict.get("document_type_guess"),
                    detection_confidence=result_dict.get("detection_confidence"),
                    detection_metadata=result_dict.get("detection_metadata"),
                )

                await candidate_repo.bulk_create(db_session.id, candidates)

                await session_repo.update_counts(
                    db_session,
                    total=len(candidates),
                    reviewed=0,
                    approved=0,
                    rejected=0,
                    status="pending",
                )

                if job:
                    job.status = AIJobStatus.COMPLETED
                    job.result = {
                        "session_id": str(db_session.id),
                        "candidate_count": len(candidates),
                    }
                    db.add(job)

                await db.commit()
                return {"session_id": str(db_session.id), "status": "completed"}

            except Exception as exc:
                await db.rollback()
                if job:
                    async with Session() as err_db:
                        err_job = await err_db.get(AIJob, job_uuid)
                        if err_job:
                            err_job.status = AIJobStatus.FAILED
                            err_job.error_message = str(exc)[:500]
                            err_db.add(err_job)
                            await err_db.commit()
                raise exc

    try:
        return _run_async(_run())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)
