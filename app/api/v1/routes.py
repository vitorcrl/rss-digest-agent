from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.domain.models import Feed
from app.repositories.article_repository import ArticleRepository
from app.repositories.digest_repository import DigestRepository
from app.repositories.feed_repository import FeedRepository
from app.services.digest_service import DigestService
from app.api.v1.schemas import (
    ArticleResponse,
    DigestRunDetail,
    DigestRunResponse,
    DigestTriggerResponse,
    FeedCreate,
    FeedResponse,
    FeedUpdate,
)

router = APIRouter()


# --- Feeds ---

@router.post("/feeds", response_model=FeedResponse, status_code=201)
async def create_feed(body: FeedCreate, session: AsyncSession = Depends(get_session)):
    repo = FeedRepository(session)
    if await repo.get_by_url(str(body.url)):
        raise HTTPException(status_code=409, detail="Feed already exists")
    feed = Feed(url=str(body.url), name=body.name, category=body.category)
    return await repo.create(feed)


@router.get("/feeds", response_model=list[FeedResponse])
async def list_feeds(session: AsyncSession = Depends(get_session)):
    return await FeedRepository(session).get_all()


@router.patch("/feeds/{feed_id}", response_model=FeedResponse)
async def update_feed(
    feed_id: UUID,
    body: FeedUpdate,
    session: AsyncSession = Depends(get_session),
):
    repo = FeedRepository(session)
    feed = await repo.get_by_id(feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    return await repo.update_active(feed, body.active)


# --- Digest ---

@router.post("/digest/run", response_model=DigestTriggerResponse, status_code=202)
async def trigger_digest(session: AsyncSession = Depends(get_session)):
    digest = await DigestService(session).run()
    return DigestTriggerResponse(digest_run_id=digest.id, status=digest.status.value)


@router.get("/digest/runs", response_model=list[DigestRunResponse])
async def list_digest_runs(
    limit: int = Query(default=10, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    return await DigestRepository(session).get_recent(limit=limit)


@router.get("/digest/runs/{digest_id}", response_model=DigestRunDetail)
async def get_digest_run(digest_id: UUID, session: AsyncSession = Depends(get_session)):
    digest = await DigestRepository(session).get_by_id(digest_id)
    if not digest:
        raise HTTPException(status_code=404, detail="Digest run not found")
    articles = await ArticleRepository(session).get_by_date(
        digest.run_date, relevant_only=True
    )
    return DigestRunDetail(
        **DigestRunResponse.model_validate(digest).model_dump(),
        articles=[ArticleResponse.model_validate(a) for a in articles],
    )


# --- Articles ---

@router.get("/articles", response_model=list[ArticleResponse])
async def list_articles(
    run_date: date | None = Query(default=None),
    relevant_only: bool = Query(default=False),
    feed_id: UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    target_date = run_date or date.today()
    return await ArticleRepository(session).get_by_date(
        target_date, relevant_only=relevant_only, feed_id=feed_id
    )
