"""
scraper/services/sync_service.py
----------------------------------
Sends unsynced scraper products to the external API and records every attempt
in scraper_sync_logs.

Design principles:
  - Per-product commit: a failure on one product does NOT roll back others.
  - Every attempt (success or failure) is logged to scraper_sync_logs.
  - On success: product.is_synced = True, product.synced_at = now().
  - Uses httpx for async HTTP with Bearer token auth.
  - The payload structure can be customised by overriding `_build_payload()`.

Usage:
    async with ScraperSessionLocal() as db:
        service = SyncService(db)
        result = await service.sync_pending()

    # result = {"processed": N, "succeeded": N, "failed": N}
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from scraper.models.product import ScraperProduct
from scraper.repositories.product_repository import ScraperProductRepository
from scraper.repositories.sync_log_repository import ScraperSyncLogRepository

logger = logging.getLogger(__name__)
settings = get_settings()

# Sync status constants
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"


class SyncService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._product_repo = ScraperProductRepository(db)
        self._log_repo = ScraperSyncLogRepository(db)

    # ── Public entry-point ─────────────────────────────────────────────────────

    async def sync_pending(
        self, batch_size: int | None = None
    ) -> dict[str, int]:
        """
        Fetch up to `batch_size` unsynced products and POST each one to the
        external API.

        Returns:
            {"processed": N, "succeeded": N, "failed": N}
        """
        limit = batch_size or settings.SCRAPER_SYNC_BATCH_SIZE
        products = await self._product_repo.get_unsynced(limit=limit)

        stats = {"processed": len(products), "succeeded": 0, "failed": 0}

        async with httpx.AsyncClient(timeout=30) as client:
            for product in products:
                success = await self._sync_one(client, product)
                if success:
                    stats["succeeded"] += 1
                else:
                    stats["failed"] += 1

        logger.info("[SyncService] Sync batch complete — %s", stats)
        return stats

    # ── Single-product sync ────────────────────────────────────────────────────

    async def _sync_one(
        self, client: httpx.AsyncClient, product: ScraperProduct
    ) -> bool:
        """
        POST a single product to the external API.
        Commits after each product so partial batches are persisted.
        Returns True on success.
        """
        payload = self._build_payload(product)
        payload_json = json.dumps(payload, default=str)
        synced_at = datetime.now(timezone.utc)

        try:
            response = await client.post(
                settings.SCRAPER_SYNC_API_URL,
                content=payload_json,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {settings.SCRAPER_SYNC_API_KEY}",
                    "Accept": "application/json",
                },
            )
            response.raise_for_status()

            # Log success
            await self._log_repo.log_attempt(
                scraper_product_id=product.id,
                sync_status=STATUS_SUCCESS,
                request_payload=payload_json,
                response_body=response.text[:10_000],  # truncate large responses
                synced_at=synced_at,
            )

            # Mark product as synced
            await self._product_repo.mark_synced(product)
            await self.db.commit()

            logger.debug(
                "[SyncService] product_id=%s synced successfully (HTTP %s)",
                product.id,
                response.status_code,
            )
            return True

        except httpx.HTTPStatusError as exc:
            await self._handle_failure(
                product,
                payload_json,
                response_body=exc.response.text[:10_000],
                error_msg=str(exc),
            )
            return False

        except httpx.RequestError as exc:
            await self._handle_failure(
                product,
                payload_json,
                response_body=None,
                error_msg=str(exc),
            )
            return False

    async def _handle_failure(
        self,
        product: ScraperProduct,
        payload_json: str,
        response_body: str | None,
        error_msg: str,
    ) -> None:
        logger.warning(
            "[SyncService] product_id=%s sync failed: %s", product.id, error_msg
        )
        await self._log_repo.log_attempt(
            scraper_product_id=product.id,
            sync_status=STATUS_FAILED,
            request_payload=payload_json,
            response_body=response_body or error_msg,
            synced_at=None,
        )
        await self.db.commit()

    # ── Payload builder (override to customise) ────────────────────────────────

    def _build_payload(self, product: ScraperProduct) -> dict[str, Any]:
        """
        Build the JSON payload sent to the external API.
        Override this method in a subclass to match the target API's schema.
        """
        return {
            "scraper_product_id": product.id,
            "source_id": product.source_id,
            "external_id": product.external_id,
            "source_url": product.source_url,
            "sku": product.sku,
            "name": product.name,
            "description": product.description,
            "specifications": product.specifications,
            "price": str(product.price) if product.price is not None else None,
            "scraper_category_id": product.scraper_category_id,
            "scraper_brand_id": product.scraper_brand_id,
            "last_scraped_at": (
                product.last_scraped_at.isoformat()
                if product.last_scraped_at
                else None
            ),
        }
