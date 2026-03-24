"""Service for syncing RSS feed articles to the database.

Full pipeline: Fetch → Persist → Summarize → Sentiment → Detect Spikes → Alert
"""

import asyncio
import os
from datetime import datetime, timedelta

import httpx
from loguru import logger

from src.infrastructure.datasources.adapters.rss_enhanced import RssEnhancedAdapter
from src.infrastructure.datasources.spike_detector import spike_detector
from src.infrastructure.persistence.database import get_session
from src.infrastructure.persistence.repositories.news_repository import NewsRepository

# Telegram config (optional, for spike alerts)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


class NewsSyncService:
    """Fetches news from RssEnhancedAdapter and persists to DB.

    Pipeline: fetch → deduplicate → persist → summarize → sentiment → spike detect → alert
    """

    def __init__(self, adapter: RssEnhancedAdapter | None = None):
        self._adapter = adapter or RssEnhancedAdapter()

    async def sync_all(self, limit: int = 200, auto_enrich: bool = True) -> dict:
        """Sync all enabled feeds to database.

        Args:
            limit: Max articles to fetch
            auto_enrich: If True, auto-summarize + sentiment new articles

        Returns:
            dict with sync stats
        """
        logger.info("Starting full news sync...")

        try:
            articles = await self._adapter.search(
                {
                    "limit": limit,
                    "deduplicate": True,
                }
            )
        except Exception as e:
            logger.error(f"Failed to fetch feeds: {e}")
            return {"fetched": 0, "inserted": 0, "error": str(e)}

        return await self._persist(articles, auto_enrich=auto_enrich)

    async def sync_category(self, category: str, limit: int = 50, auto_enrich: bool = True) -> dict:
        """Sync a specific feed category."""
        logger.info(f"Syncing category: {category}")

        articles = await self._adapter.search(
            {
                "categories": [category],
                "limit": limit,
                "deduplicate": True,
            }
        )

        return await self._persist(articles, auto_enrich=auto_enrich)

    async def sync_recent(self, hours: int = 6, limit: int = 100, auto_enrich: bool = True) -> dict:
        """Sync only recent articles (published in the last N hours)."""
        since = datetime.utcnow() - timedelta(hours=hours)
        logger.info(f"Syncing articles since {since.isoformat()}")

        articles = await self._adapter.search(
            {
                "since": since,
                "limit": limit,
                "deduplicate": True,
            }
        )

        return await self._persist(articles, auto_enrich=auto_enrich)

    async def _persist(self, articles: list[dict], auto_enrich: bool = True) -> dict:
        """Persist articles to database via NewsRepository."""
        if not articles:
            return {"fetched": 0, "inserted": 0, "duplicates": 0}

        async with get_session() as session:
            repo = NewsRepository(session)
            inserted = await repo.upsert_batch(articles)

        duplicates = len(articles) - inserted
        logger.info(
            f"News sync complete: {len(articles)} fetched, "
            f"{inserted} inserted, {duplicates} duplicates skipped"
        )

        # Feed spike detector with per-category counts
        spikes = self._update_spike_detector(articles, inserted)

        result = {
            "fetched": len(articles),
            "inserted": inserted,
            "duplicates": duplicates,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if spikes:
            result["spikes_detected"] = [s.to_dict() for s in spikes]
            # Send Telegram alerts for spikes
            asyncio.create_task(self._alert_spikes(spikes))

        # Auto-enrich new articles in background
        if auto_enrich and inserted > 0:
            enriched = await self._auto_enrich(min(inserted, 20))
            result["enriched"] = enriched

        return result

    async def _auto_enrich(self, limit: int = 20) -> dict:
        """Auto-summarize + sentiment analysis for recent articles without AI summary."""
        from sqlalchemy import select, update

        from src.application.services.llm_summarizer import get_summarizer
        from src.infrastructure.datasources.models import News

        summarizer = get_summarizer()
        enriched = 0
        sentiments = {"positif": 0, "negatif": 0, "neutre": 0}

        async with get_session() as session:
            # Fetch articles missing AI summary
            query = (
                select(News)
                .where(News.ai_summary.is_(None))
                .order_by(News.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(query)
            articles = list(result.scalars().all())

        if not articles:
            return {"enriched": 0}

        logger.info(f"[auto-enrich] Processing {len(articles)} articles")

        for article in articles:
            try:
                text = article.summary or article.title
                enrichment = await summarizer.summarize_with_sentiment(article.title, text)

                if enrichment.get("summary"):
                    async with get_session() as session:
                        stmt = (
                            update(News)
                            .where(News.id == article.id)
                            .values(
                                ai_summary=enrichment["summary"],
                                sentiment=enrichment.get("sentiment", "neutre"),
                            )
                        )
                        await session.execute(stmt)
                        await session.commit()
                    enriched += 1
                    sentiment = enrichment.get("sentiment", "neutre")
                    sentiments[sentiment] = sentiments.get(sentiment, 0) + 1
            except Exception as e:
                logger.warning(f"[auto-enrich] Failed for article {article.id}: {e}")

        logger.info(f"[auto-enrich] Enriched {enriched}/{len(articles)} articles")
        return {
            "enriched": enriched,
            "total_attempted": len(articles),
            "sentiments": sentiments,
        }

    def _update_spike_detector(self, articles: list[dict], inserted: int) -> list:
        """Feed Welford spike detector with sync data."""
        from collections import Counter

        # Track total volume
        spike_total = spike_detector.record("news_total", float(inserted))
        spikes = [spike_total] if spike_total else []

        # Track per-category volume
        cats = Counter(a.get("feed_category", "unknown") for a in articles)
        for cat, count in cats.items():
            spike = spike_detector.record(f"news_{cat}", float(count))
            if spike:
                spikes.append(spike)
                logger.warning(
                    f"SPIKE detected in {cat}: {count} articles "
                    f"(mean={spike.mean:.1f}, z={spike.z_score:.1f}, "
                    f"severity={spike.severity.value})"
                )

        return spikes

    async def _alert_spikes(self, spikes: list) -> None:
        """Send Telegram alert for detected spikes."""
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            return

        for spike in spikes:
            severity_emoji = {"low": "🟡", "medium": "🟠", "high": "🔴", "critical": "🚨"}.get(
                spike.severity.value, "📊"
            )

            message = (
                f"{severity_emoji} *SPIKE NEWS — {spike.stream}*\n"
                f"Volume: {spike.current_value:.0f} articles\n"
                f"Moyenne: {spike.mean:.1f} | Z-score: {spike.z_score:.1f}\n"
                f"Sévérité: {spike.severity.value.upper()}"
            )

            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    await client.post(
                        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                        json={
                            "chat_id": TELEGRAM_CHAT_ID,
                            "text": message,
                            "parse_mode": "Markdown",
                        },
                    )
                logger.info(f"[telegram] Spike alert sent: {spike.stream}")
            except Exception as e:
                logger.warning(f"[telegram] Failed to send alert: {e}")

    async def alert_focal_points(self, focal_points: list[dict], min_score: int = 50) -> int:
        """Send Telegram alerts for significant focal points."""
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            return 0

        sent = 0
        for fp in focal_points:
            if fp.get("score", 0) < min_score:
                continue

            actor_tag = ""
            if fp.get("is_known_actor") and fp.get("actor"):
                actor_tag = (
                    f"\n🏢 Acteur connu: {fp['actor']['actor_name']} ({fp['actor']['actor_type']})"
                )

            message = (
                f"🎯 *FOCAL POINT — {fp['entity']}*\n"
                f"Score: {fp['score']} | {fp['source_count']} sources | {fp['mention_count']} mentions\n"
                f"Sources: {', '.join(fp.get('sources', [])[:4])}"
                f"{actor_tag}"
            )

            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    await client.post(
                        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                        json={
                            "chat_id": TELEGRAM_CHAT_ID,
                            "text": message,
                            "parse_mode": "Markdown",
                        },
                    )
                sent += 1
            except Exception as e:
                logger.warning(f"[telegram] Failed to send focal point alert: {e}")

        return sent

    async def get_stats(self) -> dict:
        """Get news database statistics."""
        async with get_session() as session:
            repo = NewsRepository(session)
            total = await repo.count()
            last_24h = await repo.count(since=datetime.utcnow() - timedelta(hours=24))
            by_category = await repo.count_by_category()
            hourly = await repo.count_by_hour(hours=48)

        # Sentiment distribution
        sentiment_dist = await self._get_sentiment_distribution()

        breaker_stats = self._adapter.breaker_stats()
        open_breakers = [s for s in breaker_stats if s["state"] != "closed"]

        return {
            "total_articles": total,
            "last_24h": last_24h,
            "by_category": by_category,
            "hourly_distribution": hourly,
            "sentiment_distribution": sentiment_dist,
            "feeds_active": self._adapter.feed_count,
            "breakers_open": len(open_breakers),
        }

    async def _get_sentiment_distribution(self) -> dict:
        """Get sentiment distribution from DB."""
        from sqlalchemy import func, select

        from src.infrastructure.datasources.models import News

        try:
            async with get_session() as session:
                query = (
                    select(News.sentiment, func.count(News.id))
                    .where(News.sentiment.isnot(None))
                    .group_by(News.sentiment)
                )
                result = await session.execute(query)
                return {row[0]: row[1] for row in result.all()}
        except Exception:
            return {}
