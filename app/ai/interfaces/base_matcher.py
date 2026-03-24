"""
app/ai/interfaces/base_matcher.py
-----------------------------------
Abstract interface for entity-matching logic (extracted item → product).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseMatcher(ABC):
    @abstractmethod
    async def match(self, extracted_items: list[dict]) -> list[dict]:
        """
        Given a list of extracted item dicts, attempt to match each one to an
        existing product and return the enriched dicts with a `product_id` field.
        """
