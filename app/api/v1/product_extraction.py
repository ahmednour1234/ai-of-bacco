"""
app/api/v1/product_extraction.py
--------------------------------
On-demand extraction endpoint for products from file uploads.
"""

from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from app.core.response import success_response
from app.schemas.product_extraction import ProductExtractionResultSchema
from app.services.product_extraction_service import ProductExtractionService

router = APIRouter(prefix="/extract", tags=["Product Extraction"])


@router.post("/products")
async def extract_products(file: UploadFile = File(...)):
    """
    Extract product name, category, brand, quantity, and unit from:
    - PDF
    - Image
    - Excel (xlsx)
    - CSV
    """
    service = ProductExtractionService()
    items = await service.extract_from_upload(file)

    result = ProductExtractionResultSchema(
        file_name=file.filename or "upload",
        file_type=(file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else "unknown"),
        count=len(items),
        items=items,
    )
    return success_response(data=result, message="Products extracted successfully.")
