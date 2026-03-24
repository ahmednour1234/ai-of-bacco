"""
app/ai/interfaces/base_parser.py
----------------------------------
Abstract interface for all document parsers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseParser(ABC):
    """Parse raw file bytes into structured data."""

    @abstractmethod
    async def parse(self, file_bytes: bytes, filename: str) -> dict:
        """
        Parse file content and return a normalized dict.
        The exact shape of the dict is defined per-parser.
        """
