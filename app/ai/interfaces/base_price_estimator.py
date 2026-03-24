"""
app/ai/interfaces/base_price_estimator.py
-------------------------------------------
Abstract interface for price estimation engines.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import uuid


class BasePriceEstimator(ABC):
    @abstractmethod
    async def estimate(self, product_id: uuid.UUID, context: dict) -> dict:
        """
        Produce a price estimate for the given product.
        Returns a dict compatible with PriceEstimationCreateSchema.
        """
