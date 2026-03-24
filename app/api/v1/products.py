"""
app/api/v1/products.py
-----------------------
Full products endpoint — the reference implementation for all API modules.
Demonstrates pagination, search, slug lookup, and alias sub-resources.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.core.dependencies import CurrentUserDep, DbDep
from app.core.response import created_response, no_content_response, paginated_response, success_response
from app.schemas.product import ProductCreateSchema, ProductUpdateSchema
from app.schemas.product_alias import ProductAliasCreateSchema
from app.services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["Products"])


# ── Collection ────────────────────────────────────────────────────────────────

@router.get("/")
async def list_products(
    db: DbDep,
    current_user: CurrentUserDep,
    page: int = Query(1, ge=1),
    per_page: int = Query(15, ge=1, le=100),
    search: str | None = Query(None, description="Full-text product name search"),
    category: str | None = Query(None, description="Filter by category"),
):
    """
    List products with optional search and category filtering.
    Returns a paginated envelope containing ProductListItemSchema records.
    """
    service = ProductService(db)
    if search:
        items, total = await service.search_products(
            query=search, org_id=current_user.org_id, page=page, per_page=per_page
        )
    else:
        items, total = await service.list_products(
            org_id=current_user.org_id,
            page=page,
            per_page=per_page,
            category=category,
        )
    return paginated_response(items=items, total=total, page=page, per_page=per_page)


@router.post("/", status_code=201)
async def create_product(schema: ProductCreateSchema, db: DbDep, current_user: CurrentUserDep):
    """Create a new product. Slug is auto-generated from the name."""
    service = ProductService(db)
    product = await service.create_product(
        schema=schema,
        org_id=current_user.org_id,
        owner_id=current_user.id,
    )
    return created_response(data=product, message="Product created.")


# ── Single resource ────────────────────────────────────────────────────────────

@router.get("/{product_id}")
async def get_product(product_id: uuid.UUID, db: DbDep, current_user: CurrentUserDep):
    """Retrieve a single product by UUID."""
    service = ProductService(db)
    product = await service.get_product(product_id, org_id=current_user.org_id)
    return success_response(data=product)


@router.patch("/{product_id}")
async def update_product(
    product_id: uuid.UUID,
    schema: ProductUpdateSchema,
    db: DbDep,
    current_user: CurrentUserDep,
):
    """Partially update a product. Slug regenerates when name changes."""
    service = ProductService(db)
    product = await service.update_product(
        product_id=product_id,
        schema=schema,
        org_id=current_user.org_id,
    )
    return success_response(data=product, message="Product updated.")


@router.delete("/{product_id}", status_code=204)
async def delete_product(product_id: uuid.UUID, db: DbDep, current_user: CurrentUserDep):
    """Soft-delete a product."""
    service = ProductService(db)
    await service.delete_product(product_id, org_id=current_user.org_id)
    return no_content_response()


# ── Aliases sub-resource ───────────────────────────────────────────────────────

@router.post("/{product_id}/aliases", status_code=201)
async def add_alias(
    product_id: uuid.UUID,
    schema: ProductAliasCreateSchema,
    db: DbDep,
    current_user: CurrentUserDep,
):
    """Add an alternate name/alias to a product."""
    from app.services.product_alias_service import ProductAliasService
    service = ProductAliasService(db)
    alias = await service.create_alias(
        schema=schema,
        product_id=product_id,
        org_id=current_user.org_id,
        owner_id=current_user.id,
    )
    return created_response(data=alias, message="Alias added.")


@router.get("/{product_id}/aliases")
async def list_aliases(product_id: uuid.UUID, db: DbDep, current_user: CurrentUserDep):
    """List all aliases for a product."""
    from app.services.product_alias_service import ProductAliasService
    service = ProductAliasService(db)
    aliases = await service.list_aliases(product_id=product_id, org_id=current_user.org_id)
    return success_response(data=aliases)
