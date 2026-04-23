"""
AIJob Schemas
=============
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, Any

from pydantic import Field

from app.schemas.base import BaseSchema, BaseResponseSchema
from app.models.ai_job import AIJobType, AIJobStatus


class AIJobCreateSchema(BaseSchema):
    job_type: AIJobType
    document_id: Optional[uuid.UUID] = None
    payload: Optional[dict[str, Any]] = None


class AIJobResponseSchema(BaseResponseSchema):
    id: uuid.UUID
    job_type: AIJobType
    status: AIJobStatus
    document_id: Optional[uuid.UUID]
    payload: Optional[dict[str, Any]]
    result: Optional[dict[str, Any]]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    org_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class AIJobListItemSchema(BaseResponseSchema):
    id: uuid.UUID
    job_type: AIJobType
    status: AIJobStatus
    document_id: Optional[uuid.UUID]
    created_at: datetime
    completed_at: Optional[datetime]
