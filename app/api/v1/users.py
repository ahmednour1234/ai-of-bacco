"""
app/api/v1/users.py
--------------------
User management endpoints (admin-only for list/delete; self for update).
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.dependencies import CurrentUserDep, DbDep
from app.core.response import no_content_response, paginated_response, success_response
from app.schemas.user import UserUpdateSchema
from app.services.user_service import UserService
import uuid

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me")
async def get_me(current_user: CurrentUserDep):
    """Return the authenticated user's profile."""
    from app.schemas.user import UserResponseSchema
    return success_response(data=UserResponseSchema.model_validate(current_user))


@router.get("/")
async def list_users(
    db: DbDep,
    current_user: CurrentUserDep,
    page: int = Query(1, ge=1),
    per_page: int = Query(15, ge=1, le=100),
):
    """List all users in the current organization (admin only)."""
    service = UserService(db)
    items, total = await service.list_users(org_id=current_user.org_id, page=page, per_page=per_page)
    return paginated_response(items=items, total=total, page=page, per_page=per_page)


@router.get("/{user_id}")
async def get_user(user_id: uuid.UUID, db: DbDep, current_user: CurrentUserDep):
    service = UserService(db)
    user = await service.get_user(user_id, org_id=current_user.org_id)
    return success_response(data=user)


@router.patch("/{user_id}")
async def update_user(user_id: uuid.UUID, schema: UserUpdateSchema, db: DbDep, current_user: CurrentUserDep):
    service = UserService(db)
    user = await service.update_user(user_id, schema, org_id=current_user.org_id)
    return success_response(data=user, message="User updated.")


@router.delete("/{user_id}", status_code=204)
async def delete_user(user_id: uuid.UUID, db: DbDep, current_user: CurrentUserDep):
    service = UserService(db)
    await service.delete_user(user_id, org_id=current_user.org_id)
    return no_content_response()
