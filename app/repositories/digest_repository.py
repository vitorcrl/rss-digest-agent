from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import DigestRun


class DigestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, digest_run: DigestRun) -> DigestRun:
        self.session.add(digest_run)
        await self.session.commit()
        await self.session.refresh(digest_run)
        return digest_run

    async def get_by_date(self, run_date: date) -> DigestRun | None:
        result = await self.session.execute(
            select(DigestRun).where(DigestRun.run_date == run_date)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, digest_id: UUID) -> DigestRun | None:
        result = await self.session.execute(
            select(DigestRun).where(DigestRun.id == digest_id)
        )
        return result.scalar_one_or_none()

    async def get_recent(self, limit: int = 10) -> list[DigestRun]:
        result = await self.session.execute(
            select(DigestRun).order_by(DigestRun.run_date.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def save(self, digest_run: DigestRun) -> DigestRun:
        await self.session.commit()
        await self.session.refresh(digest_run)
        return digest_run
