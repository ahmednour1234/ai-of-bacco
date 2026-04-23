"""
UploadedFile Model
==================
Tracks every file uploaded by a user (PDF, image, invoice, supplier sheet).
The physical file lives in the storage driver (local or S3).
"""

from __future__ import annotations
from typing import Optional

import enum

from sqlalchemy import BigInteger, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin


class UploadedFileStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class UploadedFileType(str, enum.Enum):
    PDF = "pdf"
    IMAGE = "image"
    INVOICE = "invoice"
    SUPPLIER_FILE = "supplier_file"
    OTHER = "other"


class UploadedFile(UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin, Base):
    __tablename__ = "uploaded_files"

    # ── File Identity ─────────────────────────────────────────────────────────
    original_name: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    # ── Classification ────────────────────────────────────────────────────────
    file_type: Mapped[UploadedFileType] = mapped_column(
        Enum(UploadedFileType, name="uploaded_file_type_enum"),
        nullable=False,
        default=UploadedFileType.OTHER,
    )
    status: Mapped[UploadedFileStatus] = mapped_column(
        Enum(UploadedFileStatus, name="uploaded_file_status_enum"),
        nullable=False,
        default=UploadedFileStatus.PENDING,
        index=True,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    owner: Mapped["User"] = relationship(  # noqa: F821
        "User", back_populates="uploaded_files", foreign_keys="UploadedFile.owner_id", lazy="noload"
    )
    document: Mapped[Optional["Document"]] = relationship(  # noqa: F821
        "Document", back_populates="uploaded_file", uselist=False, lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<UploadedFile id={self.id} name={self.original_name!r} status={self.status}>"
