from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, HttpUrl


# --- Feed ---

class FeedCreate(BaseModel):
    url: HttpUrl
    name: str
    category: str


class FeedResponse(BaseModel):
    id: UUID
    url: str
    name: str
    category: str
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class FeedUpdate(BaseModel):
    active: bool


# --- Article ---

class ArticleResponse(BaseModel):
    id: UUID
    feed_id: UUID
    title: str
    url: str
    relevance_score: int | None
    summary_pt: str | None
    is_relevant: bool
    published_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Digest ---

class DigestRunResponse(BaseModel):
    id: UUID
    run_date: date
    status: str
    articles_processed: int
    articles_selected: int
    tokens_used: int
    delivered_at: datetime | None
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DigestRunDetail(DigestRunResponse):
    articles: list[ArticleResponse] = []


class DigestTriggerResponse(BaseModel):
    digest_run_id: UUID
    status: str
