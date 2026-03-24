"""Tests for AdaptiveLLMProvider."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.llm.adaptive_provider import AdaptiveLLMProvider


@pytest.fixture
def mock_ollama_client():
    """Mock OllamaClient for testing."""
    client = MagicMock()
    client.generate = AsyncMock(return_value="Generated response")
    client.analyze_screenshot = AsyncMock(return_value="Vision response")
    client.base_url = "http://localhost:11434"

    # Mock the httpx client for vision calls
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "Vision response"}
    mock_response.raise_for_status = MagicMock()
    client.client = MagicMock()
    client.client.post = AsyncMock(return_value=mock_response)

    return client


@pytest.mark.asyncio
async def test_generate_without_images_uses_text_model(mock_ollama_client):
    """Test that generate without images uses the text model."""
    provider = AdaptiveLLMProvider(
        client=mock_ollama_client,
        text_model="qwen3:14b",
        vision_model="qwen3-vl:32b",
    )

    result = await provider.generate("Hello world")

    mock_ollama_client.generate.assert_called_once()
    call_kwargs = mock_ollama_client.generate.call_args
    assert (
        call_kwargs.kwargs.get("model") == "qwen3:14b" or call_kwargs[1].get("model") == "qwen3:14b"
    )
    assert result == "Generated response"


@pytest.mark.asyncio
async def test_generate_with_images_uses_vision_model(mock_ollama_client):
    """Test that generate with images uses the vision model."""
    provider = AdaptiveLLMProvider(
        client=mock_ollama_client,
        text_model="qwen3:14b",
        vision_model="qwen3-vl:32b",
    )

    result = await provider.generate("Describe this image", images=[b"fake_image_data"])

    # Should use vision capability via HTTP client
    mock_ollama_client.client.post.assert_called_once()
    call_args = mock_ollama_client.client.post.call_args
    assert "qwen3-vl:32b" in str(call_args)  # Vision model used
    assert result == "Vision response"
