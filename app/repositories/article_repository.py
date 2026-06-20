from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Article


class ArticleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_bulk(self, articles: list[Article]) -> None:
        self.session.add_all(articles)
        await self.session.commit()

    async def get_by_content_hashes(self, hashes: set[str]) -> set[str]:
        result = await self.session.execute(
            select(Article.content_hash).where(Article.content_hash.in_(hashes))
        )
        return set(result.scalars().all())

    async def get_by_date(
        self,
        run_date: date,
        relevant_only: bool = False,
        feed_id: UUID | None = None,
    ) -> list[Article]:
        stmt = select(Article).where(
            Article.created_at >= run_date,
            Article.created_at < run_date + timedelta(days=1),
        )
        if relevant_only:
            stmt = stmt.where(Article.is_relevant.is_(True))
        if feed_id:
            stmt = stmt.where(Article.feed_id == feed_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_relevant_by_date(self, run_date: date, limit: int) -> list[Article]:
        result = await self.session.execute(
            select(Article)
            .where(
                Article.is_relevant.is_(True),
                Article.created_at >= run_date,
            )
            .order_by(Article.relevance_score.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
