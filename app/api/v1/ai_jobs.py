"""
app/api/v1/ai_jobs.py
----------------------
AI job monitoring endpoints.
Jobs are dispatched by Celery tasks; these endpoints allow clients to
poll status and retrieve results.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.core.dependencies import CurrentUserDep, DbDep
from app.core.response import no_content_response, paginated_response, success_response
from app.services.ai_job_service import AIJobService

router = APIRouter(prefix="/ai-jobs", tags=["AI Jobs"])


@router.get("/")
async def list_jobs(
    db: DbDep,
    current_user: CurrentUserDep,
    page: int = Query(1, ge=1),
    per_page: int = Query(15, ge=1, le=100),
):
    service = AIJobService(db)
    items, total = await service.list_jobs(org_id=current_user.org_id, page=page, per_page=per_page)
    return paginated_response(items=items, total=total, page=page, per_page=per_page)


@router.get("/{job_id}")
async def get_job(job_id: uuid.UUID, db: DbDep, current_user: CurrentUserDep):
    service = AIJobService(db)
    job = await service.get_job(job_id, org_id=current_user.org_id)
    return success_response(data=job)


@router.delete("/{job_id}", status_code=204)
async def delete_job(job_id: uuid.UUID, db: DbDep, current_user: CurrentUserDep):
    service = AIJobService(db)
    await service.soft_delete_or_fail(job_id, org_id=current_user.org_id, resource_name="AIJob")
    return no_content_response()
