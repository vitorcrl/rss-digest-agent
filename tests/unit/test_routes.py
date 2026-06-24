"""
Unit tests for API routes using FastAPI TestClient with mocked dependencies.
"""
import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.domain.enums import DigestStatus
from app.domain.models import Article, DigestRun, Feed
from app.main import app


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


def _make_article(feed_id: uuid.UUID, **kwargs) -> Article:
    article = Article(
        feed_id=feed_id,
        title=kwargs.get("title", "Article Title"),
        url=kwargs.get("url", "https://example.com/article-1"),
        content_hash="abc123",
        published_at=datetime(2026, 6, 24, 10, 0, 0),
        relevance_score=8,
        summary_pt="Resumo do artigo.",
        is_relevant=True,
    )
    article.id = uuid.uuid4()
    article.created_at = datetime(2026, 6, 24, 10, 0, 0)
    article.processed_at = datetime(2026, 6, 24, 10, 5, 0)
    return article


def _make_digest(**kwargs) -> DigestRun:
    digest = DigestRun(
        run_date=kwargs.get("run_date", date(2026, 6, 24)),
        status=kwargs.get("status", DigestStatus.delivered),
        articles_processed=kwargs.get("articles_processed", 10),
        articles_selected=kwargs.get("articles_selected", 3),
        tokens_used=kwargs.get("tokens_used", 5000),
        delivered_at=datetime(2026, 6, 24, 7, 5, 0),
        error_message=None,
    )
    digest.id = uuid.uuid4()
    digest.created_at = datetime(2026, 6, 24, 7, 0, 0)
    return digest


# --- Feeds ---

class TestFeedsRoutes:
    def test_create_feed_returns_201(self):
        feed = _make_feed()
        mock_session = AsyncMock()

        with (
            patch("app.api.v1.routes.FeedRepository") as mock_repo_cls,
            patch("app.core.database.AsyncSessionFactory") as _,
        ):
            repo = AsyncMock()
            mock_repo_cls.return_value = repo
            repo.get_by_url.return_value = None
            repo.create.return_value = feed

            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/feeds",
                    json={"url": "https://example.com/feed.xml", "name": "Test Feed", "category": "backend"},
                )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Feed"
        assert data["category"] == "backend"

    def test_create_feed_duplicate_returns_409(self):
        existing = _make_feed()

        with patch("app.api.v1.routes.FeedRepository") as mock_repo_cls:
            repo = AsyncMock()
            mock_repo_cls.return_value = repo
            repo.get_by_url.return_value = existing

            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/feeds",
                    json={"url": "https://example.com/feed.xml", "name": "Test Feed", "category": "backend"},
                )

        assert response.status_code == 409
        assert response.json()["detail"] == "Feed already exists"

    def test_list_feeds_returns_200(self):
        feeds = [_make_feed(), _make_feed(name="Feed 2", url="https://other.com/feed.xml")]

        with patch("app.api.v1.routes.FeedRepository") as mock_repo_cls:
            repo = AsyncMock()
            mock_repo_cls.return_value = repo
            repo.get_all.return_value = feeds

            with TestClient(app) as client:
                response = client.get("/api/v1/feeds")

        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_update_feed_active_status(self):
        feed = _make_feed(active=False)

        with patch("app.api.v1.routes.FeedRepository") as mock_repo_cls:
            repo = AsyncMock()
            mock_repo_cls.return_value = repo
            repo.get_by_id.return_value = feed
            repo.update_active.return_value = feed

            with TestClient(app) as client:
                response = client.patch(
                    f"/api/v1/feeds/{feed.id}",
                    json={"active": False},
                )

        assert response.status_code == 200

    def test_update_feed_not_found_returns_404(self):
        with patch("app.api.v1.routes.FeedRepository") as mock_repo_cls:
            repo = AsyncMock()
            mock_repo_cls.return_value = repo
            repo.get_by_id.return_value = None

            with TestClient(app) as client:
                response = client.patch(
                    f"/api/v1/feeds/{uuid.uuid4()}",
                    json={"active": False},
                )

        assert response.status_code == 404


# --- Digest ---

class TestDigestRoutes:
    def test_trigger_digest_returns_202(self):
        digest = _make_digest()

        with patch("app.api.v1.routes.DigestService") as mock_svc_cls:
            svc = AsyncMock()
            mock_svc_cls.return_value = svc
            svc.run.return_value = digest

            with TestClient(app) as client:
                response = client.post("/api/v1/digest/run")

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "delivered"
        assert "digest_run_id" in data

    def test_list_digest_runs_returns_200(self):
        digests = [_make_digest(), _make_digest(run_date=date(2026, 6, 23))]

        with patch("app.api.v1.routes.DigestRepository") as mock_repo_cls:
            repo = AsyncMock()
            mock_repo_cls.return_value = repo
            repo.get_recent.return_value = digests

            with TestClient(app) as client:
                response = client.get("/api/v1/digest/runs")

        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_list_digest_runs_respects_limit(self):
        with patch("app.api.v1.routes.DigestRepository") as mock_repo_cls:
            repo = AsyncMock()
            mock_repo_cls.return_value = repo
            repo.get_recent.return_value = []

            with TestClient(app) as client:
                response = client.get("/api/v1/digest/runs?limit=5")

        assert response.status_code == 200
        repo.get_recent.assert_called_once_with(limit=5)

    def test_get_digest_run_by_id(self):
        digest = _make_digest()
        feed_id = uuid.uuid4()
        articles = [_make_article(feed_id)]

        with (
            patch("app.api.v1.routes.DigestRepository") as mock_digest_cls,
            patch("app.api.v1.routes.ArticleRepository") as mock_article_cls,
        ):
            digest_repo = AsyncMock()
            mock_digest_cls.return_value = digest_repo
            digest_repo.get_by_id.return_value = digest

            article_repo = AsyncMock()
            mock_article_cls.return_value = article_repo
            article_repo.get_by_date.return_value = articles

            with TestClient(app) as client:
                response = client.get(f"/api/v1/digest/runs/{digest.id}")

        assert response.status_code == 200
        data = response.json()
        assert len(data["articles"]) == 1

    def test_get_digest_run_not_found_returns_404(self):
        with patch("app.api.v1.routes.DigestRepository") as mock_repo_cls:
            repo = AsyncMock()
            mock_repo_cls.return_value = repo
            repo.get_by_id.return_value = None

            with TestClient(app) as client:
                response = client.get(f"/api/v1/digest/runs/{uuid.uuid4()}")

        assert response.status_code == 404


# --- Articles ---

class TestArticlesRoutes:
    def test_list_articles_default(self):
        feed_id = uuid.uuid4()
        articles = [_make_article(feed_id), _make_article(feed_id, url="https://example.com/article-2")]

        with patch("app.api.v1.routes.ArticleRepository") as mock_repo_cls:
            repo = AsyncMock()
            mock_repo_cls.return_value = repo
            repo.get_by_date.return_value = articles

            with TestClient(app) as client:
                response = client.get("/api/v1/articles")

        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_list_articles_with_filters(self):
        feed_id = uuid.uuid4()

        with patch("app.api.v1.routes.ArticleRepository") as mock_repo_cls:
            repo = AsyncMock()
            mock_repo_cls.return_value = repo
            repo.get_by_date.return_value = []

            with TestClient(app) as client:
                response = client.get(
                    f"/api/v1/articles?run_date=2026-06-24&relevant_only=true&feed_id={feed_id}"
                )

        assert response.status_code == 200
        repo.get_by_date.assert_called_once_with(
            date(2026, 6, 24), relevant_only=True, feed_id=feed_id
        )

    def test_list_articles_relevant_only(self):
        feed_id = uuid.uuid4()
        articles = [_make_article(feed_id)]

        with patch("app.api.v1.routes.ArticleRepository") as mock_repo_cls:
            repo = AsyncMock()
            mock_repo_cls.return_value = repo
            repo.get_by_date.return_value = articles

            with TestClient(app) as client:
                response = client.get("/api/v1/articles?relevant_only=true")

        assert response.status_code == 200
        _, kwargs = repo.get_by_date.call_args
        assert kwargs["relevant_only"] is True
