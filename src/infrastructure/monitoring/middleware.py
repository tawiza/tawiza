"""Monitoring middleware for FastAPI."""

import time
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.infrastructure.monitoring.prometheus_metrics import (
    http_request_duration_seconds,
    http_requests_total,
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware to collect Prometheus metrics for HTTP requests."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """Process request and collect metrics.

        Args:
            request: FastAPI request
            call_next: Next middleware/handler

        Returns:
            Response from the handler
        """
        # Start timer
        start_time = time.time()

        # Get method and path
        method = request.method
        path = request.url.path

        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            # Record error
            http_requests_total.labels(
                method=method,
                endpoint=path,
                status="500",
            ).inc()
            raise e

        # Calculate duration
        duration = time.time() - start_time

        # Record metrics
        http_requests_total.labels(
            method=method,
            endpoint=path,
            status=str(status_code),
        ).inc()

        http_request_duration_seconds.labels(
            method=method,
            endpoint=path,
        ).observe(duration)

        return response
