"""Tests for VisionAnalyzer service."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.llm.vision_analyzer import VisionAnalyzer


@pytest.fixture
def mock_provider():
    """Mock LLM provider for testing."""
    provider = MagicMock()
    provider.generate = AsyncMock(return_value="Analysis result")
    return provider


@pytest.mark.asyncio
async def test_analyze_screenshot_returns_analysis(mock_provider):
    """Test that analyze_screenshot returns LLM analysis."""
    analyzer = VisionAnalyzer(provider=mock_provider)

    result = await analyzer.analyze_screenshot(
        image_bytes=b"fake_image_data",
        prompt="Describe this website",
    )

    mock_provider.generate.assert_called_once()
    call_kwargs = mock_provider.generate.call_args
    assert b"fake_image_data" in call_kwargs.kwargs.get("images", [])
    assert result == "Analysis result"


@pytest.mark.asyncio
async def test_analyze_screenshot_with_system_prompt(mock_provider):
    """Test that system prompt is passed to provider."""
    analyzer = VisionAnalyzer(provider=mock_provider)

    await analyzer.analyze_screenshot(
        image_bytes=b"image",
        prompt="What do you see?",
        system="You are an expert analyst.",
    )

    call_kwargs = mock_provider.generate.call_args
    assert call_kwargs.kwargs.get("system") == "You are an expert analyst."


@pytest.mark.asyncio
async def test_extract_company_info(mock_provider):
    """Test specialized company info extraction."""
    mock_provider.generate = AsyncMock(return_value='{"name": "Test Corp", "sector": "Tech"}')
    analyzer = VisionAnalyzer(provider=mock_provider)

    result = await analyzer.extract_company_info(image_bytes=b"screenshot")

    assert "Test Corp" in result
    # Verify specific prompt for company extraction
    call_kwargs = mock_provider.generate.call_args
    assert "company" in call_kwargs.kwargs.get("prompt", "").lower()
