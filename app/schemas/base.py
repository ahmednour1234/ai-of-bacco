"""
Base Schema Classes
===================
Equivalent to Laravel API Resources + Form Request base classes.

Provides:
- BaseSchema          → shared model_config for all input schemas
- BaseResponseSchema  → shared model_config for all output schemas (from_attributes=True)
- PaginationMeta      → pagination metadata envelope
- APIResponse[T]      → generic success envelope
- PaginatedAPIResponse[T] → paginated success envelope
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class BaseSchema(BaseModel):
    """
    Base for all input (create/update) schemas.
    Equivalent to Laravel's FormRequest base class.
    """
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )


class BaseResponseSchema(BaseModel):
    """
    Base for all output (response / resource) schemas.
    Setting from_attributes=True allows instantiation from SQLAlchemy model objects,
    equivalent to Laravel's Resource::make($model).
    """
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


# ── Response Envelope Schemas ─────────────────────────────────────────────────
# These mirror what app/core/response.py returns as raw dicts,
# but typed for documentation and testing purposes.

class PaginationMeta(BaseModel):
    total: int
    page: int
    per_page: int
    last_page: int
    from_: int | None = None
    to: int | None = None

    model_config = ConfigDict(populate_by_name=True)


class APIResponse(BaseModel, Generic[T]):
    """Typed wrapper for success_response(). Used in OpenAPI docs."""
    success: bool = True
    message: str
    data: T | None = None
    meta: dict | None = None


class PaginatedAPIResponse(BaseModel, Generic[T]):
    """Typed wrapper for paginated_response(). Used in OpenAPI docs."""
    success: bool = True
    message: str
    data: list[T]
    meta: PaginationMeta
