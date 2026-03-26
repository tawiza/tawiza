"""Tests for LLM factory functions."""

from unittest.mock import MagicMock, patch

import pytest


def test_create_debate_system_with_llm():
    """Test factory creates properly configured DebateSystem."""
    with patch("src.infrastructure.llm.factory.OllamaClient") as MockClient:
        mock_client = MagicMock()
        mock_client.base_url = "http://localhost:11434"
        MockClient.return_value = mock_client

        from src.infrastructure.llm.factory import create_debate_system_with_llm

        debate_system = create_debate_system_with_llm(
            text_model="qwen3:14b",
            vision_model="qwen3-vl:32b",
        )

        assert debate_system is not None
        # All agents should have LLM configured
        assert debate_system.chercheur.has_llm
        assert debate_system.critique.has_llm
        assert debate_system.verificateur.has_llm


def test_create_vision_analyzer():
    """Test factory creates VisionAnalyzer."""
    with patch("src.infrastructure.llm.factory.OllamaClient") as MockClient:
        mock_client = MagicMock()
        mock_client.base_url = "http://localhost:11434"
        MockClient.return_value = mock_client

        from src.infrastructure.llm.factory import create_vision_analyzer

        analyzer = create_vision_analyzer(vision_model="qwen3-vl:32b")

        assert analyzer is not None


def test_create_debate_system_with_default_models():
    """Test factory uses default models when not specified."""
    with patch("src.infrastructure.llm.factory.OllamaClient") as MockClient:
        mock_client = MagicMock()
        mock_client.base_url = "http://localhost:11434"
        MockClient.return_value = mock_client

        from src.infrastructure.llm.factory import create_debate_system_with_llm

        debate_system = create_debate_system_with_llm()

        MockClient.assert_called_once()
        # Check default model was used
        call_kwargs = MockClient.call_args
        assert call_kwargs.kwargs.get("model") == "qwen3.5:27b"
