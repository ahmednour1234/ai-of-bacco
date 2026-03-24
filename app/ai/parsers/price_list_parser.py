"""
app/ai/parsers/price_list_parser.py
-------------------------------------
Stub price-list document parser.
Replace the body of `parse()` with your actual implementation.
"""

from __future__ import annotations

from app.ai.interfaces.base_parser import BaseParser


class PriceListParser(BaseParser):
    async def parse(self, file_bytes: bytes, filename: str) -> dict:
        """
        TODO: Implement price-list parsing (CSV, PDF, Excel …).

        Expected return shape:
        {
            "supplier_name": str | None,
            "effective_date": str | None,   # ISO 8601
            "currency": str,
            "items": [
                {
                    "sku": str | None,
                    "description": str,
                    "unit_price": float,
                    "unit": str | None,
                }
            ],
            "raw_text": str,
        }
        """
        return {
            "supplier_name": None,
            "effective_date": None,
            "currency": "USD",
            "items": [],
            "raw_text": "",
        }
