"""
OrganizationRepository
======================
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.repositories.base import BaseRepository
from app.schemas.organization import OrganizationCreateSchema, OrganizationUpdateSchema


class OrganizationRepository(BaseRepository[Organization, OrganizationCreateSchema, OrganizationUpdateSchema]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, Organization)

    async def get_by_slug(self, slug: str) -> Optional[Organization]:
        stmt = (
            select(Organization)
            .where(Organization.slug == slug, Organization.deleted_at.is_(None))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
