"""
app/ai/interfaces/base_extractor.py
-------------------------------------
Abstract interface for entity extractors (products, prices, suppliers …).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseExtractor(ABC):
    """Extract structured entities from parsed document text."""

    @abstractmethod
    async def extract(self, parsed_data: dict) -> list[dict]:
        """
        Receive the output of a BaseParser and return a list of extracted
        entity dicts ready for persistence.
        """
