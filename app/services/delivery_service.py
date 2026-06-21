import asyncio
import logging
from datetime import date

import httpx

from app.core.config import settings
from app.domain.models import Article

logger = logging.getLogger(__name__)


class DeliveryError(Exception):
    pass


class DeliveryService:
    async def send(
        self,
        run_date: date,
        articles: list[Article],
        total_read: int,
        tokens_used: int,
    ) -> None:
        payload = {
            "date": run_date.isoformat(),
            "total_articles_read": total_read,
            "total_selected": len(articles),
            "tokens_used": tokens_used,
            "articles": [
                {
                    "title": a.title,
                    "url": a.url,
                    "relevance_score": a.relevance_score,
                    "summary_pt": a.summary_pt,
                    "published_at": a.published_at.isoformat() if a.published_at else None,
                }
                for a in articles
            ],
        }

        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=10.0) as client:
            for attempt in range(settings.DELIVERY_RETRY_ATTEMPTS):
                try:
                    response = await client.post(settings.DELIVERY_WEBHOOK_URL, json=payload)
                    response.raise_for_status()
                    return
                except httpx.HTTPError as exc:
                    last_error = exc
                    wait = 2 ** attempt  # 1s, 2s, 4s
                    logger.warning("Delivery attempt %d failed: %s — retrying in %ds", attempt + 1, exc, wait)
                    if attempt < settings.DELIVERY_RETRY_ATTEMPTS - 1:
                        await asyncio.sleep(wait)

        raise DeliveryError(f"All {settings.DELIVERY_RETRY_ATTEMPTS} delivery attempts failed") from last_error
