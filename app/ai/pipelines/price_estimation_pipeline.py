"""
app/ai/pipelines/price_estimation_pipeline.py
-----------------------------------------------
Aggregates historical price data and produces an AI-derived price estimate.

TODO: Replace the stub body with an actual estimation strategy
      (weighted average, LLM, regression model …).
"""

from __future__ import annotations

import uuid

from app.ai.interfaces.base_pipeline import BasePipeline


class PriceEstimationPipeline(BasePipeline):
    async def run(self, payload: dict) -> dict:
        """
        payload keys:
            product_id: str    (UUID)
            org_id: str        (UUID)
            context: dict      (optional extra data for the estimator)

        Returns a dict compatible with PriceEstimationCreateSchema, minus
        the org_id / owner_id fields (those are injected by the service).

        TODO: query SupplierProductRepository + InvoiceItemRepository for
              historical prices, then call BasePriceEstimator.estimate().
        """
        return {
            "product_id": payload.get("product_id"),
            "source_type": "ai_generated",
            "estimated_price": None,
            "currency": "USD",
            "confidence_score": None,
            "notes": "Stub — estimation not yet implemented.",
        }
