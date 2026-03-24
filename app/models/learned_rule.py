"""
LearnedRule Model
=================
Stores rules that were extracted from user corrections and are applied
to improve future extraction predictions.

Rule types:
    product_keyword  → a word / phrase that strongly signals a product line
    ignore_pattern   → a regex / phrase that signals the line should be ignored
    meta_pattern     → a regex / phrase for document metadata lines
    total_pattern    → a regex / phrase for total / tax lines
    category_keyword → a word that maps to a product category (category_hint)

Weight:
    0.0 → disabled (corrected to not-product multiple times)
    1.0 → normal signal (adds 1 point to product score)
    2.0 → strong signal (adds 2 points)
    3.0 → very strong signal (adds 3 points, immediately flags as product)
"""

from __future__ import annotations

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class LearnedRule(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "learned_rules"

    # product_keyword | ignore_pattern | meta_pattern | total_pattern | category_keyword
    rule_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # The keyword string or regex pattern value
    rule_value: Mapped[str] = mapped_column(String(512), nullable=False)

    # Scoring weight applied during extraction (0.0 – 3.0)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    # user_correction | system
    source: Mapped[str] = mapped_column(
        String(64), nullable=False, default="user_correction"
    )

    # How many independent corrections have reinforced this rule
    examples_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Only used for category_keyword type — the mapped category name
    category_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Soft-disable without deleting
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return (
            f"<LearnedRule type={self.rule_type} "
            f"value={self.rule_value!r} weight={self.weight}>"
        )
