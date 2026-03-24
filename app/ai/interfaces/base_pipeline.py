"""
app/ai/interfaces/base_pipeline.py
-------------------------------------
Abstract interface for AI processing pipelines.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BasePipeline(ABC):
    @abstractmethod
    async def run(self, payload: dict) -> dict:
        """
        Execute the full pipeline for the given payload.
        Returns a result dict that will be stored as the AIJob result.
        """
