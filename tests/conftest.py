"""
Pytest configuration and fixtures for Tawiza-V2 tests.

This module provides shared fixtures and test configuration for:
- Async test client
- Database fixtures
- MinIO storage fixtures
- Service mocks
- Test data generators
"""

import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from minio import Minio

# ═══════════════════════════════════════════════════════════════════════════════
# LANGFUSE MOCK (autouse - prevents network calls during tests)
# ═══════════════════════════════════════════════════════════════════════════════

# Disable Langfuse BEFORE any imports (module-level)
os.environ["LANGFUSE_ENABLED"] = "false"


@pytest.fixture(autouse=True)
def mock_langfuse_calls(monkeypatch):
    """
    Mock Langfuse at runtime to prevent network calls during tests.

    Uses monkeypatch to ensure clean teardown per test.
    LANGFUSE_ENABLED=false is set at module level above.
    """
    # Patch the instrumentor module's LANGFUSE_AVAILABLE flag
    try:
        import src.infrastructure.agents.tajine.telemetry.instrumentor as instrumentor

        monkeypatch.setattr(instrumentor, "LANGFUSE_AVAILABLE", False)
        monkeypatch.setattr(instrumentor, "langfuse_observe", None)
        monkeypatch.setattr(instrumentor, "langfuse_context", None)
    except ImportError:
        pass  # Module not yet imported, env var will handle it

    # Also patch langfuse.Langfuse directly if it exists
    try:
        import langfuse

        mock_client = MagicMock()
        mock_client.flush = MagicMock()
        mock_client.shutdown = MagicMock()
        monkeypatch.setattr(langfuse, "Langfuse", MagicMock(return_value=mock_client))
    except ImportError:
        pass


from src.infrastructure.config.settings import get_settings
from src.infrastructure.storage.minio_adapter import MinIOStorageAdapter
from src.infrastructure.storage.versioning_service import ModelVersioningService

# Test configuration
TEST_TIMEOUT = 300  # 5 minutes for integration tests
TEST_ANNOTATION_DATA = Path(__file__).parent / "fixtures" / "test_annotations.json"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def settings():
    """Get test settings."""
    os.environ["APP_ENV"] = "testing"
    return get_settings()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    """Create async HTTP client for testing FastAPI app."""
    from src.interfaces.api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def minio_client(settings) -> Generator[Minio]:
    """Create MinIO client for tests."""
    client = Minio(
        endpoint=settings.minio.endpoint,
        access_key=settings.minio.access_key,
        secret_key=settings.minio.secret_key,
        secure=settings.minio.secure,
    )
    yield client


@pytest_asyncio.fixture
async def storage_adapter(settings) -> AsyncGenerator[MinIOStorageAdapter]:
    """Create MinIO storage adapter for tests."""
    adapter = MinIOStorageAdapter(
        endpoint=settings.minio.endpoint,
        access_key=settings.minio.access_key,
        secret_key=settings.minio.secret_key,
        bucket_name=f"test-{uuid4().hex[:8]}",  # Unique test bucket
        secure=settings.minio.secure,
    )

    # Initialize bucket
    await adapter.initialize_bucket()
    yield adapter

    # Cleanup: Delete all objects in test bucket
    try:
        objects = adapter.client.list_objects(adapter.bucket_name, recursive=True)
        for obj in objects:
            adapter.client.remove_object(adapter.bucket_name, obj.object_name)

        # Delete bucket
        adapter.client.remove_bucket(adapter.bucket_name)
    except Exception as e:
        print(f"Cleanup warning: {e}")


@pytest_asyncio.fixture
async def versioning_service(
    storage_adapter: MinIOStorageAdapter,
) -> ModelVersioningService:
    """Create versioning service for tests."""
    return ModelVersioningService(storage_service=storage_adapter)


@pytest.fixture
def sample_modelfile() -> str:
    """Generate a sample Ollama Modelfile for testing."""
    return """FROM qwen3-coder:30b

PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER num_ctx 4096

SYSTEM You are a helpful AI assistant fine-tuned for code review.

MESSAGE user What is your purpose?
MESSAGE assistant I help review code and provide suggestions for improvement.

MESSAGE user Can you check this Python function?
MESSAGE assistant I'd be happy to review your Python code. Please share it.
"""


@pytest.fixture
def sample_annotations() -> list[dict]:
    """Generate sample Label Studio annotations for testing."""
    return [
        {
            "id": 1,
            "data": {
                "text": "def add(a, b):\n    return a + b",
                "language": "python",
            },
            "annotations": [
                {
                    "result": [
                        {
                            "value": {
                                "text": "Simple addition function",
                                "labels": ["function"],
                            },
                            "from_name": "label",
                            "to_name": "text",
                            "type": "labels",
                        }
                    ],
                    "was_cancelled": False,
                    "ground_truth": False,
                }
            ],
        },
        {
            "id": 2,
            "data": {
                "text": "class User:\n    def __init__(self, name):\n        self.name = name",
                "language": "python",
            },
            "annotations": [
                {
                    "result": [
                        {
                            "value": {
                                "text": "User class definition",
                                "labels": ["class"],
                            },
                            "from_name": "label",
                            "to_name": "text",
                            "type": "labels",
                        }
                    ],
                    "was_cancelled": False,
                    "ground_truth": False,
                }
            ],
        },
        {
            "id": 3,
            "data": {
                "text": "async def fetch_data(url):\n    async with httpx.AsyncClient() as client:\n        return await client.get(url)",
                "language": "python",
            },
            "annotations": [
                {
                    "result": [
                        {
                            "value": {
                                "text": "Async HTTP request function",
                                "labels": ["async", "function"],
                            },
                            "from_name": "label",
                            "to_name": "text",
                            "type": "labels",
                        }
                    ],
                    "was_cancelled": False,
                    "ground_truth": False,
                }
            ],
        },
    ]


@pytest.fixture
def sample_training_metadata() -> dict:
    """Generate sample training metadata."""
    return {
        "mlflow_run_id": f"test-run-{uuid4().hex[:8]}",
        "mlflow_experiment_id": "ollama-fine-tuning",
        "accuracy": 0.92,
        "precision": 0.89,
        "recall": 0.94,
        "f1_score": 0.915,
        "loss": 0.124,
        "training_examples": 150,
        "task_type": "classification",
        "hyperparameters": {
            "learning_rate": 0.001,
            "batch_size": 32,
            "epochs": 5,
        },
        "tags": {
            "framework": "ollama",
            "test": "true",
        },
        "description": "Test model version",
    }


@pytest.fixture
def test_model_name() -> str:
    """Generate unique test model name."""
    return f"test-model-{uuid4().hex[:8]}"


# Markers for test categorization
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests (fast, isolated)")
    config.addinivalue_line("markers", "integration: Integration tests (require services)")
    config.addinivalue_line("markers", "e2e: End-to-end tests (full system)")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "minio: Tests requiring MinIO")
    config.addinivalue_line("markers", "ollama: Tests requiring Ollama")
    config.addinivalue_line("markers", "mlflow: Tests requiring MLflow")


# Async test configuration
def pytest_collection_modifyitems(config, items):
    """Add markers to tests based on their location."""
    for item in items:
        # Add integration marker to integration tests
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)

        # Add performance marker to performance tests
        if "performance" in str(item.fspath):
            item.add_marker(pytest.mark.slow)

        # Add security marker to security tests
        if "security" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
