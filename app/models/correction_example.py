"""
CorrectionExample Model
=======================
Stores approved "right answer" examples used for similarity-based label
retrieval during future extraction runs.

When a candidate is approved or corrected, a CorrectionExample is saved.
During the next extraction session the service retrieves all examples,
computes word-overlap similarity against every candidate line, and overrides
the machine prediction when a high-confidence match exists.

This implements a non-parametric nearest-neighbour correction layer that
improves over time as more feedback is supplied — without any ML model.
"""

from __future__ import annotations
from typing import Optional

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class CorrectionExample(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "correction_examples"

    # Original source line from the document
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Lower-cased, whitespace-normalised version used for similarity matching
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    # Correct label (product | description | meta | total | ignore | price_row)
    correct_label: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # Correct field values (may differ from the original prediction)
    correct_name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    correct_category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    correct_brand: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    correct_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    correct_quantity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    correct_unit: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    correct_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # How many extraction runs retrieved this example
    use_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return (
            f"<CorrectionExample label={self.correct_label} "
            f"text={self.raw_text[:50]!r}>"
        )
