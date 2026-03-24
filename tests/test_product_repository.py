"""
tests/test_product_repository.py
----------------------------------
Unit tests for ProductRepository.
"""

from __future__ import annotations

import uuid

import pytest

from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductCreateSchema


ORG_ID = uuid.uuid4()
OWNER_ID = uuid.uuid4()


def _make_product_dict(name: str = "Repo Test Product") -> dict:
    return {
        "name": name,
        "slug": name.lower().replace(" ", "-"),
        "description": None,
        "sku": None,
        "unit": "pcs",
        "category": "Test",
        "org_id": ORG_ID,
        "owner_id": OWNER_ID,
    }


@pytest.mark.asyncio
async def test_create_and_get_by_id(db_session):
    repo = ProductRepository(db_session)
    product = await repo.create_from_dict(_make_product_dict("Repo Product 1"))
    fetched = await repo.get_by_id(product.id, org_id=ORG_ID)
    assert fetched is not None
    assert fetched.id == product.id


@pytest.mark.asyncio
async def test_get_by_slug(db_session):
    repo = ProductRepository(db_session)
    data = _make_product_dict("Slug Test Product")
    product = await repo.create_from_dict(data)
    found = await repo.get_by_slug(product.slug, org_id=ORG_ID)
    assert found is not None
    assert found.slug == product.slug


@pytest.mark.asyncio
async def test_soft_deleted_not_returned(db_session):
    repo = ProductRepository(db_session)
    product = await repo.create_from_dict(_make_product_dict("Soft Delete Test"))
    await repo.soft_delete(product)
    fetched = await repo.get_by_id(product.id, org_id=ORG_ID)
    assert fetched is None
