import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.models import Article, Feed


@pytest.fixture
def sample_feed() -> Feed:
    feed = Feed(
        name="Test Feed",
        url="https://example.com/feed.xml",
        category="backend",
        active=True,
    )
    feed.id = uuid.uuid4()
    return feed


@pytest.fixture
def sample_article(sample_feed: Feed) -> Article:
    article = Article(
        feed_id=sample_feed.id,
        title="How Shopify scaled Kafka to 1M events/sec",
        url="https://example.com/article-1",
        content_hash="abc123",
        published_at=datetime(2026, 6, 24, 10, 0, 0),
    )
    article.id = uuid.uuid4()
    return article


@pytest.fixture
def mock_anthropic_client():
    with patch("app.services.ai_service.anthropic.AsyncAnthropic") as mock_cls:
        client = AsyncMock()
        mock_cls.return_value = client
        yield client


def make_claude_response(text: str, input_tokens: int = 100, output_tokens: int = 50):
    response = MagicMock()
    response.content = [MagicMock(text=text)]
    response.usage.input_tokens = input_tokens
    response.usage.output_tokens = output_tokens
    return response
