"""Tests for Datasets API router.

This module tests:
- List datasets endpoint with pagination
- Get dataset by ID endpoint
- Health check endpoint
- Error handling
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.interfaces.api.routers.datasets import (
    DatasetResponse,
    DatasetsListResponse,
    router,
)


class TestPydanticModels:
    """Test suite for Pydantic response models."""

    def test_dataset_response_minimal(self):
        """DatasetResponse should work with minimal fields."""
        response = DatasetResponse(
            id="123",
            name="Test Dataset",
            created_at="2025-01-01T00:00:00",
            updated_at="2025-01-01T00:00:00",
        )
        assert response.id == "123"
        assert response.name == "Test Dataset"
        assert response.description is None
        assert response.size == 0
        assert response.format == "unknown"

    def test_dataset_response_full(self):
        """DatasetResponse should accept all fields."""
        response = DatasetResponse(
            id="456",
            name="Full Dataset",
            description="A complete dataset",
            size=10000,
            format="parquet",
            num_samples=5000,
            created_at="2025-06-01T12:00:00",
            updated_at="2025-06-02T14:30:00",
            status="ready",
        )
        assert response.description == "A complete dataset"
        assert response.size == 10000
        assert response.format == "parquet"
        assert response.num_samples == 5000
        assert response.status == "ready"

    def test_datasets_list_response(self):
        """DatasetsListResponse should contain pagination info."""
        response = DatasetsListResponse(
            datasets=[
                DatasetResponse(
                    id="1",
                    name="Dataset 1",
                    created_at="2025-01-01T00:00:00",
                    updated_at="2025-01-01T00:00:00",
                ),
            ],
            total=100,
            page=2,
            page_size=10,
        )
        assert len(response.datasets) == 1
        assert response.total == 100
        assert response.page == 2
        assert response.page_size == 10


class TestListDatasetsEndpoint:
    """Test suite for list datasets endpoint."""

    @pytest.fixture
    def mock_dataset(self):
        """Create a mock dataset entity."""
        dataset = MagicMock()
        dataset.id = uuid4()
        dataset.name = "Test Dataset"
        dataset.created_at = datetime(2025, 1, 1, 0, 0, 0)
        dataset.updated_at = datetime(2025, 1, 2, 0, 0, 0)
        dataset.status = MagicMock()
        dataset.status.value = "ready"
        dataset.metadata = MagicMock()
        dataset.metadata.source = "Test source"
        dataset.metadata.format = "csv"
        dataset.metadata.size = 1000
        return dataset

    @pytest.fixture
    def mock_repository(self, mock_dataset):
        """Create a mock dataset repository."""
        repo = MagicMock()
        repo.get_all = AsyncMock(return_value=[mock_dataset])
        repo.count = AsyncMock(return_value=1)
        return repo

    @pytest.fixture
    def mock_container(self, mock_repository):
        """Create a mock DI container."""
        container = MagicMock()
        container.dataset_repository = MagicMock(return_value=mock_repository)
        return container

    @pytest.fixture
    def test_client(self, mock_container):
        """Create FastAPI test client with mocked container."""
        app = FastAPI()
        app.include_router(router, prefix="/datasets")

        with patch(
            "src.interfaces.api.routers.datasets.get_container", return_value=mock_container
        ):
            yield TestClient(app)

    def test_list_datasets_success(self, mock_container):
        """GET /datasets should return list of datasets."""
        app = FastAPI()
        app.include_router(router, prefix="/datasets")

        with patch(
            "src.interfaces.api.routers.datasets.get_container", return_value=mock_container
        ):
            client = TestClient(app)
            response = client.get("/datasets/")

        assert response.status_code == 200
        data = response.json()
        assert "datasets" in data
        assert data["total"] == 1
        assert data["page"] == 1
        assert data["page_size"] == 10
        assert len(data["datasets"]) == 1
        assert data["datasets"][0]["name"] == "Test Dataset"

    def test_list_datasets_pagination(self, mock_container, mock_repository):
        """GET /datasets should support pagination."""
        app = FastAPI()
        app.include_router(router, prefix="/datasets")

        with patch(
            "src.interfaces.api.routers.datasets.get_container", return_value=mock_container
        ):
            client = TestClient(app)
            response = client.get("/datasets/?page=2&page_size=20")

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 20

        # Verify repository was called with correct offset
        mock_repository.get_all.assert_called_once_with(skip=20, limit=20)

    def test_list_datasets_without_trailing_slash(self, mock_container):
        """GET /datasets should work without trailing slash."""
        app = FastAPI()
        app.include_router(router, prefix="/datasets")

        with patch(
            "src.interfaces.api.routers.datasets.get_container", return_value=mock_container
        ):
            client = TestClient(app)
            response = client.get("/datasets")

        assert response.status_code == 200

    def test_list_datasets_empty(self, mock_container, mock_repository):
        """GET /datasets should handle empty list."""
        mock_repository.get_all = AsyncMock(return_value=[])
        mock_repository.count = AsyncMock(return_value=0)

        app = FastAPI()
        app.include_router(router, prefix="/datasets")

        with patch(
            "src.interfaces.api.routers.datasets.get_container", return_value=mock_container
        ):
            client = TestClient(app)
            response = client.get("/datasets/")

        assert response.status_code == 200
        data = response.json()
        assert data["datasets"] == []
        assert data["total"] == 0

    def test_list_datasets_without_metadata(self, mock_container, mock_repository):
        """GET /datasets should handle datasets without metadata."""
        dataset = MagicMock()
        dataset.id = uuid4()
        dataset.name = "No Metadata Dataset"
        dataset.created_at = datetime(2025, 1, 1)
        dataset.updated_at = datetime(2025, 1, 1)
        dataset.status = MagicMock()
        dataset.status.value = "pending"
        dataset.metadata = None  # No metadata

        mock_repository.get_all = AsyncMock(return_value=[dataset])

        app = FastAPI()
        app.include_router(router, prefix="/datasets")

        with patch(
            "src.interfaces.api.routers.datasets.get_container", return_value=mock_container
        ):
            client = TestClient(app)
            response = client.get("/datasets/")

        assert response.status_code == 200
        data = response.json()
        assert data["datasets"][0]["format"] == "unknown"
        assert data["datasets"][0]["description"] is None

    def test_list_datasets_infrastructure_error(self, mock_container, mock_repository):
        """GET /datasets should handle infrastructure errors."""
        from src.domain.exceptions import InfrastructureError

        mock_repository.get_all = AsyncMock(
            side_effect=InfrastructureError("Database connection failed")
        )

        app = FastAPI()
        app.include_router(router, prefix="/datasets")

        with patch(
            "src.interfaces.api.routers.datasets.get_container", return_value=mock_container
        ):
            client = TestClient(app)
            response = client.get("/datasets/")

        assert response.status_code == 500
        assert "Failed to list datasets" in response.json()["detail"]

    def test_list_datasets_unexpected_error(self, mock_container, mock_repository):
        """GET /datasets should handle unexpected errors."""
        mock_repository.get_all = AsyncMock(side_effect=RuntimeError("Unexpected error"))

        app = FastAPI()
        app.include_router(router, prefix="/datasets")

        with patch(
            "src.interfaces.api.routers.datasets.get_container", return_value=mock_container
        ):
            client = TestClient(app)
            response = client.get("/datasets/")

        assert response.status_code == 500

    def test_list_datasets_page_validation(self, mock_container):
        """GET /datasets should validate page parameter."""
        app = FastAPI()
        app.include_router(router, prefix="/datasets")

        with patch(
            "src.interfaces.api.routers.datasets.get_container", return_value=mock_container
        ):
            client = TestClient(app)
            response = client.get("/datasets/?page=0")  # Invalid - must be >= 1

        assert response.status_code == 422  # Validation error

    def test_list_datasets_page_size_validation(self, mock_container):
        """GET /datasets should validate page_size parameter."""
        app = FastAPI()
        app.include_router(router, prefix="/datasets")

        with patch(
            "src.interfaces.api.routers.datasets.get_container", return_value=mock_container
        ):
            client = TestClient(app)
            response = client.get("/datasets/?page_size=101")  # Invalid - max is 100

        assert response.status_code == 422  # Validation error


class TestGetDatasetEndpoint:
    """Test suite for get dataset by ID endpoint."""

    @pytest.fixture
    def mock_dataset(self):
        """Create a mock dataset entity."""
        dataset = MagicMock()
        dataset.id = uuid4()
        dataset.name = "Specific Dataset"
        dataset.created_at = datetime(2025, 3, 15, 10, 30, 0)
        dataset.updated_at = datetime(2025, 3, 16, 14, 0, 0)
        dataset.status = MagicMock()
        dataset.status.value = "annotated"
        dataset.metadata = MagicMock()
        dataset.metadata.source = "API Upload"
        dataset.metadata.format = "parquet"
        dataset.metadata.size = 50000
        return dataset

    @pytest.fixture
    def mock_repository(self, mock_dataset):
        """Create a mock dataset repository."""
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=mock_dataset)
        return repo

    @pytest.fixture
    def mock_container(self, mock_repository):
        """Create a mock DI container."""
        container = MagicMock()
        container.dataset_repository = MagicMock(return_value=mock_repository)
        return container

    def test_get_dataset_success(self, mock_container, mock_dataset):
        """GET /datasets/{id} should return dataset."""
        app = FastAPI()
        app.include_router(router, prefix="/datasets")

        dataset_id = str(mock_dataset.id)

        with patch(
            "src.interfaces.api.routers.datasets.get_container", return_value=mock_container
        ):
            client = TestClient(app)
            response = client.get(f"/datasets/{dataset_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == dataset_id
        assert data["name"] == "Specific Dataset"
        assert data["format"] == "parquet"
        assert data["status"] == "annotated"

    def test_get_dataset_not_found(self, mock_container, mock_repository):
        """GET /datasets/{id} should return 404 for non-existent dataset."""
        mock_repository.get_by_id = AsyncMock(return_value=None)

        app = FastAPI()
        app.include_router(router, prefix="/datasets")

        dataset_id = str(uuid4())

        with patch(
            "src.interfaces.api.routers.datasets.get_container", return_value=mock_container
        ):
            client = TestClient(app)
            response = client.get(f"/datasets/{dataset_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_get_dataset_invalid_uuid(self, mock_container):
        """GET /datasets/{id} should return 400 for invalid UUID."""
        app = FastAPI()
        app.include_router(router, prefix="/datasets")

        with patch(
            "src.interfaces.api.routers.datasets.get_container", return_value=mock_container
        ):
            client = TestClient(app)
            response = client.get("/datasets/not-a-valid-uuid")

        assert response.status_code == 400
        assert "Invalid dataset ID format" in response.json()["detail"]

    def test_get_dataset_without_metadata(self, mock_container, mock_repository):
        """GET /datasets/{id} should handle dataset without metadata."""
        dataset = MagicMock()
        dataset.id = uuid4()
        dataset.name = "No Metadata"
        dataset.created_at = datetime(2025, 1, 1)
        dataset.updated_at = datetime(2025, 1, 1)
        dataset.status = MagicMock()
        dataset.status.value = "pending"
        dataset.metadata = None

        mock_repository.get_by_id = AsyncMock(return_value=dataset)

        app = FastAPI()
        app.include_router(router, prefix="/datasets")

        with patch(
            "src.interfaces.api.routers.datasets.get_container", return_value=mock_container
        ):
            client = TestClient(app)
            response = client.get(f"/datasets/{dataset.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "unknown"
        assert data["description"] is None

    def test_get_dataset_error(self, mock_container, mock_repository):
        """GET /datasets/{id} should handle repository errors."""
        mock_repository.get_by_id = AsyncMock(side_effect=RuntimeError("Database error"))

        app = FastAPI()
        app.include_router(router, prefix="/datasets")

        dataset_id = str(uuid4())

        with patch(
            "src.interfaces.api.routers.datasets.get_container", return_value=mock_container
        ):
            client = TestClient(app)
            response = client.get(f"/datasets/{dataset_id}")

        assert response.status_code == 500
        assert "Failed to fetch dataset" in response.json()["detail"]


class TestHealthCheckEndpoint:
    """Test suite for health check endpoint.

    The /health endpoint is correctly placed before /{dataset_id}
    ensuring static routes are matched before parametric routes.
    """

    def test_health_check_works(self):
        """GET /datasets/health should return healthy status.

        The /health route is now correctly defined before /{dataset_id}
        so static routes are matched before parametric routes.
        """
        app = FastAPI()
        app.include_router(router, prefix="/datasets")

        client = TestClient(app)
        response = client.get("/datasets/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "datasets"


class TestPaginationCalculation:
    """Test suite for pagination logic."""

    def test_page_1_offset_calculation(self):
        """Page 1 should have offset 0."""
        page = 1
        page_size = 10
        skip = (page - 1) * page_size
        assert skip == 0

    def test_page_2_offset_calculation(self):
        """Page 2 should have offset equal to page_size."""
        page = 2
        page_size = 10
        skip = (page - 1) * page_size
        assert skip == 10

    def test_page_5_with_custom_size(self):
        """Page 5 with page_size 25 should have offset 100."""
        page = 5
        page_size = 25
        skip = (page - 1) * page_size
        assert skip == 100
