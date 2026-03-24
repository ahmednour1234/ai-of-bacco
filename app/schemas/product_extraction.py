"""
Schemas for product extraction API responses.
"""

from __future__ import annotations

from app.schemas.base import BaseResponseSchema


class ProductExtractedItemSchema(BaseResponseSchema):
    product_name: str
    category: str | None = None
    brand: str | None = None
    quantity: float | None = None
    unit: str | None = None
    description: str | None = None
    source_line: str | None = None


class ProductExtractionResultSchema(BaseResponseSchema):
    file_name: str
    file_type: str
    count: int
    items: list[ProductExtractedItemSchema]
