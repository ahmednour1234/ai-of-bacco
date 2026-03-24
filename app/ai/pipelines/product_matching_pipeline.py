"""
app/ai/pipelines/product_matching_pipeline.py
------------------------------------------------
Resolves extracted items to existing products using name/SKU similarity.

TODO: Swap the stub matcher for a real implementation that uses pgvector
      cosine similarity on ProductAlias.embedding.
"""

from __future__ import annotations

from app.ai.interfaces.base_pipeline import BasePipeline


class ProductMatchingPipeline(BasePipeline):
    async def run(self, payload: dict) -> dict:
        """
        payload keys:
            extracted_items: list[dict]
            org_id: str

        Returns:
            {
                "matched": list[dict],    # items with product_id filled in
                "unmatched": list[dict],  # items with no product_id
                "match_rate": float,
            }

        TODO: inject ProductRepository + BaseEmbedder for vector search.
        """
        items: list[dict] = payload.get("extracted_items", [])

        # Stub: nothing is matched yet
        return {
            "matched": [],
            "unmatched": items,
            "match_rate": 0.0,
        }
