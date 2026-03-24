"""
AIJobRepository
===============
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_job import AIJob, AIJobStatus, AIJobType
from app.repositories.base import BaseRepository
from app.schemas.ai_job import AIJobCreateSchema


class AIJobRepository(BaseRepository[AIJob, AIJobCreateSchema, AIJobCreateSchema]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, AIJob)

    async def get_by_status(
        self, status: AIJobStatus, org_id: uuid.UUID
    ) -> list[AIJob]:
        stmt = (
            select(AIJob)
            .where(AIJob.status == status, AIJob.org_id == org_id)
            .order_by(AIJob.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_pending_jobs(self, org_id: uuid.UUID) -> list[AIJob]:
        return await self.get_by_status(AIJobStatus.PENDING, org_id)

    async def get_by_document(
        self, document_id: uuid.UUID, org_id: uuid.UUID
    ) -> list[AIJob]:
        stmt = (
            select(AIJob)
            .where(AIJob.document_id == document_id, AIJob.org_id == org_id)
            .order_by(AIJob.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_type_and_status(
        self,
        job_type: AIJobType,
        status: AIJobStatus,
        org_id: uuid.UUID,
    ) -> list[AIJob]:
        stmt = (
            select(AIJob)
            .where(
                AIJob.job_type == job_type,
                AIJob.status == status,
                AIJob.org_id == org_id,
            )
            .order_by(AIJob.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
