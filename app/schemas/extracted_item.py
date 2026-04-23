"""
ExtractedItem Schemas
=====================
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, Any

from app.schemas.base import BaseSchema, BaseResponseSchema


class ExtractedItemUpdateSchema(BaseSchema):
    """Used for manual review — linking to a product or marking reviewed."""
    matched_product_id: Optional[uuid.UUID] = None
    is_reviewed: Optional[bool] = None
    normalized_text: Optional[str] = None


class ExtractedItemResponseSchema(BaseResponseSchema):
    id: uuid.UUID
    document_id: uuid.UUID
    raw_text: str
    normalized_text: Optional[str]
    matched_product_id: Optional[uuid.UUID]
    confidence_score: Optional[float]
    is_reviewed: bool
    metadata: Optional[dict[str, Any]]
    org_id: uuid.UUID
    created_at: datetime
