"""
DocumentService
===============
Manages document lifecycle: creation from uploaded files, status transitions,
and triggering AI pipeline jobs.
"""

from __future__ import annotations

import uuid
from typing import Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentStatus, DocumentType
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import DocumentUpdateSchema, DocumentResponseSchema, DocumentListItemSchema
from app.services.base import BaseService


class DocumentService(BaseService[DocumentRepository]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(DocumentRepository(db))

    async def create_from_uploaded_file(
        self,
        uploaded_file_id: uuid.UUID,
        doc_type: DocumentType,
        org_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> DocumentResponseSchema:
        """Create a Document record linked to an UploadedFile."""
        doc = await self.repo.create_from_dict({
            "uploaded_file_id": uploaded_file_id,
            "doc_type": doc_type,
            "status": DocumentStatus.PENDING,
            "org_id": org_id,
            "owner_id": owner_id,
        })
        return DocumentResponseSchema.model_validate(doc)

    async def get_document(
        self, doc_id: uuid.UUID, org_id: uuid.UUID
    ) -> DocumentResponseSchema:
        doc = await self.get_by_id_or_fail(doc_id, org_id, "Document")
        return DocumentResponseSchema.model_validate(doc)

    async def list_documents(
        self,
        org_id: uuid.UUID,
        page: int = 1,
        per_page: int = 15,
        filters: Optional[dict[str, Any]] = None,
    ) -> tuple[list[DocumentListItemSchema], int]:
        items, total = await self.list_paginated(page=page, per_page=per_page, org_id=org_id, filters=filters)
        return [DocumentListItemSchema.model_validate(d) for d in items], total

    async def update_document(
        self, doc_id: uuid.UUID, schema: DocumentUpdateSchema, org_id: uuid.UUID
    ) -> DocumentResponseSchema:
        doc = await self.get_by_id_or_fail(doc_id, org_id, "Document")
        updated = await self.repo.update(doc, schema)
        return DocumentResponseSchema.model_validate(updated)

    async def set_parsed(
        self, doc_id: uuid.UUID, raw_text: str, parsed_data: dict[str, Any]
    ) -> None:
        """Called by AI pipeline after successful parsing."""
        doc = await self.repo.get_by_id(doc_id)
        if doc:
            await self.repo.update_fields(
                doc,
                raw_text=raw_text,
                parsed_data=parsed_data,
                status=DocumentStatus.COMPLETED,
            )

    async def set_failed(self, doc_id: uuid.UUID, error: str) -> None:
        doc = await self.repo.get_by_id(doc_id)
        if doc:
            await self.repo.update_fields(doc, status=DocumentStatus.FAILED, error_message=error)

    async def delete_document(self, doc_id: uuid.UUID, org_id: uuid.UUID) -> None:
        await self.soft_delete_or_fail(doc_id, org_id, "Document")
