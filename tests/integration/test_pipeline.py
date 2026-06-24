"""
Integration tests — require a real PostgreSQL database.

Run with:
    docker compose up -d db
    pytest tests/integration/ -v
"""
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domain.enums import DigestStatus
from app.domain.models import Base, Feed
from app.repositories.article_repository import ArticleRepository
from app.repositories.digest_repository import DigestRepository
from app.repositories.feed_repository import FeedRepository
from app.services.digest_service import DigestService
from tests.conftest import make_claude_response

TEST_DATABASE_URL = "postgresql+asyncpg://user:pass@localhost:5432/digest_db"

pytestmark = pytest.mark.integration

MOCK_RSS_ENTRIES = [
    {
        "title": "How Shopify scaled Kafka to 1M events/sec",
        "link": "https://example.com/kafka-shopify",
        "published_parsed": (2026, 6, 24, 10, 0, 0, 0, 0, 0),
    },
    {
        "title": "10 tips for better CSS animations",
        "link": "https://example.com/css-tips",
        "published_parsed": (2026, 6, 24, 9, 0, 0, 0, 0, 0),
    },
]


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s

    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_feed(session: AsyncSession) -> Feed:
    feed = Feed(
        name="Test Feed",
        url="https://example.com/feed.xml",
        category="backend",
        active=True,
    )
    return await FeedRepository(session).create(feed)


def make_parsed_mock(entries):
    from unittest.mock import MagicMock
    mock = MagicMock()
    mock.get.side_effect = lambda key, default=None: {"status": 200}.get(key, default)
    mock.entries = [_make_entry(**e) for e in entries]
    return mock


def _make_entry(title, link, published_parsed=None, **_):
    from unittest.mock import MagicMock
    entry = MagicMock()
    entry.get.side_effect = lambda key, default="": {"title": title, "link": link}.get(key, default)
    entry.published_parsed = published_parsed
    entry.updated_parsed = None
    entry.__contains__ = lambda self, key: key == "published_parsed" and published_parsed is not None
    return entry


class TestFullPipeline:
    async def test_pipeline_persists_articles_and_marks_delivered(
        self, session: AsyncSession, seeded_feed: Feed
    ):
        relevance_response = make_claude_response('[{"index": 0, "score": 9}, {"index": 1, "score": 2}]')
        summary_response = make_claude_response("Shopify migrou seus consumers Kafka.")

        with (
            patch("app.services.rss_service.feedparser.parse", return_value=make_parsed_mock(MOCK_RSS_ENTRIES)),
            patch("app.services.ai_service.anthropic.AsyncAnthropic") as mock_cls,
            patch("app.services.delivery_service.httpx.AsyncClient") as mock_http,
        ):
            client = AsyncMock()
            mock_cls.return_value = client
            client.messages.create.side_effect = [relevance_response, summary_response]

            http_client = AsyncMock()
            mock_http.return_value.__aenter__.return_value = http_client
            http_client.post.return_value = AsyncMock(raise_for_status=lambda: None)

            digest = await DigestService(session).run(date(2026, 6, 24))

        assert digest.status == DigestStatus.delivered
        assert digest.articles_processed == 2
        assert digest.articles_selected == 1
        assert digest.tokens_used > 0

        articles = await ArticleRepository(session).get_by_date(date(2026, 6, 24))
        assert len(articles) == 2

        relevant = [a for a in articles if a.is_relevant]
        assert len(relevant) == 1
        assert relevant[0].title == "How Shopify scaled Kafka to 1M events/sec"
        assert relevant[0].summary_pt is not None

    async def test_pipeline_is_idempotent_when_already_delivered(
        self, session: AsyncSession, seeded_feed: Feed
    ):
        relevance_response = make_claude_response('[{"index": 0, "score": 9}, {"index": 1, "score": 2}]')
        summary_response = make_claude_response("Resumo.")

        with (
            patch("app.services.rss_service.feedparser.parse", return_value=make_parsed_mock(MOCK_RSS_ENTRIES)),
            patch("app.services.ai_service.anthropic.AsyncAnthropic") as mock_cls,
            patch("app.services.delivery_service.httpx.AsyncClient") as mock_http,
        ):
            client = AsyncMock()
            mock_cls.return_value = client
            client.messages.create.side_effect = [relevance_response, summary_response]

            http_client = AsyncMock()
            mock_http.return_value.__aenter__.return_value = http_client
            http_client.post.return_value = AsyncMock(raise_for_status=lambda: None)

            first = await DigestService(session).run(date(2026, 6, 24))
            second = await DigestService(session).run(date(2026, 6, 24))

        assert first.id == second.id
        assert second.status == DigestStatus.delivered
        assert client.messages.create.call_count == 2

    async def test_duplicate_articles_not_reprocessed(
        self, session: AsyncSession, seeded_feed: Feed
    ):
        relevance_response = make_claude_response('[{"index": 0, "score": 9}, {"index": 1, "score": 2}]')
        summary_response = make_claude_response("Resumo.")

        with (
            patch("app.services.rss_service.feedparser.parse", return_value=make_parsed_mock(MOCK_RSS_ENTRIES)),
            patch("app.services.ai_service.anthropic.AsyncAnthropic") as mock_cls,
            patch("app.services.delivery_service.httpx.AsyncClient") as mock_http,
        ):
            client = AsyncMock()
            mock_cls.return_value = client
            client.messages.create.side_effect = [relevance_response, summary_response, make_claude_response("[]")]

            http_client = AsyncMock()
            mock_http.return_value.__aenter__.return_value = http_client
            http_client.post.return_value = AsyncMock(raise_for_status=lambda: None)

            await DigestService(session).run(date(2026, 6, 24))
            second_digest = await DigestService(session).run(date(2026, 6, 25))

        assert second_digest.articles_processed == 0
        assert second_digest.status == DigestStatus.delivered
