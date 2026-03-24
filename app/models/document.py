"""
Document Model
==============
Represents the processed content of an uploaded file.
Contains the raw extracted text and structured parsed data (JSONB).
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin


class DocumentType(str, enum.Enum):
    INVOICE = "invoice"
    SUPPLIER_CATALOG = "supplier_catalog"
    PRICE_LIST = "price_list"
    OTHER = "other"


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PARSING = "parsing"
    EXTRACTING = "extracting"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin, Base):
    __tablename__ = "documents"

    # ── Source ────────────────────────────────────────────────────────────────
    uploaded_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("uploaded_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Classification ────────────────────────────────────────────────────────
    doc_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="document_type_enum"),
        nullable=False,
        default=DocumentType.OTHER,
        index=True,
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status_enum"),
        nullable=False,
        default=DocumentStatus.PENDING,
        index=True,
    )

    # ── Content ───────────────────────────────────────────────────────────────
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    uploaded_file: Mapped["UploadedFile"] = relationship(  # noqa: F821
        "UploadedFile", back_populates="document", lazy="noload"
    )
    extracted_items: Mapped[list["ExtractedItem"]] = relationship(  # noqa: F821
        "ExtractedItem", back_populates="document", lazy="noload"
    )
    invoice: Mapped["Invoice | None"] = relationship(  # noqa: F821
        "Invoice", back_populates="document", uselist=False, lazy="noload"
    )
    ai_jobs: Mapped[list["AIJob"]] = relationship(  # noqa: F821
        "AIJob", back_populates="document", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id} type={self.doc_type} status={self.status}>"
