"""Tests for Ollama model auto-detection and fallback."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.infrastructure.llm.ollama_client import OllamaClient


@pytest.fixture
def ollama_client():
    """Create an OllamaClient for testing."""
    return OllamaClient(base_url="http://localhost:11434", model="qwen2.5:7b")


# =============================================================================
# discover_models tests
# =============================================================================


class TestDiscoverModels:
    @pytest.mark.asyncio
    async def test_discover_models_returns_sorted_by_size(self, ollama_client):
        """Models should be returned sorted by size, largest first."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "models": [
                {"name": "nomic-embed-text", "size": 274_000_000},
                {"name": "qwen3.5:27b", "size": 17_000_000_000},
                {"name": "qwen2.5:7b", "size": 4_700_000_000},
            ]
        }

        ollama_client.client = AsyncMock()
        ollama_client.client.get = AsyncMock(return_value=mock_response)

        models = await ollama_client.discover_models()

        assert len(models) == 3
        assert models[0]["name"] == "qwen3.5:27b"
        assert models[1]["name"] == "qwen2.5:7b"
        assert models[2]["name"] == "nomic-embed-text"

    @pytest.mark.asyncio
    async def test_discover_models_empty_when_unreachable(self, ollama_client):
        """Should return empty list when Ollama is unreachable."""
        ollama_client.client = AsyncMock()
        ollama_client.client.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        models = await ollama_client.discover_models()
        assert models == []

    @pytest.mark.asyncio
    async def test_discover_models_empty_when_no_models(self, ollama_client):
        """Should return empty list when no models are pulled."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"models": []}

        ollama_client.client = AsyncMock()
        ollama_client.client.get = AsyncMock(return_value=mock_response)

        models = await ollama_client.discover_models()
        assert models == []


# =============================================================================
# select_best_model tests
# =============================================================================


class TestSelectBestModel:
    @pytest.mark.asyncio
    async def test_selects_preferred_model_when_available(self, ollama_client):
        """Should return preferred model if it exists in available models."""
        ollama_client.discover_models = AsyncMock(
            return_value=[
                {"name": "qwen3.5:27b", "size": 17_000_000_000},
                {"name": "qwen2.5:7b", "size": 4_700_000_000},
            ]
        )

        result = await ollama_client.select_best_model(preferred_model="qwen2.5:7b")
        assert result == "qwen2.5:7b"

    @pytest.mark.asyncio
    async def test_falls_back_to_largest_when_preferred_missing(self, ollama_client):
        """Should pick largest non-embedding model when preferred is not found."""
        ollama_client.discover_models = AsyncMock(
            return_value=[
                {"name": "qwen3.5:27b", "size": 17_000_000_000},
                {"name": "qwen2.5:7b", "size": 4_700_000_000},
                {"name": "nomic-embed-text", "size": 274_000_000},
            ]
        )

        result = await ollama_client.select_best_model(
            preferred_model="llama3:70b"
        )
        assert result == "qwen3.5:27b"

    @pytest.mark.asyncio
    async def test_skips_embedding_models(self, ollama_client):
        """Should skip embedding models and pick a generation model."""
        ollama_client.discover_models = AsyncMock(
            return_value=[
                {"name": "nomic-embed-text", "size": 274_000_000},
                {"name": "bge-large", "size": 600_000_000},
                {"name": "qwen2.5:7b", "size": 4_700_000_000},
            ]
        )

        result = await ollama_client.select_best_model()
        assert result == "qwen2.5:7b"

    @pytest.mark.asyncio
    async def test_returns_none_when_no_models(self, ollama_client):
        """Should return None if Ollama has no models."""
        ollama_client.discover_models = AsyncMock(return_value=[])

        result = await ollama_client.select_best_model()
        assert result is None

    @pytest.mark.asyncio
    async def test_falls_back_to_embedding_if_only_option(self, ollama_client):
        """If only embedding models exist, use one anyway."""
        ollama_client.discover_models = AsyncMock(
            return_value=[
                {"name": "nomic-embed-text", "size": 274_000_000},
            ]
        )

        result = await ollama_client.select_best_model()
        assert result == "nomic-embed-text"

    @pytest.mark.asyncio
    async def test_no_preferred_selects_largest(self, ollama_client):
        """With no preferred model, should select the largest generation model."""
        ollama_client.discover_models = AsyncMock(
            return_value=[
                {"name": "qwen3.5:27b", "size": 17_000_000_000},
                {"name": "qwen2.5:7b", "size": 4_700_000_000},
            ]
        )

        result = await ollama_client.select_best_model()
        assert result == "qwen3.5:27b"


# =============================================================================
# format_model_size tests
# =============================================================================


class TestFormatModelSize:
    def test_gigabytes(self):
        assert OllamaClient.format_model_size(17_000_000_000) == "17.0GB"

    def test_megabytes(self):
        assert OllamaClient.format_model_size(274_000_000) == "274MB"

    def test_kilobytes(self):
        assert OllamaClient.format_model_size(500_000) == "500KB"

    def test_fractional_gigabytes(self):
        assert OllamaClient.format_model_size(4_700_000_000) == "4.7GB"


# =============================================================================
# probe_ollama_models integration test (via AgentOrchestrator)
# =============================================================================


class TestProbeOllamaModels:
    @pytest.mark.asyncio
    async def test_probe_selects_configured_model(self):
        """Probe should use the configured model when available."""
        from src.application.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()
        orchestrator.ollama_client.discover_models = AsyncMock(
            return_value=[
                {"name": "qwen3.5:27b", "size": 17_000_000_000},
                {"name": "qwen2.5:7b", "size": 4_700_000_000},
            ]
        )
        orchestrator.ollama_client.select_best_model = AsyncMock(
            return_value="qwen2.5:7b"
        )

        with patch.dict("os.environ", {"OLLAMA_MODEL": "qwen2.5:7b"}):
            result = await orchestrator.probe_ollama_models()

        assert result == "qwen2.5:7b"
        assert orchestrator._selected_model == "qwen2.5:7b"
        assert orchestrator.ollama_client.model == "qwen2.5:7b"

    @pytest.mark.asyncio
    async def test_probe_returns_none_when_unreachable(self):
        """Probe should return None and log error when Ollama unreachable."""
        from src.application.services.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()
        orchestrator.ollama_client.discover_models = AsyncMock(return_value=[])

        result = await orchestrator.probe_ollama_models()
        assert result is None
        assert orchestrator._selected_model is None
