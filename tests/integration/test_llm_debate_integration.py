"""Integration tests for LLM-enhanced debate system."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_full_debate_with_mocked_llm():
    """Test complete debate flow with LLM."""
    from src.domain.debate import DebateMode
    from src.infrastructure.llm.factory import create_debate_system_with_llm

    with patch("src.infrastructure.llm.factory.OllamaClient") as MockClient:
        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value="LLM analysis response")
        mock_client.base_url = "http://localhost:11434"
        mock_client.client = MagicMock()
        MockClient.return_value = mock_client

        debate = create_debate_system_with_llm(mode=DebateMode.EXTENDED)

        data = {
            "results": [
                {"source": "sirene", "siret": "12345678901234", "name": "Test Corp"},
                {"source": "bodacc", "siret": "12345678901234", "name": "Test Corp"},
            ],
            "sources": ["sirene", "bodacc"],
        }

        result = await debate.validate("Test Corp", data)

        assert result is not None
        assert len(result.messages) == 6  # Extended mode has 6 agents
        assert result.final_confidence > 0


@pytest.mark.asyncio
async def test_debate_without_llm_fallback():
    """Test debate system works without LLM (rule-based fallback)."""
    from src.domain.debate import DebateMode, DebateSystem

    # Create debate system without LLM
    debate = DebateSystem(mode=DebateMode.STANDARD)

    data = {
        "results": [
            {"source": "sirene", "siret": "12345678901234", "name": "Test Corp"},
        ],
        "sources": ["sirene"],
    }

    result = await debate.validate("Test Corp", data)

    assert result is not None
    assert result.final_confidence >= 0
    # Standard mode has 3 agents
    assert len(result.messages) == 3


@pytest.mark.asyncio
async def test_adaptive_provider_text_mode():
    """Test AdaptiveLLMProvider uses text model for text-only prompts."""
    from src.infrastructure.llm.adaptive_provider import AdaptiveLLMProvider

    mock_client = MagicMock()
    mock_client.generate = AsyncMock(return_value="Text response")

    provider = AdaptiveLLMProvider(
        client=mock_client,
        text_model="qwen3:14b",
        vision_model="qwen3-vl:32b",
    )

    result = await provider.generate("Hello, world!")

    mock_client.generate.assert_called_once()
    call_kwargs = mock_client.generate.call_args.kwargs
    assert call_kwargs.get("model") == "qwen3:14b"
    assert result == "Text response"


@pytest.mark.asyncio
async def test_vision_analyzer_with_mock():
    """Test VisionAnalyzer with mocked provider."""
    from src.infrastructure.llm.vision_analyzer import VisionAnalyzer

    mock_provider = MagicMock()
    mock_provider.generate = AsyncMock(return_value='{"name": "Acme Corp"}')

    analyzer = VisionAnalyzer(provider=mock_provider)

    result = await analyzer.extract_company_info(image_bytes=b"fake_screenshot")

    assert "Acme Corp" in result
    mock_provider.generate.assert_called_once()
    # Verify images were passed
    call_kwargs = mock_provider.generate.call_args.kwargs
    assert call_kwargs.get("images") == [b"fake_screenshot"]


@pytest.mark.asyncio
async def test_agents_have_system_prompts():
    """Test that all LLM-enabled agents have system prompts."""
    from src.domain.debate.agents import (
        ChercheurAgent,
        CritiqueAgent,
        FactCheckerAgent,
        SourceRankerAgent,
        SynthesisAgent,
        VerificateurAgent,
    )

    agents = [
        ChercheurAgent,
        CritiqueAgent,
        VerificateurAgent,
        FactCheckerAgent,
        SourceRankerAgent,
        SynthesisAgent,
    ]

    for agent_class in agents:
        assert hasattr(agent_class, "SYSTEM_PROMPT"), (
            f"{agent_class.__name__} missing SYSTEM_PROMPT"
        )
        assert agent_class.SYSTEM_PROMPT, f"{agent_class.__name__} has empty SYSTEM_PROMPT"
        assert "français" in agent_class.SYSTEM_PROMPT.lower(), (
            f"{agent_class.__name__} SYSTEM_PROMPT should mention French"
        )
