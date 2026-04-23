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
    product_name: Optional[str] = None
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    needs_review: bool = False
    # Provenance from the universal pipeline — unpacked into DB columns on persist
    extra_metadata: Optional[dict] = field(default=None)
    # Extended fields for normalization / validation pipeline
    raw_unit: Optional[str] = None               # unit string exactly as found in source
    normalized_unit: Optional[str] = None        # canonical unit (e.g. "pcs" → "pc")
    model_code: Optional[str] = None             # product model / SKU code
    total: Optional[float] = None                # line total (qty × price)
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
    product_name: Optional[str] = None
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    needs_review: bool

    # Universal pipeline provenance
    region_id: Optional[str] = None
    region_type: Optional[str] = None
    page_number: Optional[int] = None
    coordinates: Optional[dict] = None
    classification_source: Optional[str] = None

    # Review status
    status: str                           # pending | approved | rejected | corrected
    corrected_label: Optional[str] = None
    corrected_name: Optional[str] = None
    corrected_description: Optional[str] = None
    corrected_quantity: Optional[float] = None
    corrected_unit: Optional[str] = None
    corrected_brand: Optional[str] = None
    corrected_category: Optional[str] = None
    corrected_price: Optional[float] = None
    correction_note: Optional[str] = None

    # Extended normalization fields (populated by pipeline)
    raw_unit: Optional[str] = None
    normalized_unit: Optional[str] = None
    model_code: Optional[str] = None
    total: Optional[float] = None
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
    contains_products: Optional[bool] = None
    document_type_guess: Optional[str] = None
    detection_confidence: Optional[float] = None
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
    contains_products: Optional[bool] = None
    document_type_guess: Optional[str] = None
    detection_confidence: Optional[float] = None
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
    corrected_label: Optional[str] = Field(
        None,
        description="product | description | meta | total | ignore",
    )
    corrected_name: Optional[str] = None
    corrected_description: Optional[str] = None
    corrected_quantity: Optional[float] = None
    corrected_unit: Optional[str] = None
    corrected_brand: Optional[str] = None
    corrected_category: Optional[str] = None
    corrected_price: Optional[float] = None
    correction_note: Optional[str] = None


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
    category: Optional[str] = None
    brand: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
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
    correct_name: Optional[str] = None
    correct_category: Optional[str] = None
    correct_brand: Optional[str] = None
    correct_description: Optional[str] = None
    correct_quantity: Optional[float] = None
    correct_unit: Optional[str] = None
    correct_price: Optional[float] = None


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
    category_hint: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
