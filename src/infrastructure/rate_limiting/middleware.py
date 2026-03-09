"""Rate limiting middleware for FastAPI."""

from collections.abc import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

from src.infrastructure.rate_limiting.token_bucket import RateLimiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using Token Bucket algorithm.

    Limits requests per client IP to prevent abuse.
    Excludes health check and static asset endpoints.
    """

    # Endpoints excluded from rate limiting
    EXCLUDED_PATHS = {
        "/health",
        "/",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/ws",
        "/ws/status",
    }

    # Prefixes excluded from rate limiting
    EXCLUDED_PREFIXES = (
        "/static/",
        "/_next/",
        "/img/",
    )

    def __init__(
        self,
        app,
        capacity: float = 100,
        refill_rate: float = 10,
        key_func: Callable[[Request], str] | None = None,
    ):
        """
        Initialize rate limiter middleware.

        Args:
            app: FastAPI application
            capacity: Max requests per burst (default: 100)
            refill_rate: Requests refilled per second (default: 10/s)
            key_func: Custom function to extract rate limit key from request
        """
        super().__init__(app)
        self.limiter = RateLimiter(
            capacity=capacity,
            refill_rate=refill_rate,
        )
        self.key_func = key_func or self._default_key_func
        logger.info(
            f"Rate limiter initialized: {capacity} capacity, {refill_rate}/s refill"
        )

    def _default_key_func(self, request: Request) -> str:
        """Extract client identifier from request (default: IP address)."""
        # Try to get real IP from proxy headers
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Take first IP (original client)
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return "unknown"

    def _should_limit(self, path: str) -> bool:
        """Check if path should be rate limited."""
        # Exclude exact paths
        if path in self.EXCLUDED_PATHS:
            return False

        # Exclude path prefixes
        return not path.startswith(self.EXCLUDED_PREFIXES)

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request through rate limiter."""
        path = request.url.path

        # Skip rate limiting for excluded paths
        if not self._should_limit(path):
            return await call_next(request)

        # Get client key
        client_key = self.key_func(request)

        # Check rate limit
        if not self.limiter.allow(client_key):
            # Calculate retry after time
            wait_time = self.limiter.wait_time(client_key)
            retry_after = int(wait_time) + 1

            logger.warning(
                f"Rate limit exceeded for {client_key} on {path}"
            )

            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "message": "Rate limit exceeded. Please slow down.",
                    "retry_after_seconds": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(int(self.limiter.capacity)),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # Get current bucket stats for headers
        bucket = self.limiter._get_bucket(client_key)
        remaining = int(bucket.tokens)

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(int(self.limiter.capacity))
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response
