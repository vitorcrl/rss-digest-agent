import hashlib
from datetime import datetime

import feedparser

from app.domain.models import Article, Feed


class FeedFetchError(Exception):
    pass


class RSSService:
    async def fetch_articles(self, feed: Feed) -> list[Article]:
        parsed = feedparser.parse(feed.url)

        status = parsed.get("status", 200)
        if status >= 400 or not parsed.entries:
            raise FeedFetchError(f"Failed to fetch feed {feed.url} (status {status})")

        articles = []
        for entry in parsed.entries:
            title = entry.get("title", "").strip()
            url = entry.get("link", "").strip()

            if not title or not url:
                continue

            content_hash = hashlib.sha256(f"{title}{url}".encode()).hexdigest()
            published_at = self._parse_date(entry)

            articles.append(
                Article(
                    feed_id=feed.id,
                    title=title,
                    url=url,
                    content_hash=content_hash,
                    published_at=published_at,
                )
            )

        return articles

    def _parse_date(self, entry: dict) -> datetime:
        if "published_parsed" in entry and entry.published_parsed:
            return datetime(*entry.published_parsed[:6])
        if "updated_parsed" in entry and entry.updated_parsed:
            return datetime(*entry.updated_parsed[:6])
        return datetime.utcnow()
