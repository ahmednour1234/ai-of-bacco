"""
app/ai/interfaces/base_embedder.py
------------------------------------
Abstract interface for text/product embedding generation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseEmbedder(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Return a dense vector embedding for the supplied text."""

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts. Default: sequential calls to embed()."""
        return [await self.embed(t) for t in texts]
