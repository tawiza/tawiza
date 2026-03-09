"""Browser automation API endpoints using browser-use and stealth browsers."""

import asyncio
from enum import Enum, StrEnum
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from src.application.ports.agent_ports import TaskNotFoundError
from src.infrastructure.config.settings import get_settings

# Lazy imports pour éviter de charger browser_use au démarrage
if TYPE_CHECKING:
    from src.infrastructure.agents.browser import StealthBrowserPool
    from src.infrastructure.agents.browser_agent_service import BrowserAgentService

router = APIRouter()


# Pydantic models
class BrowserTaskRequest(BaseModel):
    """Request model for browser automation task."""

    description: str = Field(
        ...,
        description="Natural language description of the task",
        min_length=1,
        max_length=1000,
    )
    url: str | None = Field(
        None,
        description="Starting URL (optional)",
    )
    max_actions: int = Field(
        50,
        ge=1,
        le=200,
        description="Maximum actions to perform",
    )
    timeout: int = Field(
        300,
        ge=30,
        le=600,
        description="Timeout in seconds",
    )
    headless: bool = Field(
        True,
        description="Run browser in headless mode",
    )
    model: str = Field(
        "qwen3-coder:30b",
        description="Ollama model to use for the agent",
    )


class BrowserTaskResponse(BaseModel):
    """Response model for browser task."""

    task_id: str
    description: str
    status: str
    result: dict | None = None
    error: str | None = None


class BrowserTaskSummary(BaseModel):
    """Summary of a browser task."""

    task_id: str
    description: str
    status: str
    result_preview: str | None = None
    error: str | None = None


class BrowserHealthResponse(BaseModel):
    """Browser automation health check response."""

    status: str
    browser_available: bool
    ollama_connected: bool


# Dependency to get browser service
async def get_browser_service(
    model: str = "qwen3-coder:30b",
    headless: bool = True,
) -> "BrowserAgentService":
    """
    Get browser agent service instance with configuration from settings.

    Uses Ollama settings for connection pooling and performance optimization.

    Args:
        model: Ollama model to use
        headless: Run in headless mode

    Returns:
        BrowserAgentService instance configured from environment
    """
    # Lazy imports to avoid loading browser_use at startup
    from src.infrastructure.agents.browser_agent_service import BrowserAgentService
    from src.infrastructure.ml.ollama import OllamaAdapter

    settings = get_settings()

    # Create OllamaAdapter with connection pooling from settings
    ollama = OllamaAdapter(
        base_url=settings.ollama.base_url,
        pool_connections=settings.ollama.pool_connections,
        pool_maxsize=settings.ollama.pool_maxsize,
    )

    service = BrowserAgentService(
        ollama_adapter=ollama,
        default_model=model,
        headless=headless,
    )
    return service


@router.post(
    "/execute",
    response_model=BrowserTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Execute browser automation task",
    description="Execute a web automation task using AI-powered browser agent",
)
async def execute_browser_task(
    request: BrowserTaskRequest,
) -> BrowserTaskResponse:
    """
    Execute a browser automation task.

    The agent will:
    1. Navigate to the specified URL (if provided)
    2. Interpret the task description
    3. Perform actions to complete the task
    4. Return results and history

    Args:
        request: Browser task request

    Returns:
        Task response with ID and initial status

    Example:
        ```json
        {
            "description": "Find the price of the first product",
            "url": "https://example.com/shop",
            "max_actions": 20,
            "timeout": 120
        }
        ```
    """
    try:
        # Get service with requested configuration
        service = await get_browser_service(
            model=request.model,
            headless=request.headless,
        )

        # Build task config
        task_config = {
            "description": request.description,
            "max_actions": request.max_actions,
            "timeout": request.timeout,
        }

        if request.url:
            task_config["url"] = request.url

        logger.info(f"Executing browser task: {request.description}")

        # Execute task
        result = await service.execute_task(task_config)

        return BrowserTaskResponse(
            task_id=result["task_id"],
            description=request.description,
            status=result["status"],
            result=result.get("result"),
            error=result.get("error"),
        )

    except Exception as e:
        logger.error(f"Browser task execution failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Task execution failed: {str(e)}",
        )


@router.get(
    "/tasks/{task_id}",
    response_model=BrowserTaskResponse,
    summary="Get browser task status",
    description="Retrieve the status and result of a browser automation task",
)
async def get_task_status(
    task_id: str,
    service: "BrowserAgentService" = Depends(get_browser_service),
) -> BrowserTaskResponse:
    """
    Get browser task status and results.

    Args:
        task_id: Task UUID
        service: Browser agent service

    Returns:
        Task status and results

    Raises:
        HTTPException: If task not found
    """
    try:
        task_status = await service.get_task_status(task_id)

        return BrowserTaskResponse(
            task_id=task_id,
            description=task_status["description"],
            status=task_status["status"],
            result=task_status.get("result"),
            error=task_status.get("error"),
        )

    except Exception as e:
        logger.error(f"Failed to get task status: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )


@router.get(
    "/tasks",
    response_model=list[BrowserTaskSummary],
    summary="List browser tasks",
    description="List all browser automation tasks with optional status filter",
)
async def list_tasks(
    status_filter: str | None = None,
    limit: int = 20,
    offset: int = 0,
    service: "BrowserAgentService" = Depends(get_browser_service),
) -> list[BrowserTaskSummary]:
    """
    List browser automation tasks.

    Args:
        status_filter: Filter by status (pending, running, completed, failed)
        limit: Maximum tasks to return
        offset: Offset for pagination
        service: Browser agent service

    Returns:
        List of task summaries
    """
    try:
        # Convert status filter
        from src.application.ports.agent_ports import TaskStatus

        status_enum = None
        if status_filter:
            status_enum = TaskStatus(status_filter.lower())

        tasks = await service.list_tasks(
            status=status_enum,
            limit=limit,
            offset=offset,
        )

        return [
            BrowserTaskSummary(
                task_id=task["task_id"],
                description=task["description"],
                status=task["status"],
                result_preview=task.get("result_preview"),
                error=task.get("error"),
            )
            for task in tasks
        ]

    except Exception as e:
        logger.error(f"Failed to list tasks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tasks: {str(e)}",
        )


@router.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel browser task",
    description="Cancel a running browser automation task",
)
async def cancel_task(
    task_id: str,
    service: "BrowserAgentService" = Depends(get_browser_service),
) -> None:
    """
    Cancel a browser automation task.

    Args:
        task_id: Task UUID
        service: Browser agent service

    Raises:
        HTTPException: If task not found or cannot be cancelled
    """
    try:
        cancelled = await service.cancel_task(task_id)

        if not cancelled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Task {task_id} cannot be cancelled",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel task: {str(e)}",
        )


@router.get(
    "/health",
    response_model=BrowserHealthResponse,
    summary="Browser automation health check",
    description="Check if browser automation services are available",
)
async def health_check() -> BrowserHealthResponse:
    """
    Check browser automation health.

    Returns:
        Health status including browser and Ollama availability
    """
    try:
        from src.infrastructure.ml.ollama import OllamaAdapter

        settings = get_settings()

        # Check Ollama with settings
        ollama = OllamaAdapter(
            base_url=settings.ollama.base_url,
            pool_connections=settings.ollama.pool_connections,
            pool_maxsize=settings.ollama.pool_maxsize,
        )
        ollama_ok = await ollama.health_check()

        # Check browser (create temporary service)
        service = await get_browser_service()
        browser_ok = await service.health_check()

        overall_status = "healthy" if (ollama_ok and browser_ok) else "degraded"

        return BrowserHealthResponse(
            status=overall_status,
            browser_available=browser_ok,
            ollama_connected=ollama_ok,
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return BrowserHealthResponse(
            status="unhealthy",
            browser_available=False,
            ollama_connected=False,
        )


@router.get(
    "/tasks/{task_id}/progress",
    summary="Stream browser task progress (SSE)",
    description="Stream real-time progress updates for a browser automation task via Server-Sent Events",
)
async def stream_browser_task_progress(
    task_id: str,
    service: "BrowserAgentService" = Depends(get_browser_service),
):
    """
    Stream real-time progress updates for a browser task via Server-Sent Events (SSE).

    This endpoint provides live progress updates including:
    - Current progress percentage (0-100)
    - Current step description
    - Status (pending/running/completed/failed)
    - Timestamps
    - Error messages (if failed)

    Args:
        task_id: Task identifier returned by /execute endpoint
        service: Browser agent service (injected)

    Returns:
        StreamingResponse: SSE stream with progress events

    Example client code (JavaScript):
        ```javascript
        const eventSource = new EventSource(
            `/api/v1/browser/tasks/${taskId}/progress`
        );

        eventSource.onmessage = (event) => {
            const progress = JSON.parse(event.data);
            console.log(`Progress: ${progress.progress}%`);
            console.log(`Step: ${progress.current_step}`);

            if (progress.status === 'completed') {
                eventSource.close();
            }
        };

        eventSource.onerror = (error) => {
            console.error('SSE error:', error);
            eventSource.close();
        };
        ```

    Example client code (Python):
        ```python
        import requests

        url = f"http://localhost:8000/api/v1/browser/tasks/{task_id}/progress"

        with requests.get(url, stream=True) as response:
            for line in response.iter_lines():
                if line and line.startswith(b'data:'):
                    data = json.loads(line[5:])
                    print(f"Progress: {data['progress']}% - {data['current_step']}")

                    if data['status'] in ['completed', 'failed']:
                        break
        ```
    """
    async def event_generator():
        """Generate Server-Sent Events for task progress."""
        try:
            logger.info(f"Client connected to browser task progress stream: {task_id}")

            async for progress_update in service.stream_progress(task_id):
                # Format as SSE: data: {JSON}\n\n
                import json
                data = json.dumps(progress_update)
                yield f"data: {data}\n\n"

                # Stop if task finished
                if progress_update.get("status") in ["completed", "failed", "cancelled"]:
                    logger.info(
                        f"Browser task {task_id} finished with status: {progress_update.get('status')}"
                    )
                    break

            # Send close event
            yield "event: close\ndata: {}\n\n"

        except TaskNotFoundError:
            logger.warning(f"Task {task_id} not found in progress tracker")
            error_data = json.dumps({"error": f"Task {task_id} not found"})
            yield f"event: error\ndata: {error_data}\n\n"

        except asyncio.CancelledError:
            logger.info(f"Client disconnected from browser task progress stream: {task_id}")
            raise

        except Exception as e:
            logger.error(f"Error streaming browser task progress for {task_id}: {e}")
            import json
            error_data = json.dumps({"error": str(e)})
            yield f"event: error\ndata: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


# ============================================================================
# Stealth Browser Endpoints (nodriver + Camoufox)
# ============================================================================


class StealthBrowserTypeEnum(StrEnum):
    """Browser type selection for stealth requests."""
    AUTO = "auto"  # Automatic selection based on domain
    NODRIVER = "nodriver"  # Chrome-based, CDP direct
    CAMOUFOX = "camoufox"  # Firefox-based, C++ hooks
    PLAYWRIGHT = "playwright"  # Standard Playwright (fallback)


class StealthFetchRequest(BaseModel):
    """Request model for stealth browser fetch."""
    url: str = Field(
        ...,
        description="URL to fetch",
        min_length=1,
    )
    browser: StealthBrowserTypeEnum = Field(
        StealthBrowserTypeEnum.AUTO,
        description="Browser type (auto, nodriver, camoufox, playwright)",
    )
    territory: str | None = Field(
        None,
        description="French department code for geolocation (e.g., '75' for Paris)",
    )
    headless: bool = Field(
        True,
        description="Run browser in headless mode",
    )
    max_retries: int = Field(
        2,
        ge=0,
        le=5,
        description="Maximum retry attempts with fallback browsers",
    )
    take_screenshot: bool = Field(
        True,
        description="Include screenshot in response",
    )


class StealthFetchResponse(BaseModel):
    """Response model for stealth browser fetch."""
    success: bool
    url: str | None = None
    content: str | None = None
    screenshot_b64: str | None = None
    browser_used: str | None = None
    duration_ms: int = 0
    retries: int = 0
    error: str | None = None


class StealthBrowserStatus(BaseModel):
    """Status of stealth browser availability."""
    nodriver_available: bool
    camoufox_available: bool
    recommended: str
    domain_preferences: dict[str, str] = Field(default_factory=dict)


# Global stealth pool instance (lazy init)
_stealth_pool: "StealthBrowserPool | None" = None


def get_stealth_pool(
    headless: bool = True,
    territory: str | None = None,
) -> "StealthBrowserPool":
    """Get or create stealth browser pool."""
    from src.infrastructure.agents.browser import StealthBrowserPool

    global _stealth_pool
    if _stealth_pool is None:
        _stealth_pool = StealthBrowserPool(
            headless=headless,
            territory=territory,
            max_parallel=3,
        )
    return _stealth_pool


@router.post(
    "/stealth/fetch",
    response_model=StealthFetchResponse,
    summary="Fetch URL using stealth browser",
    description="Fetch a URL using anti-detection browsers (nodriver/Camoufox) for protected sites",
)
async def stealth_fetch(request: StealthFetchRequest) -> StealthFetchResponse:
    """
    Fetch URL using stealth browser with automatic browser selection.

    Features:
    - Automatic browser selection based on domain (gov sites → Camoufox)
    - Fallback chain: nodriver → Camoufox → Playwright
    - Domain preference learning
    - Optional screenshot capture

    Args:
        request: Stealth fetch request

    Returns:
        StealthFetchResponse with content or error

    Example:
        ```json
        {
            "url": "https://service-public.fr/...",
            "browser": "auto",
            "territory": "75",
            "take_screenshot": true
        }
        ```
    """
    try:
        pool = get_stealth_pool(
            headless=request.headless,
            territory=request.territory,
        )

        # Map browser selection
        preferred_browser = None
        if request.browser != StealthBrowserTypeEnum.AUTO:
            from src.infrastructure.agents.browser import BrowserType as StealthBrowserType

            browser_map = {
                StealthBrowserTypeEnum.NODRIVER: StealthBrowserType.NODRIVER,
                StealthBrowserTypeEnum.CAMOUFOX: StealthBrowserType.CAMOUFOX,
                StealthBrowserTypeEnum.PLAYWRIGHT: StealthBrowserType.PLAYWRIGHT,
            }
            preferred_browser = browser_map.get(request.browser)

        logger.info(f"Stealth fetch: {request.url} (browser={request.browser})")

        result = await pool.fetch(
            url=request.url,
            preferred_browser=preferred_browser,
            max_retries=request.max_retries,
        )

        return StealthFetchResponse(
            success=result.success,
            url=result.url,
            content=result.content if result.success else None,
            screenshot_b64=result.screenshot_b64 if request.take_screenshot else None,
            browser_used=result.browser_used.value if result.browser_used else None,
            duration_ms=result.duration_ms,
            retries=result.retries,
            error=result.error,
        )

    except Exception as e:
        logger.error(f"Stealth fetch failed: {e}", exc_info=True)
        return StealthFetchResponse(
            success=False,
            url=request.url,
            error=str(e),
        )


@router.get(
    "/stealth/status",
    response_model=StealthBrowserStatus,
    summary="Get stealth browser status",
    description="Check availability of stealth browsers (nodriver, Camoufox)",
)
async def stealth_status() -> StealthBrowserStatus:
    """
    Get status of stealth browser availability.

    Returns:
        StealthBrowserStatus with availability info and recommendations
    """
    from src.infrastructure.agents.browser import CAMOUFOX_AVAILABLE, NODRIVER_AVAILABLE

    # Determine recommended browser
    if NODRIVER_AVAILABLE and CAMOUFOX_AVAILABLE:
        recommended = "auto"
    elif NODRIVER_AVAILABLE:
        recommended = "nodriver"
    elif CAMOUFOX_AVAILABLE:
        recommended = "camoufox"
    else:
        recommended = "playwright"

    # Get pool stats if available
    domain_preferences = {}
    if _stealth_pool:
        stats = _stealth_pool.get_stats()
        domain_preferences = {
            domain: prefs["browser"]
            for domain, prefs in stats.get("domain_preferences", {}).items()
        }

    return StealthBrowserStatus(
        nodriver_available=NODRIVER_AVAILABLE,
        camoufox_available=CAMOUFOX_AVAILABLE,
        recommended=recommended,
        domain_preferences=domain_preferences,
    )


@router.post(
    "/stealth/batch",
    response_model=list[StealthFetchResponse],
    summary="Batch fetch URLs using stealth browsers",
    description="Fetch multiple URLs in parallel using stealth browsers",
)
async def stealth_batch_fetch(
    urls: list[str],
    browser: StealthBrowserTypeEnum = StealthBrowserTypeEnum.AUTO,
    territory: str | None = None,
    headless: bool = True,
    max_parallel: int = 3,
) -> list[StealthFetchResponse]:
    """
    Batch fetch multiple URLs using stealth browsers.

    Args:
        urls: List of URLs to fetch
        browser: Browser type selection
        territory: French department code for geolocation
        headless: Run browser in headless mode
        max_parallel: Maximum parallel requests

    Returns:
        List of StealthFetchResponse (in same order as input URLs)
    """
    if len(urls) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 URLs per batch request",
        )

    try:
        pool = get_stealth_pool(headless=headless, territory=territory)

        results = await pool.fetch_batch(urls, max_parallel=max_parallel)

        return [
            StealthFetchResponse(
                success=r.success,
                url=r.url,
                content=r.content if r.success else None,
                browser_used=r.browser_used.value if r.browser_used else None,
                duration_ms=r.duration_ms,
                retries=r.retries,
                error=r.error,
            )
            for r in results
        ]

    except Exception as e:
        logger.error(f"Stealth batch fetch failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch fetch failed: {str(e)}",
        )
