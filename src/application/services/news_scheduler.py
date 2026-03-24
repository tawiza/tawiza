"""Background news intelligence scheduler.

Runs periodic sync + enrichment + focal point detection + alerts.
Can be triggered via API or run as a background task on startup.
"""

import asyncio
from datetime import datetime

from loguru import logger


class NewsScheduler:
    """Periodic news intelligence pipeline.

    Pipeline (every cycle):
    1. Sync RSS feeds → DB
    2. Auto-summarize + sentiment (via LLM)
    3. Detect focal points
    4. Compute department health
    5. Send Telegram alerts for significant events
    """

    def __init__(self, interval_hours: float = 6.0):
        self._interval = interval_hours * 3600
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_run: datetime | None = None
        self._run_count = 0
        self._last_result: dict | None = None

    async def run_once(self) -> dict:
        """Execute one full intelligence cycle."""
        from src.application.services.department_scorer import department_scorer
        from src.application.services.focal_point_detector import focal_detector
        from src.application.services.news_sync_service import NewsSyncService

        start = datetime.utcnow()
        logger.info("[scheduler] Starting news intelligence cycle")

        result = {
            "started_at": start.isoformat(),
            "steps": {},
        }

        # Step 1: Sync feeds
        try:
            service = NewsSyncService()
            sync_result = await service.sync_all(limit=200, auto_enrich=True)
            result["steps"]["sync"] = sync_result
            logger.info(f"[scheduler] Sync: {sync_result.get('inserted', 0)} new articles")
        except Exception as e:
            logger.error(f"[scheduler] Sync failed: {e}")
            result["steps"]["sync"] = {"error": str(e)}

        # Step 2: Detect focal points
        try:
            focal_points = await focal_detector.detect(hours=24, min_sources=2, limit=10)
            result["steps"]["focal_points"] = {
                "count": len(focal_points),
                "top": [{"entity": fp["entity"], "score": fp["score"]} for fp in focal_points[:5]],
            }

            # Alert on significant focal points
            if focal_points:
                service = NewsSyncService()
                sent = await service.alert_focal_points(focal_points, min_score=50)
                result["steps"]["focal_alerts_sent"] = sent

            # Cross-enrich: bridge focal points → relation graph
            if focal_points:
                from src.application.services.news_cross_enricher import (
                    enrich_relations_from_focal_points,
                )

                cross = await enrich_relations_from_focal_points(focal_points)
                result["steps"]["cross_enrichment"] = cross
        except Exception as e:
            logger.error(f"[scheduler] Focal point detection failed: {e}")
            result["steps"]["focal_points"] = {"error": str(e)}

        # Step 3: Department health snapshot
        try:
            health = await department_scorer.score_all()
            result["steps"]["department_health"] = {
                "departments_scored": len(health),
                "top_3": [
                    {"dept": d["department"], "score": d["score"], "grade": d["grade"]}
                    for d in health[:3]
                ],
            }
        except Exception as e:
            logger.error(f"[scheduler] Department scoring failed: {e}")
            result["steps"]["department_health"] = {"error": str(e)}

        elapsed = (datetime.utcnow() - start).total_seconds()
        result["elapsed_seconds"] = round(elapsed, 1)
        result["completed_at"] = datetime.utcnow().isoformat()

        self._last_run = datetime.utcnow()
        self._run_count += 1
        self._last_result = result

        logger.info(f"[scheduler] Cycle complete in {elapsed:.1f}s")
        return result

    async def start(self) -> None:
        """Start the periodic scheduler as a background task."""
        if self._running:
            logger.warning("[scheduler] Already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(f"[scheduler] Started (interval: {self._interval / 3600:.1f}h)")

    async def _loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                await self.run_once()
            except Exception as e:
                logger.error(f"[scheduler] Cycle error: {e}")

            await asyncio.sleep(self._interval)

    def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("[scheduler] Stopped")

    @property
    def status(self) -> dict:
        return {
            "running": self._running,
            "interval_hours": self._interval / 3600,
            "run_count": self._run_count,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "last_result": self._last_result,
        }


# Global singleton
news_scheduler = NewsScheduler()
