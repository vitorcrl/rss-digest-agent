import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.enums import DigestStatus
from app.domain.models import Article, DigestRun, Feed
from app.services.delivery_service import DeliveryError
from app.services.digest_service import DigestService


def make_feed(url="https://feed.example.com/rss") -> Feed:
    feed = Feed(name="Test", url=url, category="backend", active=True)
    feed.id = uuid.uuid4()
    return feed


def make_article(title="Article", url="https://example.com/a", hash="hash1") -> Article:
    article = Article(
        feed_id=uuid.uuid4(),
        title=title,
        url=url,
        content_hash=hash,
        published_at=datetime(2026, 6, 24),
    )
    article.id = uuid.uuid4()
    return article


def make_digest(run_date=date(2026, 6, 24), status=DigestStatus.pending) -> DigestRun:
    digest = DigestRun(run_date=run_date, status=status)
    digest.id = uuid.uuid4()
    return digest


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def mock_repos():
    with (
        patch("app.services.digest_service.FeedRepository") as feed_repo_cls,
        patch("app.services.digest_service.ArticleRepository") as article_repo_cls,
        patch("app.services.digest_service.DigestRepository") as digest_repo_cls,
        patch("app.services.digest_service.RSSService") as rss_cls,
        patch("app.services.digest_service.AIService") as ai_cls,
        patch("app.services.digest_service.DeliveryService") as delivery_cls,
    ):
        feed_repo = AsyncMock()
        article_repo = AsyncMock()
        digest_repo = AsyncMock()
        rss = AsyncMock()
        ai = AsyncMock()
        delivery = AsyncMock()

        feed_repo_cls.return_value = feed_repo
        article_repo_cls.return_value = article_repo
        digest_repo_cls.return_value = digest_repo
        rss_cls.return_value = rss
        ai_cls.return_value = ai
        delivery_cls.return_value = delivery

        yield {
            "feed_repo": feed_repo,
            "article_repo": article_repo,
            "digest_repo": digest_repo,
            "rss": rss,
            "ai": ai,
            "delivery": delivery,
        }


class TestDigestServiceRun:
    async def test_skips_if_already_delivered(self, mock_session, mock_repos):
        existing = make_digest(status=DigestStatus.delivered)
        mock_repos["digest_repo"].get_by_date.return_value = existing

        service = DigestService(mock_session)
        result = await service.run(date(2026, 6, 24))

        assert result.status == DigestStatus.delivered
        mock_repos["feed_repo"].get_active.assert_not_called()

    async def test_full_pipeline_marks_as_delivered(self, mock_session, mock_repos):
        digest = make_digest()
        article = make_article()

        mock_repos["digest_repo"].get_by_date.return_value = None
        mock_repos["digest_repo"].create.return_value = digest
        mock_repos["digest_repo"].save.return_value = digest
        mock_repos["feed_repo"].get_active.return_value = [make_feed()]
        mock_repos["rss"].fetch_articles.return_value = [article]
        mock_repos["article_repo"].get_by_content_hashes.return_value = set()
        mock_repos["ai"].evaluate_relevance.return_value = ([8], 100)
        mock_repos["ai"].summarize.return_value = ("Resumo.", 80)
        mock_repos["article_repo"].get_relevant_by_date.return_value = [article]
        mock_repos["delivery"].send.return_value = None

        service = DigestService(mock_session)
        await service.run(date(2026, 6, 24))

        assert digest.status == DigestStatus.delivered
        assert digest.tokens_used == 180

    async def test_dedup_filters_existing_articles(self, mock_session, mock_repos):
        digest = make_digest()
        existing_article = make_article(hash="existing_hash")
        new_article = make_article(hash="new_hash", url="https://example.com/new")

        mock_repos["digest_repo"].get_by_date.return_value = None
        mock_repos["digest_repo"].create.return_value = digest
        mock_repos["digest_repo"].save.return_value = digest
        mock_repos["feed_repo"].get_active.return_value = [make_feed()]
        mock_repos["rss"].fetch_articles.return_value = [existing_article, new_article]
        mock_repos["article_repo"].get_by_content_hashes.return_value = {"existing_hash"}
        mock_repos["ai"].evaluate_relevance.return_value = ([5], 50)
        mock_repos["ai"].summarize.return_value = ("Resumo.", 50)
        mock_repos["article_repo"].get_relevant_by_date.return_value = []
        mock_repos["delivery"].send.return_value = None

        service = DigestService(mock_session)
        await service.run(date(2026, 6, 24))

        titles_sent = mock_repos["ai"].evaluate_relevance.call_args.args[0]
        assert len(titles_sent) == 1
        assert new_article.title in titles_sent

    async def test_delivery_failure_marks_as_failed(self, mock_session, mock_repos):
        digest = make_digest()
        article = make_article()

        mock_repos["digest_repo"].get_by_date.return_value = None
        mock_repos["digest_repo"].create.return_value = digest
        mock_repos["digest_repo"].save.return_value = digest
        mock_repos["feed_repo"].get_active.return_value = [make_feed()]
        mock_repos["rss"].fetch_articles.return_value = [article]
        mock_repos["article_repo"].get_by_content_hashes.return_value = set()
        mock_repos["ai"].evaluate_relevance.return_value = ([8], 100)
        mock_repos["ai"].summarize.return_value = ("Resumo.", 50)
        mock_repos["article_repo"].get_relevant_by_date.return_value = [article]
        mock_repos["delivery"].send.side_effect = DeliveryError("webhook timeout")

        service = DigestService(mock_session)
        await service.run(date(2026, 6, 24))

        assert digest.status == DigestStatus.failed
        assert "webhook timeout" in digest.error_message

    async def test_feed_failure_does_not_stop_pipeline(self, mock_session, mock_repos):
        from app.services.rss_service import FeedFetchError

        digest = make_digest()
        good_article = make_article()

        mock_repos["digest_repo"].get_by_date.return_value = None
        mock_repos["digest_repo"].create.return_value = digest
        mock_repos["digest_repo"].save.return_value = digest
        mock_repos["feed_repo"].get_active.return_value = [make_feed("bad"), make_feed("good")]
        mock_repos["rss"].fetch_articles.side_effect = [
            FeedFetchError("timeout"),
            [good_article],
        ]
        mock_repos["article_repo"].get_by_content_hashes.return_value = set()
        mock_repos["ai"].evaluate_relevance.return_value = ([7], 80)
        mock_repos["ai"].summarize.return_value = ("Resumo.", 60)
        mock_repos["article_repo"].get_relevant_by_date.return_value = [good_article]
        mock_repos["delivery"].send.return_value = None

        service = DigestService(mock_session)
        await service.run(date(2026, 6, 24))

        assert digest.status == DigestStatus.delivered
        assert digest.articles_processed == 1

    async def test_no_new_articles_marks_as_delivered(self, mock_session, mock_repos):
        digest = make_digest()

        mock_repos["digest_repo"].get_by_date.return_value = None
        mock_repos["digest_repo"].create.return_value = digest
        mock_repos["digest_repo"].save.return_value = digest
        mock_repos["feed_repo"].get_active.return_value = [make_feed()]
        mock_repos["rss"].fetch_articles.return_value = [make_article()]
        mock_repos["article_repo"].get_by_content_hashes.return_value = {"hash1"}

        service = DigestService(mock_session)
        await service.run(date(2026, 6, 24))

        assert digest.status == DigestStatus.delivered
        mock_repos["ai"].evaluate_relevance.assert_not_called()
        mock_repos["delivery"].send.assert_not_called()

    async def test_unexpected_exception_marks_as_failed(self, mock_session, mock_repos):
        digest = make_digest()
        mock_repos["digest_repo"].get_by_date.return_value = None
        mock_repos["digest_repo"].create.return_value = digest
        mock_repos["digest_repo"].save.return_value = digest
        mock_repos["feed_repo"].get_active.side_effect = RuntimeError("db connection lost")

        service = DigestService(mock_session)
        await service.run(date(2026, 6, 24))

        assert digest.status == DigestStatus.failed
        assert digest.error_message is not None

    async def test_summarize_only_called_for_relevant_articles(self, mock_session, mock_repos):
        digest = make_digest()
        low = make_article(title="Low", url="https://example.com/low", hash="low")
        high = make_article(title="High", url="https://example.com/high", hash="high")

        mock_repos["digest_repo"].get_by_date.return_value = None
        mock_repos["digest_repo"].create.return_value = digest
        mock_repos["digest_repo"].save.return_value = digest
        mock_repos["feed_repo"].get_active.return_value = [make_feed()]
        mock_repos["rss"].fetch_articles.return_value = [low, high]
        mock_repos["article_repo"].get_by_content_hashes.return_value = set()
        mock_repos["ai"].evaluate_relevance.return_value = ([3, 9], 100)
        mock_repos["ai"].summarize.return_value = ("Resumo.", 50)
        mock_repos["article_repo"].get_relevant_by_date.return_value = [high]
        mock_repos["delivery"].send.return_value = None

        service = DigestService(mock_session)
        await service.run(date(2026, 6, 24))

        assert mock_repos["ai"].summarize.call_count == 1
        summarized_article = mock_repos["ai"].summarize.call_args.args[0]
        assert summarized_article.title == "High"
