"""
tests/test_product_service.py
-------------------------------
Unit tests for ProductService.
Uses an in-memory SQLite session (from conftest.py).
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from app.core.exceptions import ConflictException, NotFoundException
from app.schemas.product import ProductCreateSchema, ProductUpdateSchema
from app.services.product_service import ProductService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ORG_ID = uuid.uuid4()
OWNER_ID = uuid.uuid4()


def _create_schema(**kwargs) -> ProductCreateSchema:
    defaults = {
        "name": "Test Product",
        "description": "A test product",
        "sku": None,
        "unit": "pcs",
        "category": "General",
    }
    return ProductCreateSchema(**{**defaults, **kwargs})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_product(db_session):
    """Creating a product returns a response with correct fields."""
    service = ProductService(db_session)
    schema = _create_schema(name="Widget A")
    product = await service.create_product(schema, org_id=ORG_ID, owner_id=OWNER_ID)

    assert product.name == "Widget A"
    assert product.slug == "widget-a"
    assert product.id is not None


@pytest.mark.asyncio
async def test_create_product_duplicate_name_raises_conflict(db_session):
    """Creating two products with the same name should raise ConflictException."""
    service = ProductService(db_session)
    schema = _create_schema(name="Duplicate Widget")
    await service.create_product(schema, org_id=ORG_ID, owner_id=OWNER_ID)

    with pytest.raises(ConflictException):
        await service.create_product(schema, org_id=ORG_ID, owner_id=OWNER_ID)


@pytest.mark.asyncio
async def test_get_product_not_found(db_session):
    """Getting a non-existent product raises NotFoundException."""
    service = ProductService(db_session)
    with pytest.raises(NotFoundException):
        await service.get_product(uuid.uuid4(), org_id=ORG_ID)


@pytest.mark.asyncio
async def test_update_product(db_session):
    """Updating a product's name should regenerate its slug."""
    service = ProductService(db_session)
    created = await service.create_product(
        _create_schema(name="Old Name"), org_id=ORG_ID, owner_id=OWNER_ID
    )
    updated = await service.update_product(
        product_id=created.id,
        schema=ProductUpdateSchema(name="New Name"),
        org_id=ORG_ID,
    )
    assert updated.name == "New Name"
    assert updated.slug == "new-name"


@pytest.mark.asyncio
async def test_delete_product_soft_deletes(db_session):
    """Soft-deleting a product makes it no longer retrievable."""
    service = ProductService(db_session)
    created = await service.create_product(
        _create_schema(name="To Delete"), org_id=ORG_ID, owner_id=OWNER_ID
    )
    await service.delete_product(created.id, org_id=ORG_ID)

    with pytest.raises(NotFoundException):
        await service.get_product(created.id, org_id=ORG_ID)
