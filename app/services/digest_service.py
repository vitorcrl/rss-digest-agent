import logging
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.domain.enums import DigestStatus
from app.domain.models import Article, DigestRun
from app.repositories.article_repository import ArticleRepository
from app.repositories.digest_repository import DigestRepository
from app.repositories.feed_repository import FeedRepository
from app.services.ai_service import AIService
from app.services.delivery_service import DeliveryError, DeliveryService
from app.services.rss_service import FeedFetchError, RSSService

logger = logging.getLogger(__name__)


class DigestService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._feed_repo = FeedRepository(session)
        self._article_repo = ArticleRepository(session)
        self._digest_repo = DigestRepository(session)
        self._rss = RSSService()
        self._ai = AIService()
        self._delivery = DeliveryService()

    async def run(self, run_date: date | None = None) -> DigestRun:
        today = run_date or date.today()

        existing = await self._digest_repo.get_by_date(today)
        if existing and existing.status == DigestStatus.delivered:
            logger.info("Digest for %s already delivered, skipping", today)
            return existing

        digest = existing or await self._digest_repo.create(DigestRun(run_date=today))
        digest.status = DigestStatus.processing
        await self._digest_repo.save(digest)

        try:
            # 1. FETCH — pull articles from all active feeds
            feeds = await self._feed_repo.get_active()
            fetched: list[Article] = []
            for feed in feeds:
                try:
                    articles = await self._rss.fetch_articles(feed)
                    fetched.extend(articles)
                except FeedFetchError as exc:
                    logger.warning("Feed %s failed: %s", feed.url, exc)

            # 2. DEDUP — drop articles already in the database
            incoming_hashes = {a.content_hash for a in fetched}
            existing_hashes = await self._article_repo.get_by_content_hashes(incoming_hashes)
            new_articles = [a for a in fetched if a.content_hash not in existing_hashes]

            digest.articles_processed = len(new_articles)
            total_tokens = 0

            if not new_articles:
                logger.info("No new articles for %s", today)
                digest.status = DigestStatus.delivered
                digest.articles_processed = 0
                digest.articles_selected = 0
                digest.tokens_used = 0
                return await self._digest_repo.save(digest)

            # 3. FILTER — batch relevance scoring via Claude Haiku
            titles = [a.title for a in new_articles]
            scores, tokens = await self._ai.evaluate_relevance(titles)
            total_tokens += tokens

            for article, score in zip(new_articles, scores):
                article.relevance_score = score
                article.is_relevant = score >= settings.AI_MIN_RELEVANCE_SCORE

            # 4. SUMMARIZE — individual summaries for relevant articles
            relevant = [a for a in new_articles if a.is_relevant]
            for article in relevant:
                summary, tokens = await self._ai.summarize(article)
                article.summary_pt = summary
                article.processed_at = datetime.utcnow()
                total_tokens += tokens

            # 5. PERSIST — save all articles to the database
            await self._article_repo.create_bulk(new_articles)

            # 6. COMPILE — pick top N by relevance score
            top_articles = await self._article_repo.get_relevant_by_date(
                today, limit=settings.AI_MAX_ARTICLES_PER_DIGEST
            )

            digest.articles_selected = len(top_articles)
            digest.tokens_used = total_tokens

            # 7. DELIVER — send webhook
            await self._delivery.send(
                run_date=today,
                articles=top_articles,
                total_read=len(new_articles),
                tokens_used=total_tokens,
            )

            # 8. LOG — mark as delivered
            digest.status = DigestStatus.delivered
            digest.delivered_at = datetime.utcnow()

        except DeliveryError as exc:
            logger.error("Delivery failed: %s", exc)
            digest.status = DigestStatus.failed
            digest.error_message = str(exc)

        except Exception as exc:
            logger.exception("Pipeline failed: %s", exc)
            digest.status = DigestStatus.failed
            digest.error_message = str(exc)

        return await self._digest_repo.save(digest)
