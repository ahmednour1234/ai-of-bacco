"""
UploadedFileService
===================
Handles file upload, storage delegation, and status transitions.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.uploaded_file import UploadedFileStatus, UploadedFileType
from app.repositories.uploaded_file_repository import UploadedFileRepository
from app.schemas.uploaded_file import UploadedFileResponseSchema, UploadedFileListItemSchema
from app.services.base import BaseService
from app.storage.base import StorageDriver
from app.utils.file_helpers import get_file_extension, safe_filename, detect_file_type


class UploadedFileService(BaseService[UploadedFileRepository]):
    def __init__(self, db: AsyncSession, storage: StorageDriver) -> None:
        super().__init__(UploadedFileRepository(db))
        self.storage = storage

    async def upload(
        self,
        file: UploadFile,
        org_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> UploadedFileResponseSchema:
        """
        Store the file via the configured storage driver and create a DB record.
        """
        filename = safe_filename(file.filename or "upload")
        content_type = detect_file_type(filename, file.content_type)
        extension = get_file_extension(filename)

        if content_type.startswith("image/"):
            file_type = UploadedFileType.IMAGE
        elif extension == "pdf":
            file_type = UploadedFileType.PDF
        else:
            file_type = UploadedFileType.OTHER

        storage_path = f"{org_id}/{file_type.value}/{filename}"

        file_bytes = await file.read()
        await self.storage.upload(file_bytes, storage_path)

        record = await self.repo.create_from_dict({
            "original_name": file.filename,
            "storage_path": storage_path,
            "mime_type": content_type,
            "size_bytes": len(file_bytes),
            "file_type": file_type,
            "status": UploadedFileStatus.PENDING,
            "org_id": org_id,
            "owner_id": owner_id,
        })
        return UploadedFileResponseSchema.model_validate(record)

    async def get_file(
        self, file_id: uuid.UUID, org_id: uuid.UUID
    ) -> UploadedFileResponseSchema:
        record = await self.get_by_id_or_fail(file_id, org_id, "UploadedFile")
        return UploadedFileResponseSchema.model_validate(record)

    async def list_files(
        self, org_id: uuid.UUID, page: int = 1, per_page: int = 15
    ) -> tuple[list[UploadedFileListItemSchema], int]:
        items, total = await self.list_paginated(page=page, per_page=per_page, org_id=org_id)
        return [UploadedFileListItemSchema.model_validate(f) for f in items], total

    async def mark_processing(self, file_id: uuid.UUID) -> None:
        record = await self.repo.get_by_id(file_id)
        if record:
            await self.repo.update_fields(record, status=UploadedFileStatus.PROCESSING)

    async def mark_processed(self, file_id: uuid.UUID) -> None:
        record = await self.repo.get_by_id(file_id)
        if record:
            await self.repo.update_fields(record, status=UploadedFileStatus.PROCESSED)

    async def mark_failed(self, file_id: uuid.UUID) -> None:
        record = await self.repo.get_by_id(file_id)
        if record:
            await self.repo.update_fields(record, status=UploadedFileStatus.FAILED)

    async def delete_file(self, file_id: uuid.UUID, org_id: uuid.UUID) -> None:
        record = await self.get_by_id_or_fail(file_id, org_id, "UploadedFile")
        await self.storage.delete(record.storage_path)
        await self.repo.soft_delete(record)
