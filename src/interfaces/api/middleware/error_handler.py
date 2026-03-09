"""Error Handler Middleware - Centralized exception handling.

This middleware catches all exceptions and converts them to
consistent API responses using the domain exception hierarchy.

Usage:
    app.add_middleware(ErrorHandlerMiddleware)
"""

import traceback
from collections.abc import Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.logging_config import get_request_id, logger
from src.domain.exceptions import (
    InfrastructureError,
    TawizaError,
    wrap_error,
)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware that catches exceptions and returns consistent error responses."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> JSONResponse:
        try:
            return await call_next(request)

        except TawizaError as e:
            # Known domain error - log and return structured response
            logger.warning(
                f"Domain error: {e}",
                extra={
                    "error_code": e.code,
                    "details": e.details,
                },
            )
            return self._error_response(e)

        except Exception as e:
            # Unknown error - log full traceback and wrap
            request_id = get_request_id()
            logger.error(
                f"Unhandled exception: {e}",
                extra={
                    "request_id": request_id,
                    "traceback": traceback.format_exc(),
                },
            )

            # Wrap in infrastructure error
            wrapped = wrap_error(
                e,
                InfrastructureError,
                message="An unexpected error occurred",
            )
            wrapped.details["request_id"] = request_id

            return self._error_response(wrapped)

    def _error_response(self, error: TawizaError) -> JSONResponse:
        """Create JSON error response from exception."""
        request_id = get_request_id()

        return JSONResponse(
            status_code=error.http_status,
            content={
                "success": False,
                "error": {
                    "code": error.code,
                    "message": error.message,
                    "details": error.details,
                },
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id or "unknown"},
        )


# FastAPI exception handlers (alternative to middleware)

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException


def register_exception_handlers(app: FastAPI) -> None:
    """Register exception handlers on FastAPI app.

    Use this instead of middleware for more control.

    Args:
        app: FastAPI application instance
    """

    @app.exception_handler(TawizaError)
    async def tawiza_error_handler(request: Request, exc: TawizaError):
        request_id = get_request_id()
        logger.warning(f"Domain error: {exc}", extra={"error_code": exc.code})

        return JSONResponse(
            status_code=exc.http_status,
            content={
                "success": False,
                "error": exc.to_dict(),
                "request_id": request_id,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        request_id = get_request_id()
        logger.warning(f"Validation error: {exc.errors()}")

        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "code": "TWZ-API-001",
                    "message": "Request validation failed",
                    "details": {"errors": exc.errors()},
                },
                "request_id": request_id,
            },
        )

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException):
        request_id = get_request_id()

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": f"TWZ-API-{exc.status_code}",
                    "message": exc.detail,
                    "details": {},
                },
                "request_id": request_id,
            },
        )

    @app.exception_handler(Exception)
    async def general_error_handler(request: Request, exc: Exception):
        request_id = get_request_id()
        logger.error(
            f"Unhandled exception: {exc}",
            extra={"traceback": traceback.format_exc()},
        )

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "TWZ-INF-000",
                    "message": "An unexpected error occurred",
                    "details": {"request_id": request_id},
                },
                "request_id": request_id,
            },
        )
