"""Crawler API routes."""

from typing import Any

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from src.application.services.crawler_scheduler import get_crawler_scheduler

router = APIRouter(prefix="/crawler", tags=["crawler"])


class CrawlRequest(BaseModel):
    """Request to trigger a crawl."""
    source_id: str | None = None


class CrawlResponse(BaseModel):
    """Response from crawl operation."""
    success: bool
    results_count: int
    results: list[dict[str, Any]]


class StatsResponse(BaseModel):
    """Crawler statistics."""
    total_sources: int
    results_cached: int
    is_running: bool


class RelevanceFeedback(BaseModel):
    """Feedback on source relevance."""
    source_id: str
    was_useful: bool


@router.post("/start")
async def start_crawler() -> dict[str, str]:
    """Start the crawler scheduler."""
    scheduler = get_crawler_scheduler()
    await scheduler.start()
    return {"status": "started"}


@router.post("/stop")
async def stop_crawler() -> dict[str, str]:
    """Stop the crawler scheduler."""
    scheduler = get_crawler_scheduler()
    await scheduler.stop()
    return {"status": "stopped"}


@router.post("/crawl", response_model=CrawlResponse)
async def trigger_crawl(request: CrawlRequest | None = None) -> CrawlResponse:
    """Trigger an immediate crawl."""
    scheduler = get_crawler_scheduler()

    try:
        source_id = request.source_id if request else None
        results = await scheduler.crawl_now(source_id)

        return CrawlResponse(
            success=True,
            results_count=len(results),
            results=results,
        )
    except Exception as e:
        logger.error(f"Crawl error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=StatsResponse)
async def get_stats() -> StatsResponse:
    """Get crawler statistics."""
    scheduler = get_crawler_scheduler()
    stats = scheduler.get_source_stats()

    return StatsResponse(
        total_sources=stats.get("total_sources", 0),
        results_cached=stats.get("results_cached", 0),
        is_running=stats.get("is_running", False),
    )


@router.get("/results")
async def get_results(limit: int = 100) -> list[dict[str, Any]]:
    """Get recent crawl results."""
    scheduler = get_crawler_scheduler()
    return scheduler.get_recent_results(limit)


@router.post("/feedback")
async def submit_feedback(feedback: RelevanceFeedback) -> dict[str, str]:
    """Submit relevance feedback for MAB learning."""
    scheduler = get_crawler_scheduler()
    scheduler.update_relevance(feedback.source_id, feedback.was_useful)
    return {"status": "feedback recorded"}
