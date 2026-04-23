"""
Schemas for product extraction API responses.
"""

from __future__ import annotations

from app.schemas.base import BaseResponseSchema


class ProductExtractedItemSchema(BaseResponseSchema):
    product_name: str
    category: Optional[str] = None
    brand: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    description: Optional[str] = None
    source_line: Optional[str] = None


class ProductExtractionResultSchema(BaseResponseSchema):
    file_name: str
    file_type: str
    count: int
    items: list[ProductExtractedItemSchema]
