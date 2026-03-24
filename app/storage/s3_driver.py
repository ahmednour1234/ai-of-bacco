"""
app/storage/s3_driver.py
-------------------------
StorageDriver implementation backed by AWS S3 (or any S3-compatible service).
Uses boto3 with asyncio via run_in_executor to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
import io
from functools import partial

import boto3
from botocore.exceptions import ClientError

from app.core.config import get_settings
from app.storage.base import StorageDriver

settings = get_settings()


class S3StorageDriver(StorageDriver):
    def __init__(self) -> None:
        self._client = boto3.client(
            "s3",
            region_name=settings.AWS_DEFAULT_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        self._bucket = settings.AWS_S3_BUCKET

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _run_sync(self, func, *args, **kwargs):
        """Run a blocking boto3 call in a thread pool."""
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, partial(func, *args, **kwargs))

    # ------------------------------------------------------------------
    # StorageDriver contract
    # ------------------------------------------------------------------

    async def upload(self, file_bytes: bytes, destination_path: str, content_type: str = "application/octet-stream") -> str:
        await self._run_sync(
            self._client.put_object,
            Bucket=self._bucket,
            Key=destination_path,
            Body=file_bytes,
            ContentType=content_type,
        )
        return destination_path

    async def download(self, path: str) -> bytes:
        response = await self._run_sync(
            self._client.get_object,
            Bucket=self._bucket,
            Key=path,
        )
        return response["Body"].read()

    async def delete(self, path: str) -> None:
        await self._run_sync(
            self._client.delete_object,
            Bucket=self._bucket,
            Key=path,
        )

    def get_url(self, path: str) -> str:
        # Generate a pre-signed URL valid for 1 hour
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": path},
            ExpiresIn=3600,
        )
