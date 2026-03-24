"""
app/ai/interfaces/base_classifier.py
--------------------------------------
Abstract interface for document/product classifiers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseClassifier(ABC):
    @abstractmethod
    async def classify(self, text: str) -> str:
        """Return a classification label for the given text."""
