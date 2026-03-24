"""
AIJobService
============
Manages AI job records: creation, status transitions, and result storage.
Jobs are dispatched to Celery workers; this service handles the DB side.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_job import AIJobStatus, AIJobType
from app.repositories.ai_job_repository import AIJobRepository
from app.schemas.ai_job import AIJobCreateSchema, AIJobResponseSchema, AIJobListItemSchema
from app.services.base import BaseService


class AIJobService(BaseService[AIJobRepository]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(AIJobRepository(db))

    async def create_job(
        self, schema: AIJobCreateSchema, org_id: uuid.UUID, owner_id: uuid.UUID
    ) -> AIJobResponseSchema:
        data = {
            **schema.model_dump(),
            "status": AIJobStatus.PENDING,
            "org_id": org_id,
            "owner_id": owner_id,
        }
        job = await self.repo.create_from_dict(data)
        return AIJobResponseSchema.model_validate(job)

    async def get_job(self, job_id: uuid.UUID, org_id: uuid.UUID) -> AIJobResponseSchema:
        job = await self.get_by_id_or_fail(job_id, org_id, "AIJob")
        return AIJobResponseSchema.model_validate(job)

    async def list_jobs(
        self, org_id: uuid.UUID, page: int = 1, per_page: int = 15
    ) -> tuple[list[AIJobListItemSchema], int]:
        items, total = await self.list_paginated(page=page, per_page=per_page, org_id=org_id)
        return [AIJobListItemSchema.model_validate(j) for j in items], total

    async def mark_running(self, job_id: uuid.UUID) -> None:
        job = await self.repo.get_by_id(job_id)
        if job:
            await self.repo.update_fields(
                job,
                status=AIJobStatus.RUNNING,
                started_at=datetime.now(timezone.utc),
            )

    async def mark_completed(self, job_id: uuid.UUID, result: dict[str, Any]) -> None:
        job = await self.repo.get_by_id(job_id)
        if job:
            await self.repo.update_fields(
                job,
                status=AIJobStatus.COMPLETED,
                result=result,
                completed_at=datetime.now(timezone.utc),
            )

    async def mark_failed(self, job_id: uuid.UUID, error: str) -> None:
        job = await self.repo.get_by_id(job_id)
        if job:
            await self.repo.update_fields(
                job,
                status=AIJobStatus.FAILED,
                error_message=error,
                completed_at=datetime.now(timezone.utc),
            )
