"""Security middleware for the Tawiza API.

This module provides security middleware to protect against:
- Missing security headers
- Rate limiting / DoS attacks
- Request size attacks
- Malformed requests
- honey pot
"""

import time
from collections import defaultdict
from collections.abc import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses.

    Security headers:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 1; mode=block
    - Strict-Transport-Security: max-age=31536000; includeSubDomains
    - Content-Security-Policy: default-src 'self'
    - Referrer-Policy: strict-origin-when-cross-origin
    - Permissions-Policy: geolocation=(), microphone=(), camera=()
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response.

        Args:
            request: Incoming request
            call_next: Next middleware/endpoint

        Returns:
            Response with security headers
        """
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # HSTS (only for HTTPS)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self'"
        )

        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions Policy (disable dangerous features)
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=()"
        )

        # Remove server header to avoid information disclosure
        if "server" in response.headers:
            del response.headers["server"]

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware to prevent DoS attacks.

    Implements token bucket algorithm for rate limiting.
    Limits:
    - 100 requests per minute per IP address
    - 1000 requests per minute globally
    - Burst allowance of 20 requests

    Configuration is customizable through init parameters.
    """

    def __init__(
        self,
        app: ASGIApp,
        requests_per_minute: int = 100,
        burst_size: int = 20,
        global_limit_per_minute: int = 1000,
    ):
        """Initialize rate limiter.

        Args:
            app: ASGI application
            requests_per_minute: Max requests per minute per IP
            burst_size: Burst allowance
            global_limit_per_minute: Global rate limit
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.global_limit_per_minute = global_limit_per_minute

        # Token bucket state: {ip: (tokens, last_refill_time)}
        self.buckets: dict[str, tuple[float, float]] = defaultdict(
            lambda: (float(burst_size), time.time())
        )

        # Global rate limit state
        self.global_bucket: tuple[float, float] = (
            float(global_limit_per_minute),
            time.time()
        )

        # Cleanup old buckets every 1000 requests
        self.request_count = 0

    def _refill_bucket(
        self,
        current_tokens: float,
        last_refill: float,
        rate: float,
        max_tokens: float
    ) -> tuple[float, float]:
        """Refill token bucket based on elapsed time.

        Args:
            current_tokens: Current token count
            last_refill: Last refill timestamp
            rate: Tokens per second refill rate
            max_tokens: Maximum tokens (burst size)

        Returns:
            Tuple of (new_tokens, current_time)
        """
        now = time.time()
        elapsed = now - last_refill
        tokens_to_add = elapsed * rate
        new_tokens = min(current_tokens + tokens_to_add, max_tokens)
        return new_tokens, now

    def _check_rate_limit(self, ip: str) -> bool:
        """Check if request is within rate limit.

        Args:
            ip: Client IP address

        Returns:
            True if within limit, False if rate limited
        """
        # Check global rate limit
        global_tokens, global_last = self.global_bucket
        global_rate = self.global_limit_per_minute / 60.0  # tokens per second
        global_tokens, now = self._refill_bucket(
            global_tokens,
            global_last,
            global_rate,
            float(self.global_limit_per_minute)
        )

        if global_tokens < 1:
            logger.warning("Global rate limit exceeded")
            return False

        self.global_bucket = (global_tokens - 1, now)

        # Check per-IP rate limit
        tokens, last_refill = self.buckets[ip]
        rate = self.requests_per_minute / 60.0  # tokens per second
        tokens, now = self._refill_bucket(
            tokens,
            last_refill,
            rate,
            float(self.burst_size)
        )

        if tokens < 1:
            logger.warning(f"Rate limit exceeded for IP: {ip}")
            return False

        # Consume token
        self.buckets[ip] = (tokens - 1, now)
        return True

    def _cleanup_old_buckets(self) -> None:
        """Remove inactive IP buckets to prevent memory leaks."""
        now = time.time()
        # Remove buckets inactive for > 5 minutes
        inactive_threshold = 300

        to_remove = [
            ip for ip, (_, last_refill) in self.buckets.items()
            if now - last_refill > inactive_threshold
        ]

        for ip in to_remove:
            del self.buckets[ip]

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} inactive rate limit buckets")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Apply rate limiting to request.

        Args:
            request: Incoming request
            call_next: Next middleware/endpoint

        Returns:
            Response or 429 Too Many Requests if rate limited
        """
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"

        # Check rate limit
        if not self._check_rate_limit(client_ip):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "detail": "Too many requests. Please try again later.",
                    "retry_after": 60  # seconds
                },
                headers={"Retry-After": "60"}
            )

        # Periodic cleanup
        self.request_count += 1
        if self.request_count % 1000 == 0:
            self._cleanup_old_buckets()

        response = await call_next(request)
        return response


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Middleware for request validation and size limits.

    Protects against:
    - Oversized requests (DoS)
    - Missing required headers
    - Malformed content-type
    """

    def __init__(
        self,
        app: ASGIApp,
        max_request_size: int = 10 * 1024 * 1024,  # 10 MB
    ):
        """Initialize request validator.

        Args:
            app: ASGI application
            max_request_size: Maximum request body size in bytes
        """
        super().__init__(app)
        self.max_request_size = max_request_size

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Validate incoming request.

        Args:
            request: Incoming request
            call_next: Next middleware/endpoint

        Returns:
            Response or 400/413 error if validation fails
        """
        # Check request size
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > self.max_request_size:
                    logger.warning(
                        f"Request too large: {size} bytes (max: {self.max_request_size})"
                    )
                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={
                            "error": "Request too large",
                            "detail": f"Maximum request size is {self.max_request_size} bytes",
                            "max_size": self.max_request_size,
                        }
                    )
            except ValueError:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "error": "Bad Request",
                        "detail": "Invalid Content-Length header"
                    }
                )

        # Validate Content-Type for POST/PUT/PATCH
        if request.method in {"POST", "PUT", "PATCH"}:
            content_type = request.headers.get("content-type", "")

            # Allow multipart and JSON
            allowed_types = {
                "application/json",
                "multipart/form-data",
                "application/x-www-form-urlencoded",
            }

            # Check if content-type starts with any allowed type
            is_allowed = any(
                content_type.startswith(allowed)
                for allowed in allowed_types
            )

            if not is_allowed and content_length and int(content_length) > 0:
                logger.warning(f"Invalid Content-Type: {content_type}")
                return JSONResponse(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    content={
                        "error": "Unsupported Media Type",
                        "detail": f"Content-Type '{content_type}' not supported",
                        "allowed_types": list(allowed_types),
                    }
                )

        response = await call_next(request)
        return response
