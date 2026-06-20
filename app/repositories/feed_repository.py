from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Feed


class FeedRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, feed: Feed) -> Feed:
        self.session.add(feed)
        await self.session.commit()
        await self.session.refresh(feed)
        return feed

    async def get_all(self) -> list[Feed]:
        result = await self.session.execute(select(Feed))
        return list(result.scalars().all())

    async def get_active(self) -> list[Feed]:
        result = await self.session.execute(select(Feed).where(Feed.active.is_(True)))
        return list(result.scalars().all())

    async def get_by_id(self, feed_id: UUID) -> Feed | None:
        result = await self.session.execute(select(Feed).where(Feed.id == feed_id))
        return result.scalar_one_or_none()

    async def get_by_url(self, url: str) -> Feed | None:
        result = await self.session.execute(select(Feed).where(Feed.url == url))
        return result.scalar_one_or_none()

    async def update_active(self, feed: Feed, active: bool) -> Feed:
        feed.active = active
        await self.session.commit()
        await self.session.refresh(feed)
        return feed
