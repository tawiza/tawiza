"""Tests for LLM-powered cognitive processing.

Tests the integration of Ollama LLM with CognitiveEngine levels.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestLLMProviderImports:
    """Test LLMProvider can be imported."""

    def test_import_llm_provider(self):
        """Test LLMProvider class can be imported."""
        from src.infrastructure.agents.tajine.cognitive.llm_provider import LLMProvider

        assert LLMProvider is not None

    def test_import_cognitive_prompts(self):
        """Test cognitive prompts module can be imported."""
        from src.infrastructure.agents.tajine.cognitive.llm_provider import COGNITIVE_PROMPTS

        assert COGNITIVE_PROMPTS is not None


class TestLLMProviderCreation:
    """Test LLMProvider instantiation."""

    def test_create_llm_provider_default(self):
        """Test creating LLMProvider with defaults."""
        from src.infrastructure.agents.tajine.cognitive.llm_provider import LLMProvider

        provider = LLMProvider()
        assert provider is not None
        assert provider.model is not None

    def test_create_llm_provider_with_model(self):
        """Test creating LLMProvider with custom model."""
        from src.infrastructure.agents.tajine.cognitive.llm_provider import LLMProvider

        provider = LLMProvider(model="qwen3:14b")
        assert provider.model == "qwen3:14b"

    def test_create_llm_provider_with_client(self):
        """Test creating LLMProvider with existing Ollama client."""
        from src.infrastructure.agents.tajine.cognitive.llm_provider import LLMProvider

        mock_client = MagicMock()
        provider = LLMProvider(client=mock_client)
        assert provider._client is mock_client


class TestLLMProviderGenerate:
    """Test LLMProvider.generate() method."""

    @pytest.mark.asyncio
    async def test_generate_returns_string(self):
        """Test generate() returns a string response."""
        from src.infrastructure.agents.tajine.cognitive.llm_provider import LLMProvider

        provider = LLMProvider()

        # Mock the underlying Ollama client
        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value="Test response")
        provider._client = mock_client

        result = await provider.generate("Test prompt")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_generate_with_system_prompt(self):
        """Test generate() uses system prompt."""
        from src.infrastructure.agents.tajine.cognitive.llm_provider import LLMProvider

        provider = LLMProvider()

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value="Response")
        provider._client = mock_client

        await provider.generate("User prompt", system="System prompt")

        mock_client.generate.assert_called_once()
        call_kwargs = mock_client.generate.call_args
        assert call_kwargs[1].get("system") == "System prompt" or (
            call_kwargs[0] and "System prompt" in str(call_kwargs)
        )

    @pytest.mark.asyncio
    async def test_generate_handles_connection_error(self):
        """Test generate() handles connection errors gracefully."""
        from src.infrastructure.agents.tajine.cognitive.llm_provider import LLMProvider

        provider = LLMProvider()

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(side_effect=Exception("Connection refused"))
        provider._client = mock_client

        result = await provider.generate("Test prompt")
        assert result is None or result == ""


class TestLLMProviderJSON:
    """Test LLMProvider JSON parsing."""

    @pytest.mark.asyncio
    async def test_generate_json_parses_response(self):
        """Test generate_json() parses JSON from response."""
        from src.infrastructure.agents.tajine.cognitive.llm_provider import LLMProvider

        provider = LLMProvider()

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value='{"key": "value"}')
        provider._client = mock_client

        result = await provider.generate_json("Extract data")
        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_generate_json_handles_markdown_code_block(self):
        """Test generate_json() extracts JSON from markdown code blocks."""
        from src.infrastructure.agents.tajine.cognitive.llm_provider import LLMProvider

        provider = LLMProvider()

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(
            return_value="""Here's the analysis:

```json
{"analysis": "test", "confidence": 0.8}
```

That's the result."""
        )
        provider._client = mock_client

        result = await provider.generate_json("Extract data")
        assert result["analysis"] == "test"
        assert result["confidence"] == 0.8

    @pytest.mark.asyncio
    async def test_generate_json_returns_empty_on_invalid(self):
        """Test generate_json() returns empty dict on invalid JSON."""
        from src.infrastructure.agents.tajine.cognitive.llm_provider import LLMProvider

        provider = LLMProvider()

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value="Not JSON at all")
        provider._client = mock_client

        result = await provider.generate_json("Extract data")
        assert result == {}


class TestCognitivePrompts:
    """Test cognitive level prompts."""

    def test_prompts_has_all_levels(self):
        """Test COGNITIVE_PROMPTS has entries for all 5 levels."""
        from src.infrastructure.agents.tajine.cognitive.llm_provider import COGNITIVE_PROMPTS

        assert "discovery" in COGNITIVE_PROMPTS
        assert "causal" in COGNITIVE_PROMPTS
        assert "scenario" in COGNITIVE_PROMPTS
        assert "strategy" in COGNITIVE_PROMPTS
        assert "theoretical" in COGNITIVE_PROMPTS

    def test_prompts_are_strings(self):
        """Test all prompts are non-empty strings."""
        from src.infrastructure.agents.tajine.cognitive.llm_provider import COGNITIVE_PROMPTS

        for level, prompt in COGNITIVE_PROMPTS.items():
            assert isinstance(prompt, str), f"{level} prompt should be string"
            assert len(prompt) > 50, f"{level} prompt should be substantial"


class TestCognitiveEngineWithLLM:
    """Test CognitiveEngine with LLM integration."""

    def test_engine_accepts_llm_provider(self):
        """Test CognitiveEngine can be created with LLM provider."""
        from src.infrastructure.agents.tajine.cognitive import CognitiveEngine
        from src.infrastructure.agents.tajine.cognitive.llm_provider import LLMProvider

        mock_provider = MagicMock(spec=LLMProvider)
        engine = CognitiveEngine(llm_provider=mock_provider)

        assert engine._llm_provider is mock_provider

    def test_engine_without_llm_uses_rules(self):
        """Test CognitiveEngine works without LLM (rule-based fallback)."""
        from src.infrastructure.agents.tajine.cognitive import CognitiveEngine

        engine = CognitiveEngine()
        assert engine._llm_provider is None

    @pytest.mark.asyncio
    async def test_engine_process_with_llm(self):
        """Test CognitiveEngine.process() uses LLM when available."""
        from src.infrastructure.agents.tajine.cognitive import CognitiveEngine
        from src.infrastructure.agents.tajine.cognitive.llm_provider import LLMProvider

        mock_provider = MagicMock(spec=LLMProvider)
        # Mock process_level to return different results for each level
        mock_provider.process_level = AsyncMock(
            side_effect=[
                {
                    "signals": [{"type": "growth", "strength": 0.8}],
                    "patterns": [],
                    "confidence": 0.85,
                },
                {
                    "causes": [{"factor": "test", "contribution": 0.5}],
                    "effects": [],
                    "confidence": 0.75,
                },
                {"optimistic": {}, "median": {}, "pessimistic": {}, "confidence": 0.7},
                {"recommendations": [], "actions": [], "confidence": 0.65},
                {"theory_validations": [], "confidence": 0.6},
            ]
        )

        engine = CognitiveEngine(llm_provider=mock_provider)

        results = [{"result": {"companies": 500}}]
        synthesis = await engine.process(results)

        assert "cognitive_levels" in synthesis
        assert "confidence" in synthesis


class TestDiscoveryLevelWithLLM:
    """Test DiscoveryLevel with LLM integration."""

    @pytest.mark.asyncio
    async def test_discovery_uses_llm_when_available(self):
        """Test DiscoveryLevel uses LLM for signal detection."""
        from src.infrastructure.agents.tajine.cognitive.levels import DiscoveryLevel
        from src.infrastructure.agents.tajine.cognitive.llm_provider import LLMProvider

        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.process_level = AsyncMock(
            return_value={
                "signals": [
                    {
                        "type": "growth",
                        "description": "Tech sector expanding",
                        "strength": 0.9,
                        "source": "llm",
                    }
                ],
                "patterns": [],
                "confidence": 0.85,
            }
        )

        level = DiscoveryLevel(llm_provider=mock_provider)

        result = await level.process([{"result": {"companies": 847, "sector": "tech"}}], {})

        assert len(result["signals"]) >= 1
        # LLM should have been called
        mock_provider.process_level.assert_called_once()

    @pytest.mark.asyncio
    async def test_discovery_fallback_without_llm(self):
        """Test DiscoveryLevel falls back to rules without LLM."""
        from src.infrastructure.agents.tajine.cognitive.levels import DiscoveryLevel

        level = DiscoveryLevel()  # No LLM provider

        result = await level.process([{"result": {"companies": 847}}], {})

        # Should still work with rule-based detection
        assert "signals" in result
        assert "confidence" in result


class TestCausalLevelWithLLM:
    """Test CausalLevel with LLM integration."""

    @pytest.mark.asyncio
    async def test_causal_uses_llm_for_analysis(self):
        """Test CausalLevel uses LLM for causal analysis."""
        from src.infrastructure.agents.tajine.cognitive.levels import CausalLevel
        from src.infrastructure.agents.tajine.cognitive.llm_provider import LLMProvider

        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.process_level = AsyncMock(
            return_value={
                "causes": [{"factor": "university_proximity", "contribution": 0.4}],
                "effects": [{"outcome": "job_growth", "magnitude": "high"}],
                "confidence": 0.75,
            }
        )

        level = CausalLevel(llm_provider=mock_provider)

        result = await level.process([], {"discovery": {"signals": [{"type": "growth"}]}})

        assert "causes" in result
        mock_provider.process_level.assert_called_once()


class TestScenarioLevelWithLLM:
    """Test ScenarioLevel with LLM integration."""

    @pytest.mark.asyncio
    async def test_scenario_generates_three_scenarios(self):
        """Test ScenarioLevel generates optimistic/median/pessimistic."""
        from src.infrastructure.agents.tajine.cognitive.levels import ScenarioLevel
        from src.infrastructure.agents.tajine.cognitive.llm_provider import LLMProvider

        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.process_level = AsyncMock(
            return_value={
                "optimistic": {"growth_rate": 0.25, "probability": 0.2},
                "median": {"growth_rate": 0.15, "probability": 0.6},
                "pessimistic": {"growth_rate": 0.05, "probability": 0.2},
                "confidence": 0.7,
            }
        )

        level = ScenarioLevel(llm_provider=mock_provider)

        result = await level.process([], {"causal": {"causes": [{"contribution": 0.3}]}})

        assert "optimistic" in result
        assert "median" in result
        assert "pessimistic" in result
