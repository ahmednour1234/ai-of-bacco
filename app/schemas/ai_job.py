"""
AIJob Schemas
=============
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.base import BaseSchema, BaseResponseSchema
from app.models.ai_job import AIJobType, AIJobStatus


class AIJobCreateSchema(BaseSchema):
    job_type: AIJobType
    document_id: uuid.UUID | None = None
    payload: dict[str, Any] | None = None


class AIJobResponseSchema(BaseResponseSchema):
    id: uuid.UUID
    job_type: AIJobType
    status: AIJobStatus
    document_id: uuid.UUID | None
    payload: dict[str, Any] | None
    result: dict[str, Any] | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    org_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class AIJobListItemSchema(BaseResponseSchema):
    id: uuid.UUID
    job_type: AIJobType
    status: AIJobStatus
    document_id: uuid.UUID | None
    created_at: datetime
    completed_at: datetime | None
