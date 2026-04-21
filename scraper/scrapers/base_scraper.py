"""
scraper/scrapers/base_scraper.py
---------------------------------
Low-level HTTP + parsing interface.

BaseScraper is responsible only for:
  - Making HTTP requests to the source website
  - Parsing pages into raw product dicts

It does NOT interact with the database — that is the job of BaseScrapeService.
Concrete scrapers inherit from BOTH:
    BaseScrapeService  (database / upsert orchestration)
    BaseScraper        (HTTP fetching + HTML/JSON parsing)

Or they may inherit only from BaseScrapeService and implement their own
HTTP logic inside `_fetch_raw_products()`.

Example inheritance:

    class MyStoreScraper(BaseScrapeService, BaseScraper):
        source_name = "My Store"
        source_base_url = "https://mystore.example.com"

        async def _fetch_raw_products(self) -> list[dict]:
            html = await self._get(self.source_base_url + "/products")
            return self._parse_product_list(html)

        def _parse_product_list(self, html: str) -> list[dict]:
            ...
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ScraperBot/1.0; +https://example.com/bot)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


class BaseScraper:
    """
    Thin HTTP helper mixin for concrete scrapers.

    Provides `_get()` and `_get_json()` convenience methods backed by a
    shared httpx.AsyncClient.  Call `await _init_client()` before use and
    `await _close_client()` when finished (or use `async with _client_ctx():`).
    """

    _http_client: httpx.AsyncClient | None = None

    async def _init_client(
        self, headers: dict[str, str] | None = None, timeout: int = 30
    ) -> None:
        self._http_client = httpx.AsyncClient(
            headers={**DEFAULT_HEADERS, **(headers or {})},
            timeout=timeout,
            follow_redirects=True,
        )

    async def _close_client(self) -> None:
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def _get(self, url: str, **kwargs: Any) -> str:
        """Perform a GET request and return the response text."""
        if not self._http_client:
            raise RuntimeError("HTTP client not initialised. Call _init_client() first.")
        response = await self._http_client.get(url, **kwargs)
        response.raise_for_status()
        return response.text

    async def _get_json(self, url: str, **kwargs: Any) -> Any:
        """Perform a GET request and return parsed JSON."""
        if not self._http_client:
            raise RuntimeError("HTTP client not initialised. Call _init_client() first.")
        response = await self._http_client.get(url, **kwargs)
        response.raise_for_status()
        return response.json()
