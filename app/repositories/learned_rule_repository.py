"""
LearnedRuleRepository
=====================
Data-access layer for LearnedRule.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.learned_rule import LearnedRule
from app.repositories.base import BaseRepository


class LearnedRuleRepository(BaseRepository[LearnedRule, dict, dict]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, LearnedRule)

    async def get_active(self) -> list[LearnedRule]:
        """Return all active rules ordered by weight descending."""
        stmt = (
            select(LearnedRule)
            .where(LearnedRule.is_active.is_(True))
            .order_by(LearnedRule.weight.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_type(self, rule_type: str) -> list[LearnedRule]:
        stmt = (
            select(LearnedRule)
            .where(
                LearnedRule.rule_type == rule_type,
                LearnedRule.is_active.is_(True),
            )
            .order_by(LearnedRule.weight.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_by_value(
        self, rule_type: str, rule_value: str
    ) -> LearnedRule | None:
        """Case-insensitive lookup — used before inserting to avoid duplicates."""
        stmt = select(LearnedRule).where(
            LearnedRule.rule_type == rule_type,
            LearnedRule.rule_value == rule_value.lower(),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_keyword(
        self,
        rule_type: str,
        rule_value: str,
        weight_delta: float = 0.5,
        category_hint: str | None = None,
    ) -> LearnedRule:
        """
        Insert a new rule or increase its weight if it already exists.
        Weight is capped at 3.0.
        """
        existing = await self.find_by_value(rule_type, rule_value)
        if existing:
            existing.weight = min(3.0, existing.weight + weight_delta)
            existing.examples_count += 1
            self.db.add(existing)
            await self.db.flush()
            await self.db.refresh(existing)
            return existing

        new_rule = LearnedRule(
            rule_type=rule_type,
            rule_value=rule_value.lower(),
            weight=weight_delta,
            source="user_correction",
            examples_count=1,
            category_hint=category_hint,
            is_active=True,
        )
        self.db.add(new_rule)
        await self.db.flush()
        await self.db.refresh(new_rule)
        return new_rule

    async def demote_keyword(
        self,
        rule_value: str,
        weight_delta: float = 0.5,
    ) -> None:
        """Decrease weight of a product_keyword rule (false positive feedback)."""
        existing = await self.find_by_value("product_keyword", rule_value)
        if existing:
            existing.weight = max(0.0, existing.weight - weight_delta)
            if existing.weight == 0.0:
                existing.is_active = False
            self.db.add(existing)
            await self.db.flush()
