"""
app/api/v1/documents.py
------------------------
Document CRUD endpoints.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.core.dependencies import CurrentUserDep, DbDep
from app.core.response import no_content_response, paginated_response, success_response
from app.schemas.document import DocumentUpdateSchema
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.get("/")
async def list_documents(
    db: DbDep,
    current_user: CurrentUserDep,
    page: int = Query(1, ge=1),
    per_page: int = Query(15, ge=1, le=100),
):
    service = DocumentService(db)
    items, total = await service.list_documents(org_id=current_user.org_id, page=page, per_page=per_page)
    return paginated_response(items=items, total=total, page=page, per_page=per_page)


@router.get("/{document_id}")
async def get_document(document_id: uuid.UUID, db: DbDep, current_user: CurrentUserDep):
    service = DocumentService(db)
    doc = await service.get_document(document_id, org_id=current_user.org_id)
    return success_response(data=doc)


@router.patch("/{document_id}")
async def update_document(
    document_id: uuid.UUID,
    schema: DocumentUpdateSchema,
    db: DbDep,
    current_user: CurrentUserDep,
):
    service = DocumentService(db)
    doc = await service.update_document(document_id, schema, org_id=current_user.org_id)
    return success_response(data=doc, message="Document updated.")


@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id: uuid.UUID, db: DbDep, current_user: CurrentUserDep):
    service = DocumentService(db)
    await service.delete_document(document_id, org_id=current_user.org_id)
    return no_content_response()
