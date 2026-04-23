"""
API Response Helpers
====================
Equivalent to Laravel's API Resource base class + response() helper.

All endpoints return a consistent JSON envelope:
{
    "success": true,
    "message": "Products retrieved successfully.",
    "data": {...} | [...],
    "meta": {...} | null
}

Usage in a router:
    return success_response(data=product_schema, message="Product created.")
    return paginated_response(items=products, total=100, page=1, per_page=15)
    return error_response(message="Not found.", status_code=404)
"""

from __future__ import annotations

from typing import Optional, Any

from fastapi.encoders import jsonable_encoder
from fastapi import status
from fastapi.responses import JSONResponse


def success_response(
    data: Any = None,
    message: str = "Success.",
    meta: Optional[dict[str, Any]] = None,
    status_code: int = status.HTTP_200_OK,
) -> JSONResponse:
    """
    Return a standardised success response.
    Equivalent to: return response()->json(['data' => $data, 'message' => $msg])
    """
    body: dict[str, Any] = {
        "success": True,
        "message": message,
        "data": data,
    }
    if meta is not None:
        body["meta"] = meta
    return JSONResponse(content=jsonable_encoder(body), status_code=status_code)


def created_response(
    data: Any = None,
    message: str = "Resource created successfully.",
) -> JSONResponse:
    """Shorthand for 201 Created responses."""
    return success_response(data=data, message=message, status_code=status.HTTP_201_CREATED)


def paginated_response(
    items: list[Any],
    total: int,
    page: int,
    per_page: int,
    message: str = "Data retrieved successfully.",
) -> JSONResponse:
    """
    Return a paginated response with pagination metadata.
    Equivalent to Laravel's LengthAwarePaginator JSON output.
    """
    last_page = max(1, -(-total // per_page))  # ceiling division
    meta = {
        "total": total,
        "page": page,
        "per_page": per_page,
        "last_page": last_page,
        "from": (page - 1) * per_page + 1 if total > 0 else 0,
        "to": min(page * per_page, total),
    }
    return success_response(data=items, message=message, meta=meta)


def error_response(
    message: str = "An error occurred.",
    errors: Optional[dict[str, Any]] = None,
    status_code: int = status.HTTP_400_BAD_REQUEST,
) -> JSONResponse:
    """
    Return a standardised error response.
    Equivalent to: return response()->json(['message' => $msg, 'errors' => $e], 422)
    """
    body: dict[str, Any] = {
        "success": False,
        "message": message,
        "data": None,
    }
    if errors:
        body["errors"] = errors
    return JSONResponse(content=jsonable_encoder(body), status_code=status_code)


def no_content_response() -> JSONResponse:
    """Return 204 No Content (e.g., for DELETE endpoints)."""
    return JSONResponse(content=None, status_code=status.HTTP_204_NO_CONTENT)
