"""Tests for error handler middleware."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from src.domain.exceptions import (
    DatabaseError,
    EntityNotFoundError,
    InfrastructureError,
    TawizaError,
    ValidationError,
)
from src.interfaces.api.middleware.error_handler import (
    ErrorHandlerMiddleware,
    register_exception_handlers,
)


class TestErrorHandlerMiddleware:
    """Test suite for ErrorHandlerMiddleware."""

    def setup_method(self):
        """Set up test fixtures."""
        self.app = FastAPI()
        self.app.add_middleware(ErrorHandlerMiddleware)

        @self.app.get("/success")
        async def success_endpoint():
            return {"message": "success"}

        @self.app.get("/domain-error")
        async def domain_error_endpoint():
            raise EntityNotFoundError("Model", "model-123")

        @self.app.get("/validation-error")
        async def validation_error_endpoint():
            raise ValidationError("Invalid input", {"field": "name"})

        @self.app.get("/infrastructure-error")
        async def infrastructure_error_endpoint():
            raise InfrastructureError("Database connection failed")

        @self.app.get("/unknown-error")
        async def unknown_error_endpoint():
            raise RuntimeError("Something went wrong")

        self.client = TestClient(self.app)

    def test_successful_request_passes_through(self):
        """Successful requests should pass through middleware unchanged."""
        response = self.client.get("/success")

        assert response.status_code == 200
        assert response.json() == {"message": "success"}

    def test_entity_not_found_returns_404(self):
        """EntityNotFoundError should return 404 with structured response."""
        response = self.client.get("/domain-error")

        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert "error" in data
        assert "Model" in data["error"]["message"]

    def test_validation_error_returns_422(self):
        """ValidationError should return 422 with details."""
        response = self.client.get("/validation-error")

        assert response.status_code == 422  # ValidationError has 422 status
        data = response.json()
        assert data["success"] is False
        assert data["error"]["message"] == "Invalid input"

    def test_infrastructure_error_returns_503(self):
        """InfrastructureError should return 503."""
        response = self.client.get("/infrastructure-error")

        assert response.status_code == 503  # InfrastructureError has 503 status
        data = response.json()
        assert data["success"] is False

    def test_unknown_error_wrapped_and_returns_503(self):
        """Unknown errors should be wrapped in InfrastructureError and return 503."""
        response = self.client.get("/unknown-error")

        assert response.status_code == 503  # Wrapped in InfrastructureError
        data = response.json()
        assert data["success"] is False
        assert "request_id" in data

    def test_response_includes_request_id(self):
        """Error responses should include X-Request-ID header."""
        response = self.client.get("/domain-error")

        assert "X-Request-ID" in response.headers


class TestRegisterExceptionHandlers:
    """Test suite for register_exception_handlers function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.app = FastAPI()
        register_exception_handlers(self.app)

        @self.app.get("/entity-not-found")
        async def entity_not_found_endpoint():
            raise EntityNotFoundError("Dataset", "ds-456")

        @self.app.get("/database-error")
        async def database_error_endpoint():
            raise DatabaseError("Connection timeout")

        @self.app.get("/general-exception")
        async def general_exception_endpoint():
            # This triggers the general exception handler
            def inner():
                raise ValueError("Something unexpected")

            inner()

        self.client = TestClient(self.app, raise_server_exceptions=False)

    def test_tawiza_error_handler(self):
        """TawizaError should be handled with appropriate status code."""
        response = self.client.get("/entity-not-found")

        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert "error" in data
        assert "code" in data["error"]

    def test_database_error_handler(self):
        """DatabaseError should return 503."""
        response = self.client.get("/database-error")

        assert response.status_code == 503
        data = response.json()
        assert data["success"] is False

    def test_general_exception_handler(self):
        """General exceptions should return 500 with generic message."""
        response = self.client.get("/general-exception")

        assert response.status_code == 500
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "TWZ-INF-000"


class TestRequestValidationErrorHandling:
    """Test suite for Pydantic validation errors."""

    def setup_method(self):
        """Set up test fixtures."""
        self.app = FastAPI()
        register_exception_handlers(self.app)

        class UserCreate(BaseModel):
            name: str = Field(..., min_length=2)
            email: str
            age: int = Field(..., ge=0)

        @self.app.post("/users")
        async def create_user(user: UserCreate):
            return user.model_dump()

        self.client = TestClient(self.app)

    def test_validation_error_returns_422(self):
        """Invalid request body should return 422 with error details."""
        response = self.client.post("/users", json={"name": "A", "email": "test", "age": -5})

        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "TWZ-API-001"
        assert "errors" in data["error"]["details"]

    def test_missing_fields_returns_422(self):
        """Missing required fields should return 422."""
        response = self.client.post("/users", json={})

        assert response.status_code == 422
        data = response.json()
        assert len(data["error"]["details"]["errors"]) > 0


class TestHTTPExceptionHandling:
    """Test suite for HTTP exception handling."""

    def setup_method(self):
        """Set up test fixtures."""
        from fastapi import HTTPException

        self.app = FastAPI()
        register_exception_handlers(self.app)

        @self.app.get("/http-exception")
        async def http_exception_endpoint():
            raise HTTPException(status_code=403, detail="Access denied")

        self.client = TestClient(self.app)

    def test_http_exception_returns_correct_status(self):
        """HTTPException should return the specified status code."""
        response = self.client.get("/http-exception")

        assert response.status_code == 403
        data = response.json()
        assert data["success"] is False
        assert data["error"]["message"] == "Access denied"
        assert data["error"]["code"] == "TWZ-API-403"


class TestErrorResponseFormat:
    """Test suite for error response format consistency."""

    def setup_method(self):
        """Set up test fixtures."""
        self.app = FastAPI()
        register_exception_handlers(self.app)

        @self.app.get("/error-with-details")
        async def error_with_details():
            error = ValidationError(
                "Invalid configuration",
                details={
                    "field": "batch_size",
                    "value": -1,
                    "constraint": "must be positive",
                },
            )
            raise error

        self.client = TestClient(self.app)

    def test_error_response_structure(self):
        """Error response should have consistent structure."""
        response = self.client.get("/error-with-details")

        data = response.json()

        # Required top-level fields
        assert "success" in data
        assert "error" in data
        assert "request_id" in data

        # Error object structure
        error = data["error"]
        assert "code" in error
        assert "message" in error
        assert "details" in error

    def test_error_details_preserved(self):
        """Error details should be preserved in response."""
        response = self.client.get("/error-with-details")

        data = response.json()
        details = data["error"]["details"]

        assert details["field"] == "batch_size"
        assert details["value"] == -1
