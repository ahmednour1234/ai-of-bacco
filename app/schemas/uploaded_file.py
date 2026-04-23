"""
UploadedFile Schemas
====================
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseResponseSchema
from app.models.uploaded_file import UploadedFileStatus, UploadedFileType


class UploadedFileResponseSchema(BaseResponseSchema):
    id: uuid.UUID
    original_name: str
    storage_path: str
    mime_type: str
    size_bytes: int
    file_type: UploadedFileType
    status: UploadedFileStatus
    org_id: uuid.UUID
    owner_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime


class UploadedFileListItemSchema(BaseResponseSchema):
    id: uuid.UUID
    original_name: str
    mime_type: str
    size_bytes: int
    file_type: UploadedFileType
    status: UploadedFileStatus
    created_at: datetime
