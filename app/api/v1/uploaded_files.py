"""
app/api/v1/uploaded_files.py
------------------------------
File upload & management endpoints.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile

from app.core.dependencies import DbDep, get_request_user, get_storage_driver
from app.core.response import created_response, no_content_response, paginated_response, success_response
from app.models.user import User
from app.services.uploaded_file_service import UploadedFileService
from app.storage.base import StorageDriver

router = APIRouter(prefix="/files", tags=["Uploaded Files"])


@router.post("/", status_code=201)
async def upload_file(
    db: DbDep,
    request_user: User = Depends(get_request_user),
    file: UploadFile = File(...),
    storage: StorageDriver = Depends(get_storage_driver),
):
    """Upload a file; store it via the configured StorageDriver."""
    service = UploadedFileService(db, storage)
    result = await service.upload(
        file=file,
        org_id=request_user.org_id,
        owner_id=request_user.id,
    )
    return created_response(data=result, message="File uploaded.")


@router.get("/")
async def list_files(
    db: DbDep,
    request_user: User = Depends(get_request_user),
    page: int = Query(1, ge=1),
    per_page: int = Query(15, ge=1, le=100),
    storage: StorageDriver = Depends(get_storage_driver),
):
    service = UploadedFileService(db, storage)
    items, total = await service.list_files(org_id=request_user.org_id, page=page, per_page=per_page)
    return paginated_response(items=items, total=total, page=page, per_page=per_page)


@router.get("/{file_id}")
async def get_file(
    file_id: uuid.UUID,
    db: DbDep,
    request_user: User = Depends(get_request_user),
    storage: StorageDriver = Depends(get_storage_driver),
):
    service = UploadedFileService(db, storage)
    result = await service.get_file(file_id, org_id=request_user.org_id)
    return success_response(data=result)


@router.delete("/{file_id}", status_code=204)
async def delete_file(
    file_id: uuid.UUID,
    db: DbDep,
    request_user: User = Depends(get_request_user),
    storage: StorageDriver = Depends(get_storage_driver),
):
    service = UploadedFileService(db, storage)
    await service.delete_file(file_id, org_id=request_user.org_id)
    return no_content_response()
