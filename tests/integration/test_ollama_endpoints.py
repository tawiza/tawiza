"""
Integration tests for Ollama endpoints.

These tests validate the full Ollama integration pipeline.
"""

import asyncio

import pytest
from httpx import AsyncClient

from src.infrastructure.ml.ollama import OllamaAdapter, OllamaInferenceService


class TestOllamaAdapter:
    """Test OllamaAdapter directly."""

    @pytest.fixture
    async def adapter(self):
        """Create Ollama adapter."""
        return OllamaAdapter(base_url="http://localhost:11434")

    @pytest.mark.asyncio
    async def test_health_check(self, adapter):
        """Test Ollama health check."""
        is_healthy = await adapter.health_check()
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_list_models(self, adapter):
        """Test listing Ollama models."""
        models = await adapter.list_models()
        assert len(models) > 0
        assert any(m["name"] == "qwen3:14b" for m in models)

    @pytest.mark.asyncio
    async def test_generate(self, adapter):
        """Test text generation."""
        response = await adapter.generate(
            model="qwen3:14b", prompt="Say 'test' and nothing else.", temperature=0.1, max_tokens=10
        )
        assert "response" in response
        assert isinstance(response["response"], str)
        assert len(response["response"]) > 0

    @pytest.mark.asyncio
    async def test_chat(self, adapter):
        """Test chat completion."""
        response = await adapter.chat(
            model="qwen3:14b",
            messages=[{"role": "user", "content": "What is 2+2? Answer with just the number."}],
            temperature=0.1,
        )
        assert "message" in response
        assert "content" in response["message"]
        # Should contain "4" somewhere
        assert "4" in response["message"]["content"]


class TestOllamaInferenceService:
    """Test OllamaInferenceService."""

    @pytest.fixture
    async def service(self):
        """Create Ollama inference service."""
        adapter = OllamaAdapter(base_url="http://localhost:11434")
        return OllamaInferenceService(adapter, default_model="qwen3:14b")

    @pytest.mark.asyncio
    async def test_predict_with_prompt(self, service):
        """Test prediction with prompt."""
        result = await service.predict(
            model_id="qwen3:14b",
            input_data={"prompt": "What is AI? Answer in one sentence."},
            parameters={"temperature": 0.5, "max_tokens": 50},
        )
        assert "text" in result
        assert "usage" in result
        assert result["usage"]["total_tokens"] > 0
        assert len(result["text"]) > 0

    @pytest.mark.asyncio
    async def test_predict_with_messages(self, service):
        """Test prediction with chat messages."""
        result = await service.predict(
            model_id="qwen3:14b",
            input_data={"messages": [{"role": "user", "content": "Hello! How are you?"}]},
            parameters={"temperature": 0.7},
        )
        assert "text" in result
        assert len(result["text"]) > 0

    @pytest.mark.asyncio
    async def test_health_check(self, service):
        """Test model health check."""
        is_healthy = await service.health_check("qwen3:14b")
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_get_model_info(self, service):
        """Test getting model information."""
        info = await service.get_model_info("qwen3:14b")
        assert "model_id" in info
        assert "ollama_model" in info
        assert "details" in info


class TestOllamaAPIEndpoints:
    """
    Test Ollama API endpoints.

    Note: These tests require the FastAPI server to be running.
    They are marked as integration tests.
    """

    @pytest.fixture
    def base_url(self):
        """Get base URL for API."""
        return "http://localhost:8000"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_ollama_health_endpoint(self, base_url):
        """Test /api/v1/ollama/health endpoint."""
        async with AsyncClient(base_url=base_url) as client:
            response = await client.get("/api/v1/ollama/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "ollama"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_models_endpoint(self, base_url):
        """Test /api/v1/ollama/models endpoint."""
        async with AsyncClient(base_url=base_url) as client:
            response = await client.get("/api/v1/ollama/models")
            assert response.status_code == 200
            data = response.json()
            assert "models" in data
            assert "total" in data
            assert data["total"] > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_chat_completion_endpoint(self, base_url):
        """Test /api/v1/ollama/chat endpoint."""
        async with AsyncClient(base_url=base_url) as client:
            payload = {
                "messages": [{"role": "user", "content": "What is 10 + 5? Just give the number."}],
                "model": "qwen3:14b",
                "temperature": 0.1,
            }
            response = await client.post("/api/v1/ollama/chat", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "15" in data["message"]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_text_completion_endpoint(self, base_url):
        """Test /api/v1/ollama/completions endpoint."""
        async with AsyncClient(base_url=base_url) as client:
            payload = {
                "prompt": "The capital of France is",
                "model": "qwen3:14b",
                "temperature": 0.1,
                "max_tokens": 10,
            }
            response = await client.post("/api/v1/ollama/completions", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert "text" in data
            assert "Paris" in data["text"]


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom marks."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (may require services)"
    )
