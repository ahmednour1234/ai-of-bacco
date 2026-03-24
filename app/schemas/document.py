"""
Document Schemas
================
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.schemas.base import BaseSchema, BaseResponseSchema
from app.models.document import DocumentType, DocumentStatus


class DocumentUpdateSchema(BaseSchema):
    doc_type: DocumentType | None = None
    raw_text: str | None = None
    parsed_data: dict[str, Any] | None = None


class DocumentResponseSchema(BaseResponseSchema):
    id: uuid.UUID
    uploaded_file_id: uuid.UUID
    doc_type: DocumentType
    status: DocumentStatus
    raw_text: str | None
    parsed_data: dict[str, Any] | None
    error_message: str | None
    org_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class DocumentListItemSchema(BaseResponseSchema):
    id: uuid.UUID
    uploaded_file_id: uuid.UUID
    doc_type: DocumentType
    status: DocumentStatus
    created_at: datetime
