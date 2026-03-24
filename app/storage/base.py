"""
app/storage/base.py
--------------------
Abstract StorageDriver interface.
All concrete drivers must implement this contract.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class StorageDriver(ABC):
    """Abstract base class for all storage backends."""

    @abstractmethod
    async def upload(self, file_bytes: bytes, destination_path: str, content_type: str = "application/octet-stream") -> str:
        """
        Upload raw bytes to the storage backend.

        Returns the canonical path / key under which the file is stored.
        """

    @abstractmethod
    async def download(self, path: str) -> bytes:
        """Download and return file bytes from the given storage path."""

    @abstractmethod
    async def delete(self, path: str) -> None:
        """Permanently remove a file from storage."""

    @abstractmethod
    def get_url(self, path: str) -> str:
        """Return a publicly accessible (or pre-signed) URL for the given path."""
