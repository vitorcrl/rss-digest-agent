import hashlib
from unittest.mock import MagicMock, patch

import pytest

from app.domain.models import Feed
from app.services.rss_service import FeedFetchError, RSSService


def make_parsed(status=200, entries=None):
    """Build a feedparser-like result object (uses attribute access, not dict)."""
    mock = MagicMock()
    mock.get.side_effect = lambda key, default=None: {"status": status}.get(key, default)
    mock.entries = entries or []
    return mock


def make_entry(title="Article", link="https://example.com/a", published_parsed=None, updated_parsed=None):
    entry = MagicMock()
    entry.get.side_effect = lambda key, default="": {"title": title, "link": link}.get(key, default)
    entry.published_parsed = published_parsed
    entry.updated_parsed = updated_parsed
    # control `"published_parsed" in entry` and `"updated_parsed" in entry`
    entry.__contains__ = lambda self, key: (
        (key == "published_parsed" and published_parsed is not None)
        or (key == "updated_parsed" and updated_parsed is not None)
    )
    return entry


@pytest.fixture
def service() -> RSSService:
    return RSSService()


@pytest.fixture
def feed(sample_feed: Feed) -> Feed:
    return sample_feed


class TestFetchArticles:
    async def test_returns_articles_with_correct_fields(self, service, feed):
        entry = make_entry(
            title="How Shopify scaled Kafka",
            link="https://example.com/kafka",
            published_parsed=(2026, 6, 24, 10, 0, 0, 0, 0, 0),
        )
        parsed = make_parsed(status=200, entries=[entry])
        with patch("app.services.rss_service.feedparser.parse", return_value=parsed):
            articles = await service.fetch_articles(feed)

        assert len(articles) == 1
        assert articles[0].title == "How Shopify scaled Kafka"
        assert articles[0].url == "https://example.com/kafka"
        assert articles[0].feed_id == feed.id

    async def test_content_hash_is_sha256_of_title_and_url(self, service, feed):
        title = "My Article"
        url = "https://example.com/my-article"
        expected_hash = hashlib.sha256(f"{title}{url}".encode()).hexdigest()

        parsed = make_parsed(entries=[make_entry(title=title, link=url)])
        with patch("app.services.rss_service.feedparser.parse", return_value=parsed):
            articles = await service.fetch_articles(feed)

        assert articles[0].content_hash == expected_hash

    async def test_raises_on_http_error_status(self, service, feed):
        parsed = make_parsed(status=404, entries=[])
        with patch("app.services.rss_service.feedparser.parse", return_value=parsed):
            with pytest.raises(FeedFetchError, match="404"):
                await service.fetch_articles(feed)

    async def test_raises_when_no_entries(self, service, feed):
        parsed = make_parsed(status=200, entries=[])
        with patch("app.services.rss_service.feedparser.parse", return_value=parsed):
            with pytest.raises(FeedFetchError):
                await service.fetch_articles(feed)

    async def test_raises_on_connection_failure(self, service, feed):
        parsed = make_parsed(status=None, entries=[])
        with patch("app.services.rss_service.feedparser.parse", return_value=parsed):
            with pytest.raises(FeedFetchError):
                await service.fetch_articles(feed)

    async def test_skips_entries_without_title_or_url(self, service, feed):
        entries = [
            make_entry(title="Valid Article", link="https://example.com/valid"),
            make_entry(title="", link="https://example.com/no-title"),
            make_entry(title="No URL", link=""),
        ]
        parsed = make_parsed(entries=entries)
        with patch("app.services.rss_service.feedparser.parse", return_value=parsed):
            articles = await service.fetch_articles(feed)

        assert len(articles) == 1
        assert articles[0].title == "Valid Article"

    async def test_falls_back_to_updated_parsed_when_no_published(self, service, feed):
        entry = make_entry(
            title="Article",
            link="https://example.com/article",
            updated_parsed=(2026, 6, 20, 8, 0, 0, 0, 0, 0),
        )
        parsed = make_parsed(entries=[entry])
        with patch("app.services.rss_service.feedparser.parse", return_value=parsed):
            articles = await service.fetch_articles(feed)

        assert articles[0].published_at.year == 2026
        assert articles[0].published_at.month == 6
        assert articles[0].published_at.day == 20

    async def test_falls_back_to_utcnow_when_no_date(self, service, feed):
        entry = make_entry(title="Article", link="https://example.com/article")
        parsed = make_parsed(entries=[entry])
        with patch("app.services.rss_service.feedparser.parse", return_value=parsed):
            articles = await service.fetch_articles(feed)

        assert articles[0].published_at is not None
