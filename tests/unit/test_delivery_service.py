"""
Unit tests for DeliveryService — webhook sending with retry logic.
"""
import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.domain.models import Article
from app.services.delivery_service import DeliveryError, DeliveryService


def _make_article(**kwargs) -> Article:
    article = Article(
        feed_id=uuid.uuid4(),
        title=kwargs.get("title", "Article Title"),
        url=kwargs.get("url", "https://example.com/article"),
        content_hash="abc123",
        published_at=datetime(2026, 6, 24, 10, 0, 0),
        relevance_score=8,
        summary_pt="Resumo.",
        is_relevant=True,
    )
    article.id = uuid.uuid4()
    return article


def _mock_http_client(raise_exc=None):
    http_client = AsyncMock()
    if raise_exc:
        http_client.post.side_effect = raise_exc
    else:
        http_client.post.return_value = AsyncMock(raise_for_status=lambda: None)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=http_client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx, http_client


class TestDeliveryService:
    async def test_send_success_on_first_attempt(self):
        ctx, http_client = _mock_http_client()

        with patch("app.services.delivery_service.httpx.AsyncClient", return_value=ctx):
            await DeliveryService().send(
                run_date=date(2026, 6, 24),
                articles=[_make_article()],
                total_read=5,
                tokens_used=1000,
            )

        http_client.post.assert_called_once()
        call_kwargs = http_client.post.call_args
        payload = call_kwargs[1]["json"]
        assert payload["date"] == "2026-06-24"
        assert payload["total_articles_read"] == 5
        assert payload["tokens_used"] == 1000
        assert len(payload["articles"]) == 1

    async def test_send_payload_structure(self):
        article = _make_article(title="Kafka Scaling", url="https://example.com/kafka")
        article.summary_pt = "Resumo Kafka."
        article.relevance_score = 9

        ctx, http_client = _mock_http_client()

        with patch("app.services.delivery_service.httpx.AsyncClient", return_value=ctx):
            await DeliveryService().send(
                run_date=date(2026, 6, 24),
                articles=[article],
                total_read=10,
                tokens_used=2000,
            )

        payload = http_client.post.call_args[1]["json"]
        art = payload["articles"][0]
        assert art["title"] == "Kafka Scaling"
        assert art["url"] == "https://example.com/kafka"
        assert art["relevance_score"] == 9
        assert art["summary_pt"] == "Resumo Kafka."
        assert art["published_at"] == "2026-06-24T10:00:00"

    async def test_send_article_with_no_published_at(self):
        article = _make_article()
        article.published_at = None

        ctx, http_client = _mock_http_client()

        with patch("app.services.delivery_service.httpx.AsyncClient", return_value=ctx):
            await DeliveryService().send(
                run_date=date(2026, 6, 24),
                articles=[article],
                total_read=1,
                tokens_used=100,
            )

        payload = http_client.post.call_args[1]["json"]
        assert payload["articles"][0]["published_at"] is None

    async def test_send_retries_on_failure_then_succeeds(self):
        http_client = AsyncMock()
        http_client.post.side_effect = [
            httpx.HTTPError("timeout"),
            AsyncMock(raise_for_status=lambda: None),
        ]
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=http_client)
        ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.services.delivery_service.httpx.AsyncClient", return_value=ctx),
            patch("app.services.delivery_service.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            await DeliveryService().send(
                run_date=date(2026, 6, 24),
                articles=[],
                total_read=0,
                tokens_used=0,
            )

        assert http_client.post.call_count == 2
        mock_sleep.assert_called_once_with(1)

    async def test_send_raises_delivery_error_after_all_attempts(self):
        ctx, http_client = _mock_http_client(raise_exc=httpx.HTTPError("connection refused"))

        with (
            patch("app.services.delivery_service.httpx.AsyncClient", return_value=ctx),
            patch("app.services.delivery_service.asyncio.sleep", new_callable=AsyncMock),
        ):
            with pytest.raises(DeliveryError, match="All 3 delivery attempts failed"):
                await DeliveryService().send(
                    run_date=date(2026, 6, 24),
                    articles=[],
                    total_read=0,
                    tokens_used=0,
                )

        assert http_client.post.call_count == 3

    async def test_send_empty_articles_list(self):
        ctx, http_client = _mock_http_client()

        with patch("app.services.delivery_service.httpx.AsyncClient", return_value=ctx):
            await DeliveryService().send(
                run_date=date(2026, 6, 24),
                articles=[],
                total_read=0,
                tokens_used=0,
            )

        payload = http_client.post.call_args[1]["json"]
        assert payload["articles"] == []
        assert payload["total_selected"] == 0

    async def test_exponential_backoff_wait_times(self):
        http_client = AsyncMock()
        http_client.post.side_effect = httpx.HTTPError("error")
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=http_client)
        ctx.__aexit__ = AsyncMock(return_value=False)

        sleep_calls = []

        async def capture_sleep(secs):
            sleep_calls.append(secs)

        with (
            patch("app.services.delivery_service.httpx.AsyncClient", return_value=ctx),
            patch("app.services.delivery_service.asyncio.sleep", side_effect=capture_sleep),
        ):
            with pytest.raises(DeliveryError):
                await DeliveryService().send(
                    run_date=date(2026, 6, 24),
                    articles=[],
                    total_read=0,
                    tokens_used=0,
                )

        # 3 attempts → sleep after attempt 0 (1s) and attempt 1 (2s), not after last
        assert sleep_calls == [1, 2]
