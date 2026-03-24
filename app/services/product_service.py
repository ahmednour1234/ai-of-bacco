"""
ProductService
==============
Business logic layer for products.
Equivalent to Laravel's ProductService / ProductController logic extracted
into a dedicated service class.

This is the FULL reference implementation. All other services follow this pattern.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductCreateSchema, ProductUpdateSchema, ProductResponseSchema
from app.services.base import BaseService
from app.utils.slugify import generate_slug


class ProductService(BaseService[ProductRepository]):
    """
    Handles all product business logic.
    Equivalent to calling ProductRepository from a Laravel ProductService.
    """

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(ProductRepository(db))

    # ── Create ────────────────────────────────────────────────────────────────

    async def create_product(
        self, schema: ProductCreateSchema, org_id: uuid.UUID, owner_id: uuid.UUID
    ) -> ProductResponseSchema:
        """
        Create a new product with slug generation and duplicate detection.
        Equivalent to: ProductService::store($request) in Laravel.
        """
        slug = generate_slug(schema.name)

        # Enforce slug uniqueness per tenant (like a unique DB constraint check)
        existing = await self.repo.get_by_slug(slug, org_id)
        if existing is not None:
            raise ConflictException(
                f"A product with the name '{schema.name}' already exists in your organization."
            )

        data = {
            **schema.model_dump(exclude_unset=False),
            "slug": slug,
            "org_id": org_id,
            "owner_id": owner_id,
        }
        product = await self.repo.create_from_dict(data)
        return ProductResponseSchema.model_validate(product)

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_product(
        self, product_id: uuid.UUID, org_id: uuid.UUID
    ) -> ProductResponseSchema:
        """
        Retrieve a single product or raise 404.
        Equivalent to: Product::findOrFail($id) scoped to tenant.
        """
        product = await self.get_by_id_or_fail(product_id, org_id, "Product")
        return ProductResponseSchema.model_validate(product)

    async def list_products(
        self,
        org_id: uuid.UUID,
        page: int = 1,
        per_page: int = 15,
        filters: dict[str, Any] | None = None,
    ) -> tuple[list[ProductResponseSchema], int]:
        """
        Return a paginated list of products.
        Equivalent to: Product::paginate($perPage) with filters applied.
        """
        items, total = await self.list_paginated(
            page=page, per_page=per_page, org_id=org_id, filters=filters
        )
        return [ProductResponseSchema.model_validate(p) for p in items], total

    async def search_products(
        self, query: str, org_id: uuid.UUID
    ) -> list[ProductResponseSchema]:
        """Search products by name. Returns up to 20 matches."""
        products = await self.repo.search_by_name(query, org_id)
        return [ProductResponseSchema.model_validate(p) for p in products]

    async def get_product_with_aliases(
        self, product_id: uuid.UUID, org_id: uuid.UUID
    ) -> ProductResponseSchema:
        """Load product with its aliases eagerly."""
        product = await self.repo.get_with_aliases(product_id, org_id)
        if product is None:
            raise NotFoundException(f"Product '{product_id}' not found.")
        return ProductResponseSchema.model_validate(product)

    # ── Update ────────────────────────────────────────────────────────────────

    async def update_product(
        self,
        product_id: uuid.UUID,
        schema: ProductUpdateSchema,
        org_id: uuid.UUID,
    ) -> ProductResponseSchema:
        """
        Partially update a product.
        Equivalent to: $product->update($request->validated()) in Laravel.
        """
        product = await self.get_by_id_or_fail(product_id, org_id, "Product")

        # If name is changing, regenerate slug and check for conflict
        if schema.name is not None and schema.name != product.name:
            new_slug = generate_slug(schema.name)
            conflicting = await self.repo.get_by_slug(new_slug, org_id)
            if conflicting is not None and conflicting.id != product_id:
                raise ConflictException(
                    f"A product named '{schema.name}' already exists."
                )
            await self.repo.update_fields(product, slug=new_slug)

        updated = await self.repo.update(product, schema)
        return ProductResponseSchema.model_validate(updated)

    # ── Delete ────────────────────────────────────────────────────────────────

    async def delete_product(
        self, product_id: uuid.UUID, org_id: uuid.UUID
    ) -> None:
        """
        Soft-delete a product.
        Equivalent to: $product->delete() with SoftDeletes in Laravel.
        """
        await self.soft_delete_or_fail(product_id, org_id, "Product")
