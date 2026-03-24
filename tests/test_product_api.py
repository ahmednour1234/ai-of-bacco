"""
tests/test_product_api.py
--------------------------
Integration tests for the /v1/products endpoints.
Uses the AsyncClient fixture from conftest.py which bypasses real auth
by overriding the CurrentUserDep dependency.
"""

from __future__ import annotations

import uuid

import pytest

from app.core.dependencies import get_current_active_user
from app.models.user import User


# ---------------------------------------------------------------------------
# Auth override helper
# ---------------------------------------------------------------------------

ORG_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


def _fake_user() -> User:
    """Return a bare User instance with just the fields our routes need."""
    user = User.__new__(User)
    user.id = USER_ID
    user.org_id = ORG_ID
    user.is_active = True
    user.is_superuser = False
    return user


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_product_returns_201(client):
    """POST /v1/products should create a product and return 201."""
    client.app.dependency_overrides[get_current_active_user] = lambda: _fake_user()

    response = await client.post(
        "/v1/products",
        json={"name": "API Widget", "unit": "pcs"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["name"] == "API Widget"


@pytest.mark.asyncio
async def test_list_products_returns_200(client):
    """GET /v1/products should return a paginated list."""
    client.app.dependency_overrides[get_current_active_user] = lambda: _fake_user()

    response = await client.get("/v1/products")
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "meta" in body


@pytest.mark.asyncio
async def test_get_nonexistent_product_returns_404(client):
    """GET /v1/products/{id} with a missing UUID should return 404."""
    client.app.dependency_overrides[get_current_active_user] = lambda: _fake_user()

    response = await client.get(f"/v1/products/{uuid.uuid4()}")
    assert response.status_code == 404
