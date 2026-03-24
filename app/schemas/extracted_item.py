"""
ExtractedItem Schemas
=====================
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.schemas.base import BaseSchema, BaseResponseSchema


class ExtractedItemUpdateSchema(BaseSchema):
    """Used for manual review — linking to a product or marking reviewed."""
    matched_product_id: uuid.UUID | None = None
    is_reviewed: bool | None = None
    normalized_text: str | None = None


class ExtractedItemResponseSchema(BaseResponseSchema):
    id: uuid.UUID
    document_id: uuid.UUID
    raw_text: str
    normalized_text: str | None
    matched_product_id: uuid.UUID | None
    confidence_score: float | None
    is_reviewed: bool
    metadata: dict[str, Any] | None
    org_id: uuid.UUID
    created_at: datetime
