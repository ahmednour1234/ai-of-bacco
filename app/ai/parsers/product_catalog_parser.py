"""
app/ai/parsers/product_catalog_parser.py
------------------------------------------
Stub product-catalog parser.
Replace the body of `parse()` with your actual implementation.
"""

from __future__ import annotations

from app.ai.interfaces.base_parser import BaseParser


class ProductCatalogParser(BaseParser):
    async def parse(self, file_bytes: bytes, filename: str) -> dict:
        """
        TODO: Implement product catalog parsing.

        Expected return shape:
        {
            "products": [
                {
                    "name": str,
                    "sku": Optional[str],
                    "description": Optional[str],
                    "category": Optional[str],
                    "unit": Optional[str],
                    "unit_price": Optional[float],
                    "currency": str,
                }
            ],
            "raw_text": str,
        }
        """
        return {
            "products": [],
            "raw_text": "",
        }
