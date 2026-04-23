"""
app/api/v1/suppliers.py
------------------------
Supplier CRUD endpoints.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.core.dependencies import CurrentUserDep, DbDep
from app.core.response import created_response, no_content_response, paginated_response, success_response
from app.schemas.supplier import SupplierCreateSchema, SupplierUpdateSchema
from app.services.supplier_service import SupplierService

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


@router.get("/")
async def list_suppliers(
    db: DbDep,
    current_user: CurrentUserDep,
    page: int = Query(1, ge=1),
    per_page: int = Query(15, ge=1, le=100),
    search: Optional[str] = Query(None),
):
    service = SupplierService(db)
    items, total = await service.list_suppliers(
        org_id=current_user.org_id, page=page, per_page=per_page, search=search
    )
    return paginated_response(items=items, total=total, page=page, per_page=per_page)


@router.post("/", status_code=201)
async def create_supplier(schema: SupplierCreateSchema, db: DbDep, current_user: CurrentUserDep):
    service = SupplierService(db)
    supplier = await service.create_supplier(
        schema=schema, org_id=current_user.org_id, owner_id=current_user.id
    )
    return created_response(data=supplier, message="Supplier created.")


@router.get("/{supplier_id}")
async def get_supplier(supplier_id: uuid.UUID, db: DbDep, current_user: CurrentUserDep):
    service = SupplierService(db)
    supplier = await service.get_supplier(supplier_id, org_id=current_user.org_id)
    return success_response(data=supplier)


@router.patch("/{supplier_id}")
async def update_supplier(
    supplier_id: uuid.UUID,
    schema: SupplierUpdateSchema,
    db: DbDep,
    current_user: CurrentUserDep,
):
    service = SupplierService(db)
    supplier = await service.update_supplier(supplier_id, schema, org_id=current_user.org_id)
    return success_response(data=supplier, message="Supplier updated.")


@router.delete("/{supplier_id}", status_code=204)
async def delete_supplier(supplier_id: uuid.UUID, db: DbDep, current_user: CurrentUserDep):
    service = SupplierService(db)
    await service.delete_supplier(supplier_id, org_id=current_user.org_id)
    return no_content_response()
