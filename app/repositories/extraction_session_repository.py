"""
ExtractionSessionRepository
============================
Data-access layer for ExtractionSession.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.extraction_session import ExtractionSession
from app.repositories.base import BaseRepository


class ExtractionSessionRepository(
    BaseRepository[ExtractionSession, dict, dict]
):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, ExtractionSession)

    async def get_with_candidates(
        self, session_id: uuid.UUID
    ) -> Optional[ExtractionSession]:
        """Load session with all candidate rows eagerly."""
        stmt = (
            select(ExtractionSession)
            .where(ExtractionSession.id == session_id)
            .options(selectinload(ExtractionSession.candidates))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_session(
        self,
        filename: str,
        file_type: str,
        raw_text: Optional[str] = None,
        contains_products: Optional[bool] = None,
        document_type_guess: Optional[str] = None,
        detection_confidence: Optional[float] = None,
        detection_metadata: Optional[dict] = None,
    ) -> ExtractionSession:
        session = ExtractionSession(
            filename=filename,
            file_type=file_type,
            status="pending",
            total_candidates=0,
            reviewed_count=0,
            approved_count=0,
            rejected_count=0,
            raw_text=raw_text,
            contains_products=contains_products,
            document_type_guess=document_type_guess,
            detection_confidence=detection_confidence,
            detection_metadata=detection_metadata,
        )
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def update_counts(
        self,
        session: ExtractionSession,
        total: int,
        reviewed: int,
        approved: int,
        rejected: int,
        status: Optional[str] = None,
    ) -> ExtractionSession:
        session.total_candidates = total
        session.reviewed_count = reviewed
        session.approved_count = approved
        session.rejected_count = rejected
        if status:
            session.status = status
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session
