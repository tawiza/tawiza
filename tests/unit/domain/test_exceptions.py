"""Tests for domain exceptions.

This module tests the domain exception hierarchy including:
- Base TawizaError and its subclasses
- Error code formats
- HTTP status codes
- Utility functions (error_to_response, wrap_error)
"""

import pytest

from src.domain.exceptions import (
    AgentError,
    AgentTimeoutError,
    # API errors
    APIError,
    # Application errors
    ApplicationError,
    AuthenticationError,
    AuthorizationError,
    BadRequestError,
    BusinessRuleViolationError,
    ConfigurationError,
    ConnectionError,
    DatabaseError,
    # Domain errors
    DomainError,
    EntityAlreadyExistsError,
    EntityNotFoundError,
    ExternalServiceError,
    InferenceError,
    # Infrastructure errors
    InfrastructureError,
    InvalidStateError,
    MethodNotAllowedError,
    # ML errors
    MLError,
    ModelLoadError,
    ModelNotFoundError,
    # Base
    TawizaError,
    NotFoundError,
    RateLimitError,
    TimeoutError,
    TrainingError,
    UseCaseError,
    ValidationError,
    # Utilities
    error_to_response,
    wrap_error,
)


class TestTawizaError:
    """Tests for base TawizaError."""

    def test_basic_creation(self):
        """TawizaError should be created with message."""
        error = TawizaError("Something went wrong")

        assert error.message == "Something went wrong"
        assert error.code == "TWZ-000-000"
        assert error.http_status == 500
        assert error.details == {}

    def test_creation_with_custom_code(self):
        """TawizaError should accept custom error code."""
        error = TawizaError("Error", code="CUSTOM-001")

        assert error.code == "CUSTOM-001"

    def test_creation_with_details(self):
        """TawizaError should accept details dictionary."""
        error = TawizaError("Error", details={"key": "value", "count": 42})

        assert error.details["key"] == "value"
        assert error.details["count"] == 42

    def test_to_dict(self):
        """TawizaError should convert to dictionary."""
        error = TawizaError("Test error", code="TEST-001", details={"field": "name"})

        result = error.to_dict()

        assert result["error"] is True
        assert result["code"] == "TEST-001"
        assert result["message"] == "Test error"
        assert result["details"]["field"] == "name"

    def test_str_representation(self):
        """TawizaError should have readable string representation."""
        error = TawizaError("Something failed", code="ERR-123")

        assert str(error) == "[ERR-123] Something failed"

    def test_is_exception(self):
        """TawizaError should be a valid Exception."""
        error = TawizaError("Test")

        assert isinstance(error, Exception)
        with pytest.raises(TawizaError):
            raise error


class TestDomainErrors:
    """Tests for domain layer errors."""

    def test_domain_error_base(self):
        """DomainError should have correct defaults."""
        error = DomainError("Domain error")

        assert error.code == "TWZ-DOM-000"
        assert error.http_status == 400

    def test_entity_not_found_error(self):
        """EntityNotFoundError should format message correctly."""
        error = EntityNotFoundError("Model", "model-123")

        assert error.code == "TWZ-DOM-001"
        assert error.http_status == 404
        assert "Model" in error.message
        assert "model-123" in error.message
        assert error.details["entity_type"] == "Model"
        assert error.details["entity_id"] == "model-123"

    def test_entity_already_exists_error(self):
        """EntityAlreadyExistsError should format message correctly."""
        error = EntityAlreadyExistsError("User", "john@example.com")

        assert error.code == "TWZ-DOM-002"
        assert error.http_status == 409
        assert "User" in error.message
        assert "john@example.com" in error.message

    def test_validation_error(self):
        """ValidationError should include field information."""
        error = ValidationError("Invalid email format", field="email")

        assert error.code == "TWZ-DOM-003"
        assert error.http_status == 422
        assert error.details["field"] == "email"

    def test_validation_error_with_extra_details(self):
        """ValidationError should merge extra details."""
        error = ValidationError(
            "Value out of range",
            field="age",
            details={"min": 0, "max": 150},
        )

        assert error.details["field"] == "age"
        assert error.details["min"] == 0
        assert error.details["max"] == 150

    def test_invalid_state_error(self):
        """InvalidStateError should include state transition info."""
        error = InvalidStateError(
            entity_type="Model",
            current_state="draft",
            required_state="trained",
            operation="deploy",
        )

        assert error.code == "TWZ-DOM-004"
        assert error.http_status == 409
        assert "deploy" in error.message
        assert "draft" in error.message
        assert "trained" in error.message

    def test_business_rule_violation_error(self):
        """BusinessRuleViolationError should include rule name."""
        error = BusinessRuleViolationError(
            rule="MAX_DATASETS_PER_USER",
            message="You have reached the maximum number of datasets",
        )

        assert error.code == "TWZ-DOM-005"
        assert error.details["rule"] == "MAX_DATASETS_PER_USER"


class TestApplicationErrors:
    """Tests for application layer errors."""

    def test_application_error_base(self):
        """ApplicationError should have correct defaults."""
        error = ApplicationError("Application error")

        assert error.code == "TWZ-APP-000"
        assert error.http_status == 500

    def test_use_case_error(self):
        """UseCaseError should have correct status code."""
        error = UseCaseError("Use case failed")

        assert error.code == "TWZ-APP-001"
        assert error.http_status == 500

    def test_authentication_error(self):
        """AuthenticationError should have 401 status."""
        error = AuthenticationError("Invalid credentials")

        assert error.code == "TWZ-APP-002"
        assert error.http_status == 401

    def test_authorization_error(self):
        """AuthorizationError should have 403 status."""
        error = AuthorizationError("Access denied")

        assert error.code == "TWZ-APP-003"
        assert error.http_status == 403

    def test_rate_limit_error(self):
        """RateLimitError should include limit information."""
        error = RateLimitError(
            resource="api/predictions",
            limit=100,
            reset_seconds=3600,
        )

        assert error.code == "TWZ-APP-004"
        assert error.http_status == 429
        assert error.details["resource"] == "api/predictions"
        assert error.details["limit"] == 100
        assert error.details["reset_seconds"] == 3600


class TestInfrastructureErrors:
    """Tests for infrastructure layer errors."""

    def test_infrastructure_error_base(self):
        """InfrastructureError should have correct defaults."""
        error = InfrastructureError("Infrastructure error")

        assert error.code == "TWZ-INF-000"
        assert error.http_status == 503

    def test_database_error(self):
        """DatabaseError should have 503 status."""
        error = DatabaseError("Connection pool exhausted")

        assert error.code == "TWZ-INF-001"
        assert error.http_status == 503

    def test_external_service_error(self):
        """ExternalServiceError should include service name."""
        error = ExternalServiceError(
            service="MLflow",
            message="Connection refused",
            status_code=502,
        )

        assert error.code == "TWZ-INF-002"
        assert error.http_status == 502
        assert "MLflow" in error.message
        assert error.details["service"] == "MLflow"
        assert error.details["status_code"] == 502

    def test_connection_error(self):
        """ConnectionError should include connection details."""
        error = ConnectionError(
            service="Redis",
            host="localhost",
            port=6379,
        )

        assert error.code == "TWZ-INF-003"
        assert error.http_status == 503
        assert "Redis" in error.message
        assert "localhost" in error.message
        assert error.details["port"] == 6379

    def test_connection_error_minimal(self):
        """ConnectionError should work with just service name."""
        error = ConnectionError(service="Database")

        assert "Database" in error.message
        assert error.details["host"] is None

    def test_timeout_error(self):
        """TimeoutError should include timeout details."""
        error = TimeoutError(
            operation="model_inference",
            timeout_seconds=30.0,
        )

        assert error.code == "TWZ-INF-004"
        assert error.http_status == 504
        assert "model_inference" in error.message
        assert "30" in error.message

    def test_configuration_error(self):
        """ConfigurationError should include config key."""
        error = ConfigurationError(
            config_key="MLFLOW_TRACKING_URI",
            message="Missing required configuration",
        )

        assert error.code == "TWZ-INF-005"
        assert error.http_status == 500
        assert error.details["config_key"] == "MLFLOW_TRACKING_URI"

    def test_configuration_error_default_message(self):
        """ConfigurationError should generate default message."""
        error = ConfigurationError(config_key="API_KEY")

        assert "API_KEY" in error.message


class TestMLErrors:
    """Tests for ML-related errors."""

    def test_ml_error_base(self):
        """MLError should have correct defaults."""
        error = MLError("ML error")

        assert error.code == "TWZ-ML-000"
        assert error.http_status == 500

    def test_model_not_found_error(self):
        """ModelNotFoundError should have 404 status."""
        error = ModelNotFoundError("Model 'llama-7b' not loaded")

        assert error.code == "TWZ-ML-001"
        assert error.http_status == 404

    def test_model_load_error(self):
        """ModelLoadError should have 503 status."""
        error = ModelLoadError("Failed to load model weights")

        assert error.code == "TWZ-ML-002"
        assert error.http_status == 503

    def test_inference_error(self):
        """InferenceError should have 500 status."""
        error = InferenceError("Inference failed: CUDA out of memory")

        assert error.code == "TWZ-ML-003"
        assert error.http_status == 500

    def test_training_error(self):
        """TrainingError should have 500 status."""
        error = TrainingError("Training diverged")

        assert error.code == "TWZ-ML-004"
        assert error.http_status == 500

    def test_agent_error(self):
        """AgentError should include agent name."""
        error = AgentError(
            agent_name="DataAnalyst",
            message="Task execution failed",
            task_id="task-123",
        )

        assert error.code == "TWZ-ML-005"
        assert error.http_status == 500
        assert "DataAnalyst" in error.message
        assert error.details["agent_name"] == "DataAnalyst"
        assert error.details["task_id"] == "task-123"

    def test_agent_timeout_error(self):
        """AgentTimeoutError should have 504 status."""
        error = AgentTimeoutError(
            agent_name="BrowserAgent",
            message="Operation timed out",
        )

        assert error.code == "TWZ-ML-006"
        assert error.http_status == 504


class TestAPIErrors:
    """Tests for API layer errors."""

    def test_api_error_base(self):
        """APIError should have correct defaults."""
        error = APIError("API error")

        assert error.code == "TWZ-API-000"
        assert error.http_status == 400

    def test_bad_request_error(self):
        """BadRequestError should have 400 status."""
        error = BadRequestError("Invalid JSON format")

        assert error.code == "TWZ-API-001"
        assert error.http_status == 400

    def test_not_found_error(self):
        """NotFoundError should have 404 status."""
        error = NotFoundError("Endpoint not found")

        assert error.code == "TWZ-API-002"
        assert error.http_status == 404

    def test_method_not_allowed_error(self):
        """MethodNotAllowedError should have 405 status."""
        error = MethodNotAllowedError("POST not allowed on this endpoint")

        assert error.code == "TWZ-API-003"
        assert error.http_status == 405


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_error_to_response(self):
        """error_to_response should create API response format."""
        error = EntityNotFoundError("Model", "model-456")

        response = error_to_response(error)

        assert response["success"] is False
        assert "error" in response
        assert response["error"]["code"] == "TWZ-DOM-001"

    def test_wrap_error_default_class(self):
        """wrap_error should wrap with InfrastructureError by default."""
        original = ValueError("Invalid value")

        wrapped = wrap_error(original)

        assert isinstance(wrapped, InfrastructureError)
        assert "Invalid value" in wrapped.message
        assert wrapped.details["original_error"] == "ValueError"

    def test_wrap_error_custom_class(self):
        """wrap_error should use specified error class."""
        original = Exception("Database timeout")

        wrapped = wrap_error(original, DatabaseError)

        assert isinstance(wrapped, DatabaseError)
        assert wrapped.code == "TWZ-INF-001"

    def test_wrap_error_custom_message(self):
        """wrap_error should use custom message when provided."""
        original = RuntimeError("Internal error")

        wrapped = wrap_error(original, message="Service temporarily unavailable")

        assert wrapped.message == "Service temporarily unavailable"


class TestErrorHierarchy:
    """Tests for error class hierarchy."""

    def test_domain_error_is_tawiza_error(self):
        """DomainError should inherit from TawizaError."""
        error = DomainError("Test")

        assert isinstance(error, TawizaError)
        assert isinstance(error, Exception)

    def test_entity_not_found_is_domain_error(self):
        """EntityNotFoundError should inherit from DomainError."""
        error = EntityNotFoundError("Model", "123")

        assert isinstance(error, DomainError)
        assert isinstance(error, TawizaError)

    def test_infrastructure_error_is_tawiza_error(self):
        """InfrastructureError should inherit from TawizaError."""
        error = InfrastructureError("Test")

        assert isinstance(error, TawizaError)

    def test_ml_error_is_tawiza_error(self):
        """MLError should inherit from TawizaError."""
        error = MLError("Test")

        assert isinstance(error, TawizaError)

    def test_agent_error_is_ml_error(self):
        """AgentError should inherit from MLError."""
        error = AgentError("Agent", "Test")

        assert isinstance(error, MLError)
        assert isinstance(error, TawizaError)


class TestExceptionRaising:
    """Tests for raising and catching exceptions."""

    def test_catch_specific_error(self):
        """Specific errors should be catchable."""
        with pytest.raises(EntityNotFoundError):
            raise EntityNotFoundError("User", "user-999")

    def test_catch_parent_error(self):
        """Child errors should be catchable by parent type."""
        with pytest.raises(DomainError):
            raise EntityNotFoundError("User", "user-999")

    def test_catch_base_error(self):
        """All errors should be catchable by TawizaError."""
        errors = [
            EntityNotFoundError("Model", "123"),
            ValidationError("Invalid"),
            DatabaseError("Connection lost"),
            InferenceError("Failed"),
            BadRequestError("Invalid JSON"),
        ]

        for error in errors:
            with pytest.raises(TawizaError):
                raise error
