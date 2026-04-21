"""
scraper/scrapers/elburoj_scraper.py
-------------------------------------
Scraper for elburoj.com — a Saudi electrical/lighting products store
built on the Salla (سلة) e-commerce platform.

Target category:
    إنارة (Lighting) — https://elburoj.com/ar/إنارة/c539403396

What is scraped from the listing pages:
    - product name      (from anchor text, first non-empty line)
    - product URL       (canonical URL including product id after /p)
    - external_id       (numeric product id extracted from the URL slug)
    - sku               (numeric string that sometimes follows the name in the anchor text)
    - price             (SAR price shown below the product card)
    - brand             (extracted from Arabic "من {brand}" pattern in the name)
    - category          (the Salla category being scraped)

Note: Product detail pages on elburoj.com are JavaScript-rendered (Salla
platform SPA), so all extractable data comes from the server-side-rendered
listing HTML.  No additional product-page requests are made.

Pagination:
    ?page=1, ?page=2, …
    Stops when a page returns no new product IDs (avoids infinite loop on
    sites that wrap around on the last page).

To run manually from the project root:

    python -c "
    import asyncio
    from scraper.core.database import ScraperSessionLocal
    from scraper.scrapers.elburoj_scraper import ElBurojScraper

    async def main():
        async with ScraperSessionLocal() as db:
            stats = await ElBurojScraper(db).run()
            print(stats)

    asyncio.run(main())
    "
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from scraper.scrapers.base_scraper import BaseScraper
from scraper.services.scrape_service import BaseScrapeService

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

_BASE_URL = "https://elburoj.com"

# Lighting category — the URL provided by the user
_LIGHTING_CATEGORY_URL = (
    "https://elburoj.com/ar/%D8%A5%D9%86%D8%A7%D8%B1%D8%A9/c539403396"
)
_LIGHTING_CATEGORY_ID = "539403396"
_LIGHTING_CATEGORY_NAME = "إنارة"  # "Lighting" in Arabic

# Match the product id suffix in paths like /ar/{slug}/p1234567
_PRODUCT_ID_RE = re.compile(r"/p(\d+)$")

# Match "من {BrandName}" (= "from {BrandName}") at end of product name
# Works for Arabic brand mentions like "من هيونداي" or "من لوكسي فاي"
_BRAND_RE = re.compile(r"من\s+(.+?)(?:\s*-\s*[A-Z0-9].*)?$")

# Numeric-looking tokens that appear as the SKU after the product name
_SKU_RE = re.compile(r"^\d{5,}$")

# Price pattern: decimal or integer followed by optional whitespace
_PRICE_RE = re.compile(r"^\d+(?:\.\d+)?$")


class ElBurojScraper(BaseScrapeService, BaseScraper):
    """
    Scraper for elburoj.com — إنارة (Lighting) category.

    Inherits scraping orchestration from BaseScrapeService and HTTP helpers
    from BaseScraper.
    """

    source_name = "El Buroj"
    source_base_url = _BASE_URL

    # ── Configuration ──────────────────────────────────────────────────────────

    #: How many products constitute a "full page" — used to detect last page.
    _expected_page_size: int = 20

    #: Maximum pages to fetch (safety cap).
    _max_pages: int = 50

    # ── BaseScrapeService contract ─────────────────────────────────────────────

    async def _fetch_raw_products(self) -> list[dict[str, Any]]:
        await self._init_client(
            headers={
                "Accept-Language": "ar,en;q=0.8",
                "Referer": _BASE_URL,
            }
        )
        try:
            return await self._scrape_lighting_category()
        finally:
            await self._close_client()

    # ── Category scraping ──────────────────────────────────────────────────────

    async def _scrape_lighting_category(self) -> list[dict[str, Any]]:
        """
        Iterate through all pages of the lighting category and return raw
        product dicts.  Stops when a page returns no new product IDs.
        """
        products: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        # Resolve category id (get-or-create) so we can attach it to products.
        category_db_id = await self._get_or_create_category(
            name=_LIGHTING_CATEGORY_NAME,
            external_id=_LIGHTING_CATEGORY_ID,
            url=_LIGHTING_CATEGORY_URL,
        )

        for page in range(1, self._max_pages + 1):
            url = self._build_category_url(page)
            logger.info("[ElBurojScraper] Fetching page %d — %s", page, url)

            try:
                html = await self._get(url)
            except Exception as exc:
                logger.warning(
                    "[ElBurojScraper] Failed to fetch page %d: %s", page, exc
                )
                break

            page_products = self._parse_listing_page(html, category_db_id)

            new_products = [
                p for p in page_products if p["external_id"] not in seen_ids
            ]
            if not new_products:
                logger.info(
                    "[ElBurojScraper] No new products on page %d — stopping.", page
                )
                break

            for p in new_products:
                seen_ids.add(p["external_id"])
            products.extend(new_products)

            logger.info(
                "[ElBurojScraper] Page %d: %d new products (total so far: %d)",
                page,
                len(new_products),
                len(products),
            )

            # If we got fewer products than a full page, this is the last page.
            if len(page_products) < self._expected_page_size:
                logger.info(
                    "[ElBurojScraper] Page %d returned fewer than %d products — "
                    "last page reached.",
                    page,
                    self._expected_page_size,
                )
                break

        return products

    # ── URL builder ────────────────────────────────────────────────────────────

    @staticmethod
    def _build_category_url(page: int) -> str:
        """Build the paginated category listing URL."""
        params = {
            "filters[category_id]": _LIGHTING_CATEGORY_ID,
            "page": str(page),
        }
        return f"{_LIGHTING_CATEGORY_URL}?{urlencode(params)}"

    # ── HTML parsing ───────────────────────────────────────────────────────────

    def _parse_listing_page(
        self, html: str, category_db_id: int
    ) -> list[dict[str, Any]]:
        """
        Parse a category listing HTML page and return raw product dicts.

        Salla listing pages render each product as an <a> tag whose href
        contains the product slug + id (e.g. /ar/{slug}/p{id}).  The price
        and SKU appear as text nodes inside or adjacent to that anchor.
        """
        soup = BeautifulSoup(html, "html.parser")
        products: list[dict[str, Any]] = []

        # Find all anchors that link to a product page (/ar/{slug}/p{id})
        for anchor in soup.find_all("a", href=_PRODUCT_ID_RE):
            raw = self._parse_product_anchor(anchor, category_db_id)
            if raw:
                products.append(raw)

        return products

    def _parse_product_anchor(
        self, anchor, category_db_id: int
    ) -> dict[str, Any] | None:
        """
        Extract product data from a single product <a> element.

        Returns None if the anchor does not look like a real product card.
        """
        href: str = anchor.get("href", "")
        m = _PRODUCT_ID_RE.search(href)
        if not m:
            return None

        external_id = m.group(1)

        # Build the canonical full URL
        source_url = href if href.startswith("http") else f"{_BASE_URL}{href}"

        # Extract all text lines from the anchor, strip blanks
        raw_text_lines = [
            t.strip() for t in anchor.get_text(separator="\n").splitlines() if t.strip()
        ]

        if not raw_text_lines:
            return None

        name, sku = self._split_name_and_sku(raw_text_lines)
        if not name:
            return None

        brand_name = self._extract_brand(name)

        # Price: look for a sibling/parent element with a numeric text node
        price = self._find_price_near(anchor)

        # Brand ID — get-or-create only if we found a brand name
        # (We call this synchronously via a stored coroutine result — note that
        # _parse_product_anchor is called from synchronous BeautifulSoup loop,
        # so brand resolution is deferred: we return it as a string and resolve
        # in _post_process_brands() after all HTML parsing is done.)
        raw_data = json.dumps(
            {
                "external_id": external_id,
                "name": name,
                "sku": sku,
                "price": str(price) if price else None,
                "brand": brand_name,
                "href": href,
            },
            ensure_ascii=False,
        )

        content_hash = hashlib.sha256(
            f"{name}|{price}|{sku}".encode()
        ).hexdigest()

        return {
            "external_id": external_id,
            "source_url": source_url,
            "name": name,
            "sku": sku,
            "price": price,
            "raw_data": raw_data,
            "hash": content_hash,
            "scraper_category_id": category_db_id,
            # Brand stored as a side-channel key; resolved below
            "_brand_name": brand_name,
        }

    # ── Brand resolution — called from BaseScrapeService._save_product override

    async def _save_product(self, raw: dict[str, Any]) -> tuple[Any, bool]:
        """
        Override to resolve brand before calling the parent upsert.
        Pops the internal `_brand_name` key and resolves it to a DB id.
        """
        brand_name: str | None = raw.pop("_brand_name", None)
        if brand_name:
            try:
                raw["scraper_brand_id"] = await self._get_or_create_brand(
                    name=brand_name
                )
            except Exception as exc:
                logger.warning(
                    "[ElBurojScraper] Could not resolve brand '%s': %s",
                    brand_name,
                    exc,
                )

        return await super()._save_product(raw)

    # ── Text parsing helpers ───────────────────────────────────────────────────

    @staticmethod
    def _split_name_and_sku(lines: list[str]) -> tuple[str, str | None]:
        """
        Salla listing anchors often contain:
            Line 0: Product name (may span multiple lines)
            Last line: SKU (pure numeric string like "31614033069")

        Returns (name, sku_or_None).
        """
        if not lines:
            return "", None

        # If the last line looks like a SKU (all digits, ≥5 chars), split it off
        if len(lines) >= 2 and _SKU_RE.match(lines[-1]):
            sku = lines[-1]
            name = " ".join(lines[:-1]).strip()
        else:
            sku = None
            name = " ".join(lines).strip()

        # Clean up repeated whitespace
        name = re.sub(r"\s+", " ", name)

        return name, sku

    @staticmethod
    def _extract_brand(name: str) -> str | None:
        """
        Extract brand from Arabic product name.
        Matches "من {BrandName}" at the end of the name.
        Example: "سبوت لايت من هيونداي - مقاس 7 سم" → "هيونداي"
        """
        m = _BRAND_RE.search(name)
        if m:
            brand = m.group(1).strip()
            # Strip trailing junk like "- HLFL" model numbers
            brand = re.sub(r"\s*-\s*[A-Z0-9].*$", "", brand).strip()
            return brand if brand else None
        return None

    @staticmethod
    def _find_price_near(anchor) -> Decimal | None:
        """
        Salla listing pages render the price as a text node that is either:
          - A sibling of the anchor's parent element, or
          - Inside a nearby element

        We walk up the DOM tree up to 4 levels and search all text nodes for
        a pattern that looks like a price (digits with optional decimal).
        """
        node = anchor
        for _ in range(4):
            parent = node.parent
            if parent is None:
                break
            for text in parent.stripped_strings:
                text = text.strip()
                if _PRICE_RE.match(text):
                    try:
                        return Decimal(text)
                    except InvalidOperation:
                        pass
            node = parent
        return None
