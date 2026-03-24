"""
app/schemas/extraction.py
=========================
Pydantic schemas for the feedback-driven extraction system.

Covers:
- CandidateData          → in-memory result from the extraction pipeline (not DB)
- ExtractionCandidateSchema   → API response for a single candidate row
- ExtractionSessionSchema     → API response for a session + its candidates
- FeedbackItemSchema          → user input for a single correction
- BulkFeedbackSchema          → user input for bulk corrections in one call
- ApprovedProductSchema       → stripped product view (only approved items)
- TrainingExampleSchema       → offline retraining export format
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema, BaseResponseSchema


# ─────────────────────────────────────────────────────────────────────────────
# Internal pipeline result — pure Python, no DB interaction
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CandidateData:
    """
    Produced by UniversalExtractionPipeline for each product candidate.
    Handed to ExtractionSessionService which persists it as ExtractionCandidate.
    """
    raw_text: str
    predicted_label: str      # product | description | meta | total | ignore | price_row | header
    confidence: float         # 0.0 – 1.0
    position: int
    product_name: str | None = None
    description: str | None = None
    quantity: float | None = None
    unit: str | None = None
    brand: str | None = None
    category: str | None = None
    price: float | None = None
    needs_review: bool = False
    # Provenance from the universal pipeline — unpacked into DB columns on persist
    extra_metadata: dict | None = field(default=None)
    # Extended fields for normalization / validation pipeline
    raw_unit: str | None = None               # unit string exactly as found in source
    normalized_unit: str | None = None        # canonical unit (e.g. "pcs" → "pc")
    model_code: str | None = None             # product model / SKU code
    total: float | None = None                # line total (qty × price)
    validation_flags: list = field(default_factory=list)  # ["price_looks_like_qty", …]


# ─────────────────────────────────────────────────────────────────────────────
# API response schemas
# ─────────────────────────────────────────────────────────────────────────────

class ExtractionCandidateSchema(BaseResponseSchema):
    id: uuid.UUID
    session_id: uuid.UUID
    position: int
    raw_text: str

    # Prediction
    predicted_label: str
    confidence: float
    product_name: str | None = None
    description: str | None = None
    quantity: float | None = None
    unit: str | None = None
    brand: str | None = None
    category: str | None = None
    price: float | None = None
    needs_review: bool

    # Universal pipeline provenance
    region_id: str | None = None
    region_type: str | None = None
    page_number: int | None = None
    coordinates: dict | None = None
    classification_source: str | None = None

    # Review status
    status: str                           # pending | approved | rejected | corrected
    corrected_label: str | None = None
    corrected_name: str | None = None
    corrected_description: str | None = None
    corrected_quantity: float | None = None
    corrected_unit: str | None = None
    corrected_brand: str | None = None
    corrected_category: str | None = None
    corrected_price: float | None = None
    correction_note: str | None = None

    # Extended normalization fields (populated by pipeline)
    raw_unit: str | None = None
    normalized_unit: str | None = None
    model_code: str | None = None
    total: float | None = None
    validation_flags: list[str] = Field(default_factory=list)

    created_at: datetime
    updated_at: datetime


class ExtractionSessionSchema(BaseResponseSchema):
    id: uuid.UUID
    filename: str
    file_type: str
    status: str
    total_candidates: int
    reviewed_count: int
    approved_count: int
    rejected_count: int
    # Universal pipeline detection results
    contains_products: bool | None = None
    document_type_guess: str | None = None
    detection_confidence: float | None = None
    created_at: datetime
    updated_at: datetime
    candidates: list[ExtractionCandidateSchema] = Field(default_factory=list)


class ExtractionSessionSummarySchema(BaseResponseSchema):
    """Session without candidates — for list views."""
    id: uuid.UUID
    filename: str
    file_type: str
    status: str
    total_candidates: int
    reviewed_count: int
    approved_count: int
    rejected_count: int
    # Universal pipeline detection results
    contains_products: bool | None = None
    document_type_guess: str | None = None
    detection_confidence: float | None = None
    created_at: datetime
    updated_at: datetime


# ─────────────────────────────────────────────────────────────────────────────
# Feedback input schemas
# ─────────────────────────────────────────────────────────────────────────────

class FeedbackItemSchema(BaseSchema):
    """Single candidate correction submitted by the user."""
    candidate_id: uuid.UUID

    # approve | reject | correct
    action: str = Field(..., pattern="^(approve|reject|correct)$")

    # Required only when action == "correct"
    corrected_label: str | None = Field(
        None,
        description="product | description | meta | total | ignore",
    )
    corrected_name: str | None = None
    corrected_description: str | None = None
    corrected_quantity: float | None = None
    corrected_unit: str | None = None
    corrected_brand: str | None = None
    corrected_category: str | None = None
    corrected_price: float | None = None
    correction_note: str | None = None


class BulkFeedbackSchema(BaseSchema):
    """Bulk corrections for one session submitted in a single request."""
    feedbacks: list[FeedbackItemSchema]


class ApproveAllSchema(BaseSchema):
    """Approve every pending candidate in the session that is predicted as product."""
    only_products: bool = True


# ─────────────────────────────────────────────────────────────────────────────
# Approved product view
# ─────────────────────────────────────────────────────────────────────────────

class ApprovedProductSchema(BaseResponseSchema):
    """
    Collapsed view of an approved / corrected product candidate.
    Correction wins over prediction — shows effective_* values.
    """
    candidate_id: uuid.UUID
    product_name: str
    category: str | None = None
    brand: str | None = None
    quantity: float | None = None
    unit: str | None = None
    description: str | None = None
    price: float | None = None
    source_line: str


class ExtractionProductsResultSchema(BaseResponseSchema):
    session_id: uuid.UUID
    filename: str
    count: int
    products: list[ApprovedProductSchema]


# ─────────────────────────────────────────────────────────────────────────────
# Training data export
# ─────────────────────────────────────────────────────────────────────────────

class TrainingExampleSchema(BaseResponseSchema):
    """One line of offline training data for future model fine-tuning."""
    raw_text: str
    correct_label: str
    correct_name: str | None = None
    correct_category: str | None = None
    correct_brand: str | None = None
    correct_description: str | None = None
    correct_quantity: float | None = None
    correct_unit: str | None = None
    correct_price: float | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Learned-rule view (readonly)
# ─────────────────────────────────────────────────────────────────────────────

class LearnedRuleSchema(BaseResponseSchema):
    id: uuid.UUID
    rule_type: str
    rule_value: str
    weight: float
    source: str
    examples_count: int
    category_hint: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
