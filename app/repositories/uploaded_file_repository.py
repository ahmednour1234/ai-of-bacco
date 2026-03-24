"""
UploadedFileRepository
======================
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.uploaded_file import UploadedFile, UploadedFileStatus
from app.repositories.base import BaseRepository
from app.schemas.uploaded_file import UploadedFileResponseSchema


class UploadedFileRepository(BaseRepository[UploadedFile, UploadedFileResponseSchema, UploadedFileResponseSchema]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, UploadedFile)

    async def get_by_status(
        self, status: UploadedFileStatus, org_id: uuid.UUID
    ) -> list[UploadedFile]:
        stmt = (
            select(UploadedFile)
            .where(
                UploadedFile.status == status,
                UploadedFile.org_id == org_id,
                UploadedFile.deleted_at.is_(None),
            )
            .order_by(UploadedFile.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_pending(self, org_id: uuid.UUID) -> list[UploadedFile]:
        return await self.get_by_status(UploadedFileStatus.PENDING, org_id)
