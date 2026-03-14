"""Domain Exceptions - Centralized exception hierarchy.

This module defines all domain-specific exceptions for Tawiza-V2.
Each exception has an error code for API responses and logging.

Usage:
    from src.domain.exceptions import EntityNotFoundError, ValidationError

    raise EntityNotFoundError("Model", model_id)
    raise ValidationError("Invalid input", details={"field": "name"})

Error Code Format: TWZ-{CATEGORY}-{NUMBER}
- TWZ-DOM-xxx: Domain errors
- TWZ-APP-xxx: Application/use case errors
- TWZ-INF-xxx: Infrastructure errors
- TWZ-API-xxx: API/interface errors
"""

from typing import Any


class TawizaError(Exception):
    """Base exception for all Tawiza errors.

    Attributes:
        message: Human-readable error message
        code: Error code for programmatic handling
        details: Additional error context
    """

    code: str = "TWZ-000-000"
    http_status: int = 500

    def __init__(
        self,
        message: str,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        if code:
            self.code = code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert to API-friendly dictionary."""
        return {
            "error": True,
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


# =============================================================================
# Domain Errors (TWZ-DOM-xxx)
# =============================================================================


class DomainError(TawizaError):
    """Base for domain layer errors."""

    code = "TWZ-DOM-000"
    http_status = 400


class EntityNotFoundError(DomainError):
    """Entity was not found in the system."""

    code = "TWZ-DOM-001"
    http_status = 404

    def __init__(
        self,
        entity_type: str,
        entity_id: Any,
        details: dict[str, Any] | None = None,
    ):
        message = f"{entity_type} with ID '{entity_id}' not found"
        super().__init__(
            message,
            details={
                "entity_type": entity_type,
                "entity_id": str(entity_id),
                **(details or {}),
            },
        )


class EntityAlreadyExistsError(DomainError):
    """Entity already exists (duplicate)."""

    code = "TWZ-DOM-002"
    http_status = 409

    def __init__(
        self,
        entity_type: str,
        identifier: Any,
        details: dict[str, Any] | None = None,
    ):
        message = f"{entity_type} with identifier '{identifier}' already exists"
        super().__init__(
            message,
            details={
                "entity_type": entity_type,
                "identifier": str(identifier),
                **(details or {}),
            },
        )


class ValidationError(DomainError):
    """Input validation failed."""

    code = "TWZ-DOM-003"
    http_status = 422

    def __init__(
        self,
        message: str,
        field: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message,
            details={
                "field": field,
                **(details or {}),
            },
        )


class InvalidStateError(DomainError):
    """Entity is in an invalid state for the requested operation."""

    code = "TWZ-DOM-004"
    http_status = 409

    def __init__(
        self,
        entity_type: str,
        current_state: str,
        required_state: str,
        operation: str,
        details: dict[str, Any] | None = None,
    ):
        message = (
            f"Cannot {operation} {entity_type}: "
            f"current state is '{current_state}', requires '{required_state}'"
        )
        super().__init__(
            message,
            details={
                "entity_type": entity_type,
                "current_state": current_state,
                "required_state": required_state,
                "operation": operation,
                **(details or {}),
            },
        )


class BusinessRuleViolationError(DomainError):
    """A business rule was violated."""

    code = "TWZ-DOM-005"
    http_status = 422

    def __init__(
        self,
        rule: str,
        message: str,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message,
            details={
                "rule": rule,
                **(details or {}),
            },
        )


# =============================================================================
# Application Errors (TWZ-APP-xxx)
# =============================================================================


class ApplicationError(TawizaError):
    """Base for application/use case errors."""

    code = "TWZ-APP-000"
    http_status = 500


class UseCaseError(ApplicationError):
    """Error during use case execution."""

    code = "TWZ-APP-001"
    http_status = 500


class AuthenticationError(ApplicationError):
    """Authentication failed."""

    code = "TWZ-APP-002"
    http_status = 401


class AuthorizationError(ApplicationError):
    """User not authorized for this action."""

    code = "TWZ-APP-003"
    http_status = 403


class RateLimitError(ApplicationError):
    """Rate limit exceeded."""

    code = "TWZ-APP-004"
    http_status = 429

    def __init__(
        self,
        resource: str,
        limit: int,
        reset_seconds: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        message = f"Rate limit exceeded for {resource}: max {limit} requests"
        super().__init__(
            message,
            details={
                "resource": resource,
                "limit": limit,
                "reset_seconds": reset_seconds,
                **(details or {}),
            },
        )


# =============================================================================
# Infrastructure Errors (TWZ-INF-xxx)
# =============================================================================


class InfrastructureError(TawizaError):
    """Base for infrastructure layer errors."""

    code = "TWZ-INF-000"
    http_status = 503


class DatabaseError(InfrastructureError):
    """Database operation failed."""

    code = "TWZ-INF-001"
    http_status = 503


class ExternalServiceError(InfrastructureError):
    """External service call failed."""

    code = "TWZ-INF-002"
    http_status = 502

    def __init__(
        self,
        service: str,
        message: str,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        full_message = f"External service '{service}' error: {message}"
        super().__init__(
            full_message,
            details={
                "service": service,
                "status_code": status_code,
                **(details or {}),
            },
        )


class ConnectionError(InfrastructureError):
    """Failed to connect to a service."""

    code = "TWZ-INF-003"
    http_status = 503

    def __init__(
        self,
        service: str,
        host: str | None = None,
        port: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        message = f"Failed to connect to {service}"
        if host:
            message += f" at {host}"
            if port:
                message += f":{port}"
        super().__init__(
            message,
            details={
                "service": service,
                "host": host,
                "port": port,
                **(details or {}),
            },
        )


class TimeoutError(InfrastructureError):
    """Operation timed out."""

    code = "TWZ-INF-004"
    http_status = 504

    def __init__(
        self,
        operation: str,
        timeout_seconds: float,
        details: dict[str, Any] | None = None,
    ):
        message = f"Operation '{operation}' timed out after {timeout_seconds}s"
        super().__init__(
            message,
            details={
                "operation": operation,
                "timeout_seconds": timeout_seconds,
                **(details or {}),
            },
        )


class ConfigurationError(InfrastructureError):
    """Configuration is invalid or missing."""

    code = "TWZ-INF-005"
    http_status = 500

    def __init__(
        self,
        config_key: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        full_message = message or f"Configuration error for '{config_key}'"
        super().__init__(
            full_message,
            details={
                "config_key": config_key,
                **(details or {}),
            },
        )


# =============================================================================
# ML/Agent Errors (TWZ-ML-xxx)
# =============================================================================


class MLError(TawizaError):
    """Base for ML-related errors."""

    code = "TWZ-ML-000"
    http_status = 500


class ModelNotFoundError(MLError):
    """ML model not found or not loaded."""

    code = "TWZ-ML-001"
    http_status = 404


class ModelLoadError(MLError):
    """Failed to load ML model."""

    code = "TWZ-ML-002"
    http_status = 503


class InferenceError(MLError):
    """Inference/prediction failed."""

    code = "TWZ-ML-003"
    http_status = 500


class TrainingError(MLError):
    """Model training failed."""

    code = "TWZ-ML-004"
    http_status = 500


class AgentError(MLError):
    """Agent execution error."""

    code = "TWZ-ML-005"
    http_status = 500

    def __init__(
        self,
        agent_name: str,
        message: str,
        task_id: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        full_message = f"Agent '{agent_name}' error: {message}"
        super().__init__(
            full_message,
            details={
                "agent_name": agent_name,
                "task_id": task_id,
                **(details or {}),
            },
        )


class AgentTimeoutError(AgentError):
    """Agent task timed out."""

    code = "TWZ-ML-006"
    http_status = 504


# =============================================================================
# API Errors (TWZ-API-xxx)
# =============================================================================


class APIError(TawizaError):
    """Base for API layer errors."""

    code = "TWZ-API-000"
    http_status = 400


class BadRequestError(APIError):
    """Invalid request format or parameters."""

    code = "TWZ-API-001"
    http_status = 400


class NotFoundError(APIError):
    """Resource not found."""

    code = "TWZ-API-002"
    http_status = 404


class MethodNotAllowedError(APIError):
    """HTTP method not allowed."""

    code = "TWZ-API-003"
    http_status = 405


# =============================================================================
# Utility functions
# =============================================================================


def error_to_response(error: TawizaError) -> dict[str, Any]:
    """Convert exception to API response format."""
    return {
        "success": False,
        "error": error.to_dict(),
    }


def wrap_error(
    exception: Exception,
    error_class: type = InfrastructureError,
    message: str | None = None,
) -> TawizaError:
    """Wrap a generic exception into an Tawiza error.

    Args:
        exception: Original exception
        error_class: Tawiza error class to use
        message: Optional custom message

    Returns:
        Wrapped Tawiza error
    """
    return error_class(
        message=message or str(exception),
        details={"original_error": type(exception).__name__},
    )
