"""
DocumentRepository
==================
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus, DocumentType
from app.repositories.base import BaseRepository
from app.schemas.document import DocumentUpdateSchema


class DocumentRepository(BaseRepository[Document, DocumentUpdateSchema, DocumentUpdateSchema]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, Document)

    async def get_by_uploaded_file(
        self, uploaded_file_id: uuid.UUID, org_id: uuid.UUID
    ) -> Optional[Document]:
        stmt = (
            select(Document)
            .where(
                Document.uploaded_file_id == uploaded_file_id,
                Document.org_id == org_id,
                Document.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_status(
        self, status: DocumentStatus, org_id: uuid.UUID
    ) -> list[Document]:
        stmt = (
            select(Document)
            .where(
                Document.status == status,
                Document.org_id == org_id,
                Document.deleted_at.is_(None),
            )
            .order_by(Document.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_type(
        self, doc_type: DocumentType, org_id: uuid.UUID
    ) -> list[Document]:
        stmt = (
            select(Document)
            .where(
                Document.doc_type == doc_type,
                Document.org_id == org_id,
                Document.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
