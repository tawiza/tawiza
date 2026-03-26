"""
Progress Streaming Router

Server-Sent Events (SSE) endpoints for real-time progress tracking.
"""

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from src.infrastructure.config.settings import get_settings
from src.infrastructure.streaming import ProgressStatus, ProgressTracker

router = APIRouter()

# Global progress tracker instance
# In production, this would be injected via DI container
_progress_tracker: ProgressTracker | None = None


def get_progress_tracker() -> ProgressTracker:
    """
    Get or create progress tracker instance with configuration from settings.

    Returns:
        ProgressTracker: Progress tracker singleton configured from environment
    """
    global _progress_tracker
    if _progress_tracker is None:
        settings = get_settings()
        _progress_tracker = ProgressTracker(
            cleanup_after=settings.monitoring.progress_cleanup_after,
            max_events_per_task=settings.monitoring.progress_max_events_per_task,
        )
        logger.info(
            f"ProgressTracker initialized with settings: "
            f"cleanup={settings.monitoring.progress_cleanup_after}s, "
            f"max_events={settings.monitoring.progress_max_events_per_task}"
        )
    return _progress_tracker


@router.get("/stream/{task_id}")
async def stream_task_progress(
    task_id: str, tracker: ProgressTracker = Depends(get_progress_tracker)
):
    """
    Stream real-time progress updates for a task via Server-Sent Events (SSE).

    Args:
        task_id: Task identifier

    Returns:
        StreamingResponse: SSE stream

    Example client code (JavaScript):
        ```javascript
        const eventSource = new EventSource('/api/v1/progress/stream/task-123');

        eventSource.onmessage = (event) => {
            const progress = JSON.parse(event.data);
            console.log(`Progress: ${progress.progress}%`);
            updateUI(progress);
        };

        eventSource.onerror = (error) => {
            console.error('SSE error:', error);
            eventSource.close();
        };
        ```
    """
    # Check if task exists
    latest = await tracker.get_latest_progress(task_id)
    if latest is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    async def event_generator():
        """
        Generate Server-Sent Events.

        Yields SSE-formatted messages with progress updates.
        """
        try:
            logger.info(f"Client connected to progress stream: {task_id}")

            async for event in tracker.stream_progress(task_id, send_history=True):
                # Format as SSE
                # data: {JSON}\n\n
                event_data = event.to_dict()
                yield f"data: {event_data}\n\n"

                # Stop if task finished
                if event.status in [
                    ProgressStatus.COMPLETED,
                    ProgressStatus.FAILED,
                    ProgressStatus.CANCELLED,
                ]:
                    logger.info(f"Task {task_id} finished, closing stream")
                    break

            # Send final close event
            yield "event: close\ndata: {}\n\n"

        except asyncio.CancelledError:
            logger.info(f"Client disconnected from progress stream: {task_id}")
            raise
        except Exception as e:
            logger.error(f"Error streaming progress for {task_id}: {e}")
            yield 'event: error\ndata: {"error": "Erreur interne du serveur"}\n\n'

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get("/latest/{task_id}")
async def get_latest_progress(
    task_id: str, tracker: ProgressTracker = Depends(get_progress_tracker)
) -> dict[str, Any]:
    """
    Get the latest progress event for a task.

    Args:
        task_id: Task identifier

    Returns:
        Latest progress event

    Raises:
        HTTPException: If task not found
    """
    latest = await tracker.get_latest_progress(task_id)

    if latest is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return latest.to_dict()


@router.get("/history/{task_id}")
async def get_progress_history(
    task_id: str, limit: int = 100, tracker: ProgressTracker = Depends(get_progress_tracker)
) -> dict[str, Any]:
    """
    Get progress history for a task.

    Args:
        task_id: Task identifier
        limit: Maximum events to return (default: 100)

    Returns:
        Progress history with events

    Raises:
        HTTPException: If task not found
    """
    history = await tracker.get_progress_history(task_id, limit=limit)

    if not history:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return {
        "task_id": task_id,
        "event_count": len(history),
        "events": [event.to_dict() for event in history],
    }


@router.get("/active")
async def get_active_tasks(
    tracker: ProgressTracker = Depends(get_progress_tracker),
) -> dict[str, Any]:
    """
    Get list of currently active tasks.

    Returns:
        List of active task IDs
    """
    active_tasks = await tracker.get_active_tasks()

    return {"active_task_count": len(active_tasks), "task_ids": active_tasks}


@router.get("/stats")
async def get_tracker_stats(
    tracker: ProgressTracker = Depends(get_progress_tracker),
) -> dict[str, Any]:
    """
    Get progress tracker statistics.

    Returns:
        Tracker statistics
    """
    stats = await tracker.get_stats()

    return {"status": "operational", "tracker": stats}


@router.post("/cleanup")
async def cleanup_old_tasks(
    tracker: ProgressTracker = Depends(get_progress_tracker),
) -> dict[str, str]:
    """
    Manually trigger cleanup of old completed tasks.

    Returns:
        Cleanup result
    """
    try:
        await tracker.cleanup_old_tasks()
        return {"status": "success", "message": "Old tasks cleaned up successfully"}
    except Exception as e:
        logger.error(f"Failed to cleanup old tasks: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
