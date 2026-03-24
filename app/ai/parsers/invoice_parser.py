"""
app/ai/parsers/invoice_parser.py
----------------------------------
Stub invoice parser.
Replace the body of `parse()` with your LLM / OCR / PDF extraction logic.
"""

from __future__ import annotations

from app.ai.interfaces.base_parser import BaseParser


class InvoiceParser(BaseParser):
    async def parse(self, file_bytes: bytes, filename: str) -> dict:
        """
        TODO: Implement invoice parsing via LLM / PDF extraction.

        Expected return shape:
        {
            "invoice_number": str | None,
            "invoice_date": str | None,   # ISO 8601
            "supplier_name": str | None,
            "total_amount": float | None,
            "currency": str,
            "line_items": [
                {
                    "description": str,
                    "quantity": float,
                    "unit_price": float,
                    "total_price": float,
                }
            ],
            "raw_text": str,
        }
        """
        return {
            "invoice_number": None,
            "invoice_date": None,
            "supplier_name": None,
            "total_amount": None,
            "currency": "USD",
            "line_items": [],
            "raw_text": "",
        }
