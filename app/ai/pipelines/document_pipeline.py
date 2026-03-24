"""
app/ai/pipelines/document_pipeline.py
---------------------------------------
Orchestrates the full document → extracted items → product matching flow.

Steps:
  1. Select the appropriate parser based on document type.
  2. Parse the file.
  3. Extract items from parsed data.
  4. Match items to existing products.
  5. Persist ExtractedItem records (via injected repositories).
"""

from __future__ import annotations

from app.ai.interfaces.base_pipeline import BasePipeline
from app.ai.parsers.invoice_parser import InvoiceParser
from app.ai.parsers.price_list_parser import PriceListParser
from app.ai.parsers.product_catalog_parser import ProductCatalogParser


class DocumentPipeline(BasePipeline):
    async def run(self, payload: dict) -> dict:
        """
        payload keys:
            file_bytes: bytes
            filename: str
            document_type: str   ("invoice" | "price_list" | "product_catalog")
            document_id: str     (UUID)
            org_id: str          (UUID)

        Returns a result dict stored as AIJob.result.

        TODO: wire up ExtractedItemRepository + BaseMatcher after inject pattern
              is decided (e.g. constructor injection or service-locator).
        """
        doc_type = payload.get("document_type", "invoice")
        file_bytes: bytes = payload["file_bytes"]
        filename: str = payload["filename"]

        parser_map = {
            "invoice": InvoiceParser(),
            "price_list": PriceListParser(),
            "product_catalog": ProductCatalogParser(),
        }
        parser = parser_map.get(doc_type, InvoiceParser())
        parsed = await parser.parse(file_bytes, filename)

        # TODO: extraction + matching + persistence steps
        return {
            "document_id": payload.get("document_id"),
            "parsed_type": doc_type,
            "extracted_count": len(parsed.get("line_items", parsed.get("items", parsed.get("products", [])))),
            "status": "parsed",
        }
