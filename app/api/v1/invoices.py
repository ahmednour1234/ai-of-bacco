"""
app/api/v1/invoices.py
-----------------------
Invoice CRUD endpoints.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.core.dependencies import CurrentUserDep, DbDep
from app.core.response import created_response, no_content_response, paginated_response, success_response
from app.schemas.invoice import InvoiceCreateSchema, InvoiceUpdateSchema
from app.services.invoice_service import InvoiceService

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.get("/")
async def list_invoices(
    db: DbDep,
    current_user: CurrentUserDep,
    page: int = Query(1, ge=1),
    per_page: int = Query(15, ge=1, le=100),
):
    service = InvoiceService(db)
    items, total = await service.list_invoices(org_id=current_user.org_id, page=page, per_page=per_page)
    return paginated_response(items=items, total=total, page=page, per_page=per_page)


@router.post("/", status_code=201)
async def create_invoice(schema: InvoiceCreateSchema, db: DbDep, current_user: CurrentUserDep):
    service = InvoiceService(db)
    invoice = await service.create_invoice(
        schema=schema, org_id=current_user.org_id, owner_id=current_user.id
    )
    return created_response(data=invoice, message="Invoice created.")


@router.get("/{invoice_id}")
async def get_invoice(invoice_id: uuid.UUID, db: DbDep, current_user: CurrentUserDep):
    service = InvoiceService(db)
    invoice = await service.get_invoice(invoice_id, org_id=current_user.org_id)
    return success_response(data=invoice)


@router.patch("/{invoice_id}")
async def update_invoice(
    invoice_id: uuid.UUID,
    schema: InvoiceUpdateSchema,
    db: DbDep,
    current_user: CurrentUserDep,
):
    service = InvoiceService(db)
    invoice = await service.update_invoice(invoice_id, schema, org_id=current_user.org_id)
    return success_response(data=invoice, message="Invoice updated.")


@router.delete("/{invoice_id}", status_code=204)
async def delete_invoice(invoice_id: uuid.UUID, db: DbDep, current_user: CurrentUserDep):
    service = InvoiceService(db)
    await service.delete_invoice(invoice_id, org_id=current_user.org_id)
    return no_content_response()
