"""Repository for news article persistence."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.datasources.models import News


class NewsRepository:
    """Repository for CRUD operations on news articles."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, article: dict) -> News | None:
        """Insert or skip if URL already exists (no update on conflict).

        Returns the News object if inserted, None if skipped.
        """
        stmt = (
            pg_insert(News)
            .values(
                source=article.get("source", "rss"),
                title=article["title"],
                url=article["url"],
                summary=article.get("summary"),
                published_at=article.get("published_dt"),
                feed_name=article.get("feed"),
                feed_category=article.get("feed_category"),
                domain=article.get("domain"),
                language=article.get("language", "fr"),
                author=article.get("author"),
                tags=article.get("tags"),
                regions=[article["_region"]] if article.get("_region") else None,
            )
            .on_conflict_do_nothing(index_elements=["url"])
            .returning(News.id)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is not None:
            return await self._session.get(News, row)
        return None

    async def upsert_batch(self, articles: list[dict]) -> int:
        """Bulk upsert articles. Returns count of newly inserted."""
        if not articles:
            return 0

        values = [
            {
                "source": a.get("source", "rss"),
                "title": a["title"],
                "url": a["url"],
                "summary": a.get("summary"),
                "published_at": a.get("published_dt"),
                "feed_name": a.get("feed"),
                "feed_category": a.get("feed_category"),
                "domain": a.get("domain"),
                "language": a.get("language", "fr"),
                "author": a.get("author"),
                "tags": a.get("tags"),
                "regions": [a["_region"]] if a.get("_region") else None,
            }
            for a in articles
            if a.get("url") and a.get("title")
        ]

        if not values:
            return 0

        stmt = pg_insert(News).values(values).on_conflict_do_nothing(index_elements=["url"])
        result = await self._session.execute(stmt)
        return result.rowcount

    async def get_latest(
        self,
        limit: int = 50,
        feed_category: str | None = None,
        source: str | None = None,
        since: datetime | None = None,
    ) -> list[News]:
        """Get latest news articles with optional filters."""
        query = select(News).order_by(News.published_at.desc().nullslast(), News.created_at.desc())

        if feed_category:
            query = query.where(News.feed_category == feed_category)
        if source:
            query = query.where(News.source == source)
        if since:
            query = query.where(News.published_at >= since)

        query = query.limit(limit)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def search(self, keywords: str, limit: int = 30) -> list[News]:
        """Search news by keywords in title."""
        query = (
            select(News)
            .where(News.title.ilike(f"%{keywords}%"))
            .order_by(News.published_at.desc().nullslast())
            .limit(limit)
        )
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_by_url(self, url: str) -> News | None:
        """Get a news article by URL."""
        query = select(News).where(News.url == url)
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def count(self, since: datetime | None = None) -> int:
        """Count news articles."""
        query = select(func.count(News.id))
        if since:
            query = query.where(News.created_at >= since)
        result = await self._session.execute(query)
        return result.scalar_one()

    async def count_by_category(self) -> dict[str, int]:
        """Count articles per feed category."""
        query = (
            select(News.feed_category, func.count(News.id))
            .group_by(News.feed_category)
            .order_by(func.count(News.id).desc())
        )
        result = await self._session.execute(query)
        return {row[0] or "unknown": row[1] for row in result.all()}

    async def count_by_hour(self, hours: int = 24) -> list[dict]:
        """Count articles per hour for the last N hours (for spike detection)."""
        since = datetime.utcnow() - __import__("datetime").timedelta(hours=hours)
        query = (
            select(
                func.date_trunc("hour", News.published_at).label("hour"),
                func.count(News.id).label("count"),
            )
            .where(News.published_at >= since)
            .group_by("hour")
            .order_by("hour")
        )
        result = await self._session.execute(query)
        return [{"hour": row.hour.isoformat(), "count": row.count} for row in result.all()]
