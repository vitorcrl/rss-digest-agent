"""
Unit tests for repositories — mock the AsyncSession to cover uncovered branches.
"""
import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.enums import DigestStatus
from app.domain.models import Article, DigestRun, Feed
from app.repositories.article_repository import ArticleRepository
from app.repositories.digest_repository import DigestRepository
from app.repositories.feed_repository import FeedRepository


def _mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    return session


def _make_feed(**kwargs) -> Feed:
    feed = Feed(
        name=kwargs.get("name", "Test Feed"),
        url=kwargs.get("url", "https://example.com/feed.xml"),
        category=kwargs.get("category", "backend"),
        active=kwargs.get("active", True),
    )
    feed.id = uuid.uuid4()
    feed.created_at = datetime(2026, 6, 24, 8, 0, 0)
    return feed


def _make_article(feed_id: uuid.UUID | None = None) -> Article:
    article = Article(
        feed_id=feed_id or uuid.uuid4(),
        title="Article Title",
        url="https://example.com/article",
        content_hash="abc123",
        published_at=datetime(2026, 6, 24, 10, 0, 0),
        is_relevant=True,
        relevance_score=8,
    )
    article.id = uuid.uuid4()
    article.created_at = datetime(2026, 6, 24, 10, 0, 0)
    return article


def _make_digest(**kwargs) -> DigestRun:
    digest = DigestRun(
        run_date=kwargs.get("run_date", date(2026, 6, 24)),
        status=kwargs.get("status", DigestStatus.delivered),
        articles_processed=5,
        articles_selected=2,
        tokens_used=1000,
    )
    digest.id = uuid.uuid4()
    digest.created_at = datetime(2026, 6, 24, 7, 0, 0)
    return digest


def _scalar_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    result.scalars.return_value.all.return_value = [value] if value else []
    return result


def _scalars_result(values):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


# --- FeedRepository ---

class TestFeedRepository:
    async def test_create_commits_and_returns_feed(self):
        session = _mock_session()
        feed = _make_feed()
        repo = FeedRepository(session)

        result = await repo.create(feed)

        session.add.assert_called_once_with(feed)
        session.commit.assert_called_once()
        session.refresh.assert_called_once_with(feed)

    async def test_get_all_returns_list(self):
        session = _mock_session()
        feeds = [_make_feed(), _make_feed(name="Feed 2", url="https://other.com/rss")]
        session.execute.return_value = _scalars_result(feeds)
        repo = FeedRepository(session)

        result = await repo.get_all()

        assert result == feeds

    async def test_get_active_filters_active(self):
        session = _mock_session()
        feed = _make_feed()
        session.execute.return_value = _scalars_result([feed])
        repo = FeedRepository(session)

        result = await repo.get_active()

        assert result == [feed]

    async def test_get_by_id_found(self):
        session = _mock_session()
        feed = _make_feed()
        session.execute.return_value = _scalar_result(feed)
        repo = FeedRepository(session)

        result = await repo.get_by_id(feed.id)

        assert result == feed

    async def test_get_by_id_not_found(self):
        session = _mock_session()
        session.execute.return_value = _scalar_result(None)
        repo = FeedRepository(session)

        result = await repo.get_by_id(uuid.uuid4())

        assert result is None

    async def test_get_by_url_found(self):
        session = _mock_session()
        feed = _make_feed()
        session.execute.return_value = _scalar_result(feed)
        repo = FeedRepository(session)

        result = await repo.get_by_url("https://example.com/feed.xml")

        assert result == feed

    async def test_get_by_url_not_found(self):
        session = _mock_session()
        session.execute.return_value = _scalar_result(None)
        repo = FeedRepository(session)

        result = await repo.get_by_url("https://nope.com/feed.xml")

        assert result is None

    async def test_update_active_commits_and_returns(self):
        session = _mock_session()
        feed = _make_feed(active=True)
        repo = FeedRepository(session)

        result = await repo.update_active(feed, False)

        assert feed.active is False
        session.commit.assert_called_once()
        session.refresh.assert_called_once_with(feed)


# --- DigestRepository ---

class TestDigestRepository:
    async def test_create_commits_and_returns(self):
        session = _mock_session()
        digest = _make_digest()
        repo = DigestRepository(session)

        result = await repo.create(digest)

        session.add.assert_called_once_with(digest)
        session.commit.assert_called_once()

    async def test_get_by_date_found(self):
        session = _mock_session()
        digest = _make_digest()
        session.execute.return_value = _scalar_result(digest)
        repo = DigestRepository(session)

        result = await repo.get_by_date(date(2026, 6, 24))

        assert result == digest

    async def test_get_by_date_not_found(self):
        session = _mock_session()
        session.execute.return_value = _scalar_result(None)
        repo = DigestRepository(session)

        result = await repo.get_by_date(date(2026, 6, 24))

        assert result is None

    async def test_get_by_id_found(self):
        session = _mock_session()
        digest = _make_digest()
        session.execute.return_value = _scalar_result(digest)
        repo = DigestRepository(session)

        result = await repo.get_by_id(digest.id)

        assert result == digest

    async def test_get_by_id_not_found(self):
        session = _mock_session()
        session.execute.return_value = _scalar_result(None)
        repo = DigestRepository(session)

        result = await repo.get_by_id(uuid.uuid4())

        assert result is None

    async def test_get_recent_returns_list(self):
        session = _mock_session()
        digests = [_make_digest(), _make_digest(run_date=date(2026, 6, 23))]
        session.execute.return_value = _scalars_result(digests)
        repo = DigestRepository(session)

        result = await repo.get_recent(limit=10)

        assert result == digests

    async def test_save_commits_and_refreshes(self):
        session = _mock_session()
        digest = _make_digest()
        repo = DigestRepository(session)

        result = await repo.save(digest)

        session.commit.assert_called_once()
        session.refresh.assert_called_once_with(digest)


# --- ArticleRepository ---

class TestArticleRepository:
    async def test_create_bulk_adds_all_and_commits(self):
        session = _mock_session()
        articles = [_make_article(), _make_article()]
        repo = ArticleRepository(session)

        await repo.create_bulk(articles)

        session.add_all.assert_called_once_with(articles)
        session.commit.assert_called_once()

    async def test_get_by_content_hashes_returns_set(self):
        session = _mock_session()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = ["abc123", "def456"]
        session.execute.return_value = result_mock
        repo = ArticleRepository(session)

        result = await repo.get_by_content_hashes({"abc123", "def456", "ghi789"})

        assert result == {"abc123", "def456"}

    async def test_get_by_date_no_filters(self):
        session = _mock_session()
        articles = [_make_article()]
        session.execute.return_value = _scalars_result(articles)
        repo = ArticleRepository(session)

        result = await repo.get_by_date(date(2026, 6, 24))

        assert result == articles

    async def test_get_by_date_relevant_only(self):
        session = _mock_session()
        session.execute.return_value = _scalars_result([])
        repo = ArticleRepository(session)

        await repo.get_by_date(date(2026, 6, 24), relevant_only=True)

        session.execute.assert_called_once()

    async def test_get_by_date_with_feed_id(self):
        session = _mock_session()
        feed_id = uuid.uuid4()
        session.execute.return_value = _scalars_result([])
        repo = ArticleRepository(session)

        await repo.get_by_date(date(2026, 6, 24), feed_id=feed_id)

        session.execute.assert_called_once()

    async def test_get_relevant_by_date_returns_ordered(self):
        session = _mock_session()
        articles = [_make_article()]
        session.execute.return_value = _scalars_result(articles)
        repo = ArticleRepository(session)

        result = await repo.get_relevant_by_date(date(2026, 6, 24), limit=5)

        assert result == articles
