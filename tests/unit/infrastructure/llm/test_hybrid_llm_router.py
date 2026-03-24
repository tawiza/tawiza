"""Tests for HybridLLMRouter - Intelligent LLM routing for TAJINE."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestHybridLLMRouterImports:
    """Test that HybridLLMRouter can be imported."""

    def test_import_hybrid_router(self):
        """Test HybridLLMRouter class can be imported."""
        from src.infrastructure.llm import HybridLLMRouter

        assert HybridLLMRouter is not None

    def test_import_task_complexity(self):
        """Test TaskComplexity enum can be imported."""
        from src.infrastructure.llm.hybrid_router import TaskComplexity

        assert TaskComplexity is not None

    def test_import_routing_decision(self):
        """Test RoutingDecision can be imported."""
        from src.infrastructure.llm.hybrid_router import RoutingDecision

        assert RoutingDecision is not None


class TestHybridLLMRouterCreation:
    """Test HybridLLMRouter instantiation."""

    def test_create_with_defaults(self):
        """Test creating router with default config."""
        from src.infrastructure.llm import HybridLLMRouter

        router = HybridLLMRouter()

        assert router is not None
        assert router.local_model is not None
        assert router.powerful_model is not None

    def test_create_with_custom_models(self):
        """Test creating router with custom models."""
        from src.infrastructure.llm import HybridLLMRouter

        router = HybridLLMRouter(local_model="qwen3:14b", powerful_model="qwen3-coder:30b")

        assert router.local_model == "qwen3:14b"
        assert router.powerful_model == "qwen3-coder:30b"

    def test_has_complexity_analyzer(self):
        """Test router has complexity analyzer."""
        from src.infrastructure.llm import HybridLLMRouter

        router = HybridLLMRouter()

        assert hasattr(router, "complexity_analyzer")


class TestTaskComplexity:
    """Test task complexity levels."""

    def test_complexity_levels(self):
        """Test all complexity levels exist."""
        from src.infrastructure.llm.hybrid_router import TaskComplexity

        assert TaskComplexity.SIMPLE is not None
        assert TaskComplexity.MODERATE is not None
        assert TaskComplexity.COMPLEX is not None
        assert TaskComplexity.STRATEGIC is not None

    def test_complexity_ordering(self):
        """Test complexity levels are ordered."""
        from src.infrastructure.llm.hybrid_router import TaskComplexity

        assert TaskComplexity.SIMPLE.value < TaskComplexity.MODERATE.value
        assert TaskComplexity.MODERATE.value < TaskComplexity.COMPLEX.value
        assert TaskComplexity.COMPLEX.value < TaskComplexity.STRATEGIC.value


class TestTaskComplexityAnalyzer:
    """Test TaskComplexityAnalyzer."""

    def test_analyze_simple_task(self):
        """Test analyzing a simple task."""
        from src.infrastructure.llm.hybrid_router import TaskComplexity, TaskComplexityAnalyzer

        analyzer = TaskComplexityAnalyzer()

        result = analyzer.analyze("What is the capital of France?")

        assert result.complexity == TaskComplexity.SIMPLE
        assert result.confidence > 0.5

    def test_analyze_complex_task(self):
        """Test analyzing a complex task."""
        from src.infrastructure.llm.hybrid_router import TaskComplexity, TaskComplexityAnalyzer

        analyzer = TaskComplexityAnalyzer()

        result = analyzer.analyze(
            "Analyse le potentiel économique du secteur tech dans l'Hérault "
            "pour les 5 prochaines années en tenant compte des tendances globales, "
            "des politiques locales et des facteurs démographiques."
        )

        assert result.complexity in [TaskComplexity.COMPLEX, TaskComplexity.STRATEGIC]

    def test_analyze_strategic_task(self):
        """Test analyzing strategic task with keywords."""
        from src.infrastructure.llm.hybrid_router import TaskComplexity, TaskComplexityAnalyzer

        analyzer = TaskComplexityAnalyzer()

        result = analyzer.analyze(
            "Développe une stratégie d'investissement multi-territoriale "
            "avec analyse causale des facteurs de croissance."
        )

        assert result.complexity == TaskComplexity.STRATEGIC

    def test_analyze_returns_features(self):
        """Test that analysis returns detected features."""
        from src.infrastructure.llm.hybrid_router import TaskComplexityAnalyzer

        analyzer = TaskComplexityAnalyzer()

        result = analyzer.analyze("Compare les performances économiques de 3 régions.")

        assert "features" in result.__dict__ or hasattr(result, "features")


class TestRoutingDecision:
    """Test routing decision making."""

    @pytest.mark.asyncio
    async def test_route_simple_to_local(self):
        """Test simple tasks route to local model."""
        from src.infrastructure.llm import HybridLLMRouter

        router = HybridLLMRouter()

        decision = await router.decide_route(prompt="What is 2 + 2?", trust_score=0.8)

        assert decision.model_type == "local"
        assert decision.model_name == router.local_model

    @pytest.mark.asyncio
    async def test_route_strategic_to_powerful(self):
        """Test strategic tasks route to powerful model."""
        from src.infrastructure.llm import HybridLLMRouter

        router = HybridLLMRouter()

        decision = await router.decide_route(
            prompt="Analyse causale des facteurs de croissance avec validation théorique.",
            trust_score=0.5,
        )

        assert decision.model_type == "powerful"

    @pytest.mark.asyncio
    async def test_low_trust_routes_to_powerful(self):
        """Test low trust score routes to powerful model."""
        from src.infrastructure.llm import HybridLLMRouter

        router = HybridLLMRouter()

        decision = await router.decide_route(
            prompt="Simple calculation task",
            trust_score=0.2,  # Low trust
        )

        assert decision.model_type == "powerful"

    @pytest.mark.asyncio
    async def test_high_trust_enables_local(self):
        """Test high trust score allows local model usage."""
        from src.infrastructure.llm import HybridLLMRouter

        router = HybridLLMRouter()

        decision = await router.decide_route(
            prompt="List files in directory",
            trust_score=0.9,  # High trust
        )

        assert decision.model_type == "local"

    @pytest.mark.asyncio
    async def test_decision_includes_reasoning(self):
        """Test routing decision includes reasoning."""
        from src.infrastructure.llm import HybridLLMRouter

        router = HybridLLMRouter()

        decision = await router.decide_route(prompt="Test prompt", trust_score=0.5)

        assert hasattr(decision, "reasoning")
        assert len(decision.reasoning) > 0


class TestHybridLLMRouterGenerate:
    """Test HybridLLMRouter generation."""

    @pytest.mark.asyncio
    async def test_generate_routes_automatically(self):
        """Test generate() routes based on complexity."""
        from src.infrastructure.llm import HybridLLMRouter
        from src.infrastructure.llm.multi_provider import LLMResponse, ProviderType

        router = HybridLLMRouter()

        # Create a proper mock response
        mock_response = LLMResponse(
            content="Local response", provider=ProviderType.OLLAMA, model="qwen3:14b"
        )

        with patch.object(router._local_client, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response

            response = await router.generate(prompt="What is 1 + 1?", trust_score=0.9)

            assert response is not None

    @pytest.mark.asyncio
    async def test_generate_returns_response_with_metadata(self):
        """Test generate returns response with routing metadata."""
        from src.infrastructure.llm import HybridLLMRouter
        from src.infrastructure.llm.multi_provider import LLMResponse, ProviderType

        router = HybridLLMRouter()

        mock_response = LLMResponse(
            content="Test response", provider=ProviderType.OLLAMA, model="qwen3:14b"
        )

        with patch.object(router._local_client, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response

            response = await router.generate(
                prompt="Simple test", trust_score=0.8, include_metadata=True
            )

            assert "content" in response
            assert "routing" in response

    @pytest.mark.asyncio
    async def test_force_model_overrides_routing(self):
        """Test force_model parameter bypasses routing."""
        from src.infrastructure.llm import HybridLLMRouter
        from src.infrastructure.llm.multi_provider import LLMResponse, ProviderType

        router = HybridLLMRouter()

        mock_response = LLMResponse(
            content="Powerful response", provider=ProviderType.OLLAMA, model="qwen3-coder:30b"
        )

        with patch.object(router._powerful_client, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response

            response = await router.generate(
                prompt="Simple task", trust_score=0.9, force_model="powerful"
            )

            mock_gen.assert_called()


class TestHybridLLMRouterChat:
    """Test HybridLLMRouter chat interface."""

    @pytest.mark.asyncio
    async def test_chat_routes_based_on_messages(self):
        """Test chat() analyzes full message context."""
        from src.infrastructure.llm import HybridLLMRouter
        from src.infrastructure.llm.multi_provider import ChatMessage, LLMResponse, ProviderType

        router = HybridLLMRouter()

        messages = [
            ChatMessage(role="system", content="You are an analyst"),
            ChatMessage(role="user", content="Analyse les tendances du marché"),
        ]

        mock_response = LLMResponse(
            content="Analysis result",
            provider=ProviderType.OLLAMA,
            model="qwen3:14b",
            tool_calls=[],
        )

        with patch.object(router._local_client, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response

            response = await router.chat(messages=messages, trust_score=0.7)

            assert response is not None
            assert "content" in response

    @pytest.mark.asyncio
    async def test_chat_supports_tools(self):
        """Test chat() supports tool calling."""
        from src.infrastructure.llm import HybridLLMRouter
        from src.infrastructure.llm.multi_provider import ChatMessage, LLMResponse, ProviderType

        router = HybridLLMRouter()

        messages = [ChatMessage(role="user", content="Get data")]
        tools = [{"type": "function", "function": {"name": "get_data"}}]

        mock_response = LLMResponse(
            content="",
            provider=ProviderType.OLLAMA,
            model="qwen3:14b",
            tool_calls=[{"name": "get_data"}],
        )

        with patch.object(router._local_client, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response

            response = await router.chat(messages=messages, trust_score=0.8, tools=tools)

            assert "tool_calls" in response


class TestOumiClientIntegration:
    """Test OumiClient integration for fine-tuned models."""

    def test_import_oumi_client(self):
        """Test OumiClient can be imported."""
        from src.infrastructure.llm.hybrid_router import OumiClient

        assert OumiClient is not None

    def test_create_oumi_client(self):
        """Test creating OumiClient."""
        from src.infrastructure.llm.hybrid_router import OumiClient

        client = OumiClient(model="coalm-8b")

        assert client.model == "coalm-8b"

    @pytest.mark.asyncio
    async def test_oumi_client_generate(self):
        """Test OumiClient generation (stub)."""
        from src.infrastructure.llm.hybrid_router import OumiClient

        client = OumiClient(model="coalm-8b")

        # Should work even without real Oumi backend (stub mode)
        response = await client.generate(prompt="Test prompt", fallback_to_ollama=True)

        assert response is not None


class TestHybridRouterFallback:
    """Test fallback behavior."""

    @pytest.mark.asyncio
    async def test_fallback_to_local_on_powerful_failure(self):
        """Test fallback to local when powerful fails."""
        from src.infrastructure.llm import HybridLLMRouter
        from src.infrastructure.llm.multi_provider import LLMResponse, ProviderType

        router = HybridLLMRouter()

        mock_fallback_response = LLMResponse(
            content="Fallback response", provider=ProviderType.OLLAMA, model="qwen3:14b"
        )

        with patch.object(
            router._powerful_client, "generate", new_callable=AsyncMock
        ) as mock_powerful:
            mock_powerful.side_effect = Exception("Powerful model unavailable")

            with patch.object(
                router._local_client, "generate", new_callable=AsyncMock
            ) as mock_local:
                mock_local.return_value = mock_fallback_response

                response = await router.generate(
                    prompt="Complex task",
                    trust_score=0.3,  # Would normally route to powerful
                    allow_fallback=True,
                )

                assert response is not None

    @pytest.mark.asyncio
    async def test_no_fallback_when_disabled(self):
        """Test no fallback when disabled."""
        from src.infrastructure.llm import HybridLLMRouter

        router = HybridLLMRouter()

        with patch.object(
            router._powerful_client, "generate", new_callable=AsyncMock
        ) as mock_powerful:
            mock_powerful.side_effect = Exception("Model unavailable")

            with pytest.raises(Exception):
                await router.generate(
                    prompt="Task",
                    trust_score=0.1,  # Low trust forces powerful model
                    allow_fallback=False,
                )


class TestRoutingMetrics:
    """Test routing metrics and logging."""

    @pytest.mark.asyncio
    async def test_track_routing_metrics(self):
        """Test that routing decisions are tracked."""
        from src.infrastructure.llm import HybridLLMRouter

        router = HybridLLMRouter()

        mock_response = MagicMock()
        mock_response.content = "Response"

        with (
            patch.object(router, "_local_client") as mock_local,
            patch.object(router, "_powerful_client") as mock_powerful,
        ):
            mock_local.generate = AsyncMock(return_value=mock_response)
            mock_powerful.generate = AsyncMock(return_value=mock_response)

            await router.generate(prompt="Test 1", trust_score=0.9)
            await router.generate(prompt="Test 2", trust_score=0.9)

        metrics = router.get_metrics()

        assert "total_requests" in metrics
        assert metrics["total_requests"] >= 2

    def test_get_routing_stats(self):
        """Test getting routing statistics."""
        from src.infrastructure.llm import HybridLLMRouter

        router = HybridLLMRouter()

        stats = router.get_routing_stats()

        assert "local_count" in stats
        assert "powerful_count" in stats
        assert "avg_complexity" in stats
