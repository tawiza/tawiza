"""Request ID Middleware - Adds correlation ID to all requests.

This middleware:
- Generates or extracts request IDs for tracing
- Adds the ID to response headers
- Sets context for logging correlation

Usage:
    app.add_middleware(RequestIDMiddleware)

    # In any handler, the request_id is available via:
    from src.core.logging_config import get_request_id
    request_id = get_request_id()
"""

import uuid
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.core.logging_config import logger, set_request_id, set_user_id

REQUEST_ID_HEADER = "X-Request-ID"
CORRELATION_ID_HEADER = "X-Correlation-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware that adds request ID to all requests.

    Checks for existing request ID in headers, generates one if missing,
    and adds it to response headers for tracing.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        # Get or generate request ID
        request_id = (
            request.headers.get(REQUEST_ID_HEADER)
            or request.headers.get(CORRELATION_ID_HEADER)
            or str(uuid.uuid4())
        )

        # Set in context for logging
        set_request_id(request_id)

        # Extract user ID if available (from auth header, etc.)
        user_id = request.headers.get("X-User-ID")
        if user_id:
            set_user_id(user_id)

        # Store in request state for handlers
        request.state.request_id = request_id

        # Log request start
        logger.info(
            f"{request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query": str(request.query_params),
            },
        )

        # Process request
        response = await call_next(request)

        # Add request ID to response headers
        response.headers[REQUEST_ID_HEADER] = request_id

        # Log response
        logger.info(
            f"{request.method} {request.url.path} - {response.status_code}",
            extra={
                "request_id": request_id,
                "status_code": response.status_code,
            },
        )

        return response


def get_request_id_from_request(request: Request) -> str:
    """Get request ID from request state.

    Args:
        request: Starlette/FastAPI request

    Returns:
        Request ID string
    """
    return getattr(request.state, "request_id", "unknown")
