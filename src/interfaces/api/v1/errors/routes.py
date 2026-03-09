"""Frontend error reporting endpoint."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.core.logging_config import logger

router = APIRouter(prefix="/api/v1/errors", tags=["Error Reporting"])


class FrontendError(BaseModel):
    message: str
    stack: str | None = None
    componentStack: str | None = None
    digest: str | None = None
    url: str | None = None
    timestamp: str | None = None
    source: str | None = None


@router.post("/frontend")
async def report_frontend_error(error: FrontendError, request: Request):
    """Receive and log frontend errors."""
    logger.error(
        f"Frontend error [{error.source}]: {error.message}",
        extra={
            "frontend_url": error.url,
            "stack": error.stack,
            "component_stack": error.componentStack,
            "digest": error.digest,
            "source": error.source,
            "client_ip": request.client.host if request.client else "unknown",
        },
    )
    return {"status": "received"}
