"""
app/storage/local_driver.py
----------------------------
StorageDriver implementation that persists files on the local filesystem.
Suitable for development and single-node deployments.
"""

from __future__ import annotations

import os
from pathlib import Path

import aiofiles

from app.core.config import get_settings
from app.storage.base import StorageDriver

settings = get_settings()


class LocalStorageDriver(StorageDriver):
    def __init__(self) -> None:
        self.base_path = Path(settings.STORAGE_LOCAL_PATH).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def upload(self, file_bytes: bytes, destination_path: str, content_type: str = "application/octet-stream") -> str:
        full_path = self.base_path / destination_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(full_path, "wb") as f:
            await f.write(file_bytes)
        return destination_path

    async def download(self, path: str) -> bytes:
        full_path = self.base_path / path
        async with aiofiles.open(full_path, "rb") as f:
            return await f.read()

    async def delete(self, path: str) -> None:
        full_path = self.base_path / path
        if full_path.exists():
            full_path.unlink()

    def get_url(self, path: str) -> str:
        base_url = f"http://{settings.APP_HOST}:{settings.APP_PORT}"
        return f"{base_url}/storage/{path}"
