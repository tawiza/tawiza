"""Watcher API routes - Polling daemon control and alert management."""

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

from src.infrastructure.dashboard import DashboardDB
from src.infrastructure.watcher.daemon import WatcherDaemon
from src.infrastructure.watcher.storage import WatcherStorage

router = APIRouter(prefix="/api/v1/watcher", tags=["Watcher"])

# Singleton daemon instance
_daemon: WatcherDaemon | None = None


def get_daemon() -> WatcherDaemon:
    """Get or create the daemon singleton."""
    global _daemon
    if _daemon is None:
        _daemon = WatcherDaemon()
    return _daemon


# ============================================================================
# Pydantic Models
# ============================================================================


class WatcherStatus(BaseModel):
    """Watcher daemon status."""

    running: bool
    sources: dict


class AlertResponse(BaseModel):
    """Alert response model."""

    id: int
    source: str
    title: str
    url: str | None = None
    summary: str | None = None
    keywords_matched: list[str] = Field(default_factory=list)
    score: float = 0.0
    read: bool = False
    created_at: str


class AlertsListResponse(BaseModel):
    """List of alerts."""

    alerts: list[AlertResponse]
    total: int
    unread_count: int


class KeywordCreate(BaseModel):
    """Keyword to add to watchlist."""

    keyword: str
    sources: list[str] = Field(
        default=["bodacc", "boamp", "gdelt"], description="Sources to watch: bodacc, boamp, gdelt"
    )


class WatchlistResponse(BaseModel):
    """Watchlist response."""

    keywords: list[dict]
    total: int


class PollRequest(BaseModel):
    """Request to force poll."""

    source: str | None = Field(
        default=None, description="Source to poll (bodacc, boamp, gdelt) or None for all"
    )


# ============================================================================
# Daemon Control Endpoints
# ============================================================================


@router.post("/start")
async def start_daemon(background_tasks: BackgroundTasks):
    """Start the watcher daemon.

    Begins polling BODACC, BOAMP, and GDELT for matching entries.
    """
    daemon = get_daemon()

    if daemon.running:
        return {"status": "already_running", "message": "Daemon is already running"}

    background_tasks.add_task(daemon.start)

    return {
        "status": "starting",
        "message": "Watcher daemon is starting",
        "sources": list(daemon.INTERVALS.keys()),
    }


@router.post("/stop")
async def stop_daemon():
    """Stop the watcher daemon."""
    daemon = get_daemon()

    if not daemon.running:
        return {"status": "not_running", "message": "Daemon is not running"}

    await daemon.stop()

    return {"status": "stopped", "message": "Watcher daemon stopped"}


@router.get("/status", response_model=WatcherStatus)
async def get_status():
    """Get daemon status and polling information."""
    daemon = get_daemon()
    status = daemon.get_status()

    return WatcherStatus(running=status["running"], sources=status["sources"])


@router.post("/poll")
async def force_poll(request: PollRequest, background_tasks: BackgroundTasks):
    """Force an immediate poll of data sources.

    Bypasses the normal interval and polls immediately.
    """
    daemon = get_daemon()

    if not daemon.running:
        # Start temporarily for this poll
        await daemon.start()

    background_tasks.add_task(daemon.force_poll, request.source)

    source_str = request.source or "all sources"
    return {
        "status": "polling",
        "message": f"Forcing poll of {source_str}",
        "source": request.source,
    }


# ============================================================================
# Alert Endpoints
# ============================================================================


@router.get("/alerts", response_model=AlertsListResponse)
async def list_alerts(
    source: str | None = Query(default=None, description="Filter by source"),
    unread_only: bool = Query(default=False, description="Only show unread alerts"),
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
):
    """List alerts from the watchlist.

    Returns alerts matching your configured keywords.
    """
    db = DashboardDB()
    storage = WatcherStorage(db)

    try:
        # Get alerts from storage
        alerts_data = storage.get_alerts(
            source=source, unread_only=unread_only, limit=limit, offset=offset
        )

        alerts = [
            AlertResponse(
                id=a["id"],
                source=a["source"],
                title=a["title"],
                url=a.get("url"),
                summary=a.get("summary"),
                keywords_matched=a.get("keywords_matched", []),
                score=a.get("score", 0.0),
                read=a.get("read", False),
                created_at=a.get("created_at", ""),
            )
            for a in alerts_data
        ]

        total = storage.count_alerts(source=source, unread_only=unread_only)
        unread = storage.count_alerts(unread_only=True)

        return AlertsListResponse(alerts=alerts, total=total, unread_count=unread)

    except Exception as e:
        logger.error(f"Failed to list alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: int):
    """Get a specific alert by ID."""
    db = DashboardDB()
    storage = WatcherStorage(db)

    try:
        alert = storage.get_alert(alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

        return AlertResponse(**alert)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/alerts/{alert_id}/read")
async def mark_alert_read(alert_id: int):
    """Mark an alert as read."""
    db = DashboardDB()
    storage = WatcherStorage(db)

    try:
        success = storage.mark_read(alert_id)
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")

        return {"status": "success", "alert_id": alert_id, "read": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to mark alert read: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: int):
    """Delete an alert."""
    db = DashboardDB()
    storage = WatcherStorage(db)

    try:
        success = storage.delete_alert(alert_id)
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")

        return {"status": "success", "alert_id": alert_id, "deleted": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Watchlist Management
# ============================================================================


@router.get("/watchlist", response_model=WatchlistResponse)
async def get_watchlist():
    """Get all keywords in the watchlist."""
    db = DashboardDB()
    storage = WatcherStorage(db)

    try:
        keywords = storage.get_watchlist()

        return WatchlistResponse(keywords=keywords, total=len(keywords))

    except Exception as e:
        logger.error(f"Failed to get watchlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/watchlist")
async def add_keyword(keyword: KeywordCreate):
    """Add a keyword to the watchlist."""
    db = DashboardDB()
    storage = WatcherStorage(db)

    try:
        keyword_id = storage.add_keyword(keyword=keyword.keyword, sources=keyword.sources)

        return {
            "status": "success",
            "keyword_id": keyword_id,
            "keyword": keyword.keyword,
            "sources": keyword.sources,
        }

    except Exception as e:
        logger.error(f"Failed to add keyword: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/watchlist/{keyword_id}")
async def remove_keyword(keyword_id: int):
    """Remove a keyword from the watchlist."""
    db = DashboardDB()
    storage = WatcherStorage(db)

    try:
        success = storage.remove_keyword(keyword_id)
        if not success:
            raise HTTPException(status_code=404, detail="Keyword not found")

        return {"status": "success", "keyword_id": keyword_id, "deleted": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove keyword: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Health Check
# ============================================================================


@router.get("/health")
async def health_check():
    """Watcher service health check."""
    daemon = get_daemon()

    return {
        "status": "healthy",
        "daemon_running": daemon.running,
        "sources": list(daemon.INTERVALS.keys()),
    }
