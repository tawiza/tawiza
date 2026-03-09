"""Tests for HybridLLMRouter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.agents.tajine.llm_router import (
    HybridLLMRouter,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    ModelTier,
    OllamaProvider,
    OumiProvider,
    RoutingDecision,
    TaskComplexity,
    create_hybrid_router,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_local_provider():
    """Mock local provider."""
    provider = MagicMock(spec=LLMProvider)
    provider.name = "ollama/qwen3:14b"
    provider.tier = ModelTier.LOCAL
    provider.is_available = AsyncMock(return_value=True)
    provider.generate = AsyncMock(
        return_value={"content": "Local response", "tokens": 50, "model": "qwen3:14b"}
    )
    return provider


@pytest.fixture
def mock_standard_provider():
    """Mock standard provider."""
    provider = MagicMock(spec=LLMProvider)
    provider.name = "oumi/coalm-8b"
    provider.tier = ModelTier.STANDARD
    provider.is_available = AsyncMock(return_value=True)
    provider.generate = AsyncMock(
        return_value={"content": "Standard response", "tokens": 100, "model": "coalm-8b"}
    )
    return provider


@pytest.fixture
def mock_powerful_provider():
    """Mock powerful provider."""
    provider = MagicMock(spec=LLMProvider)
    provider.name = "oumi/coalm-70b"
    provider.tier = ModelTier.POWERFUL
    provider.is_available = AsyncMock(return_value=True)
    provider.generate = AsyncMock(
        return_value={"content": "Powerful response", "tokens": 150, "model": "coalm-70b"}
    )
    return provider


@pytest.fixture
def router(mock_local_provider, mock_standard_provider, mock_powerful_provider):
    """Create router with mock providers."""
    return HybridLLMRouter(
        local_provider=mock_local_provider,
        standard_provider=mock_standard_provider,
        powerful_provider=mock_powerful_provider,
    )


# ============================================================================
# ModelTier Tests
# ============================================================================


class TestModelTier:
    """Tests for ModelTier enum."""

    def test_tier_values(self):
        """Test tier enum values."""
        assert ModelTier.LOCAL.value == "local"
        assert ModelTier.STANDARD.value == "standard"
        assert ModelTier.POWERFUL.value == "powerful"
        assert ModelTier.MAXIMUM.value == "maximum"


class TestTaskComplexity:
    """Tests for TaskComplexity enum."""

    def test_complexity_values(self):
        """Test complexity enum values."""
        assert TaskComplexity.SIMPLE.value == "simple"
        assert TaskComplexity.MODERATE.value == "moderate"
        assert TaskComplexity.COMPLEX.value == "complex"
        assert TaskComplexity.CRITICAL.value == "critical"


# ============================================================================
# LLMRequest Tests
# ============================================================================


class TestLLMRequest:
    """Tests for LLMRequest dataclass."""

    def test_default_values(self):
        """Test default request values."""
        request = LLMRequest(prompt="Test prompt")

        assert request.prompt == "Test prompt"
        assert request.complexity == TaskComplexity.MODERATE
        assert request.trust_score == 0.5
        assert request.confidence_required == 0.7
        assert request.max_tokens == 2048

    def test_custom_values(self):
        """Test custom request values."""
        request = LLMRequest(
            prompt="Complex analysis",
            complexity=TaskComplexity.COMPLEX,
            trust_score=0.9,
            confidence_required=0.95,
        )

        assert request.complexity == TaskComplexity.COMPLEX
        assert request.trust_score == 0.9
        assert request.confidence_required == 0.95


# ============================================================================
# Routing Decision Tests
# ============================================================================


class TestRoutingDecision:
    """Tests for routing decision logic."""

    def test_simple_task_routes_to_local(self, router):
        """Simple task should route to local provider."""
        request = LLMRequest(
            prompt="What is 2+2?", complexity=TaskComplexity.SIMPLE, trust_score=0.8
        )

        decision = router._make_routing_decision(request)

        assert decision.tier == ModelTier.LOCAL

    def test_moderate_task_routes_to_standard(self, router):
        """Moderate task should route to standard provider."""
        request = LLMRequest(
            prompt="Explain photosynthesis", complexity=TaskComplexity.MODERATE, trust_score=0.5
        )

        decision = router._make_routing_decision(request)

        assert decision.tier == ModelTier.STANDARD

    def test_complex_task_routes_to_powerful(self, router):
        """Complex task should route to powerful provider."""
        request = LLMRequest(
            prompt="Analyze economic trends in Nouvelle-Aquitaine",
            complexity=TaskComplexity.COMPLEX,
            trust_score=0.5,
        )

        decision = router._make_routing_decision(request)

        assert decision.tier == ModelTier.POWERFUL

    def test_critical_task_routes_to_maximum(self, router):
        """Critical task should route to maximum provider."""
        request = LLMRequest(
            prompt="Strategic investment decision",
            complexity=TaskComplexity.CRITICAL,
            trust_score=0.5,
        )

        decision = router._make_routing_decision(request)

        assert decision.tier == ModelTier.MAXIMUM

    def test_low_trust_upgrades_tier(self, router):
        """Low trust should upgrade the tier."""
        request = LLMRequest(
            prompt="Simple question", complexity=TaskComplexity.SIMPLE, trust_score=0.2
        )

        decision = router._make_routing_decision(request)

        # Should upgrade from LOCAL to STANDARD
        assert decision.tier == ModelTier.STANDARD

    def test_high_trust_can_downgrade(self, router):
        """High trust can downgrade non-critical tasks."""
        request = LLMRequest(
            prompt="Moderate question", complexity=TaskComplexity.MODERATE, trust_score=0.9
        )

        decision = router._make_routing_decision(request)

        # Should downgrade from STANDARD to LOCAL
        assert decision.tier == ModelTier.LOCAL

    def test_high_confidence_upgrades_tier(self, router):
        """High confidence requirement upgrades tier."""
        request = LLMRequest(
            prompt="Need high confidence",
            complexity=TaskComplexity.SIMPLE,
            confidence_required=0.95,
        )

        decision = router._make_routing_decision(request)

        # Should upgrade from LOCAL
        assert decision.tier != ModelTier.LOCAL

    def test_decision_has_fallback(self, router):
        """Decision should have fallback tier."""
        request = LLMRequest(prompt="Test", complexity=TaskComplexity.COMPLEX)

        decision = router._make_routing_decision(request)

        # POWERFUL should fall back to STANDARD
        assert decision.fallback_tier == ModelTier.STANDARD

    def test_local_has_no_fallback(self, router):
        """LOCAL tier should have no fallback (can't go lower)."""
        request = LLMRequest(prompt="Simple", complexity=TaskComplexity.SIMPLE, trust_score=0.9)

        decision = router._make_routing_decision(request)

        if decision.tier == ModelTier.LOCAL:
            assert decision.fallback_tier is None


# ============================================================================
# Route Execution Tests
# ============================================================================


class TestRouteExecution:
    """Tests for route() method execution."""

    @pytest.mark.asyncio
    async def test_routes_simple_to_local(self, router, mock_local_provider):
        """Simple request routes to local provider."""
        request = LLMRequest(
            prompt="What is 2+2?", complexity=TaskComplexity.SIMPLE, trust_score=0.9
        )

        response = await router.route(request)

        assert response.tier_used == ModelTier.LOCAL
        mock_local_provider.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_routes_complex_to_powerful(self, router, mock_powerful_provider):
        """Complex request routes to powerful provider."""
        request = LLMRequest(
            prompt="Analyze market trends", complexity=TaskComplexity.COMPLEX, trust_score=0.5
        )

        response = await router.route(request)

        assert response.tier_used == ModelTier.POWERFUL
        mock_powerful_provider.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_response_contains_content(self, router):
        """Response should contain generated content."""
        request = LLMRequest(prompt="Test", complexity=TaskComplexity.SIMPLE, trust_score=0.9)

        response = await router.route(request)

        assert response.content == "Local response"
        assert response.tokens_used == 50

    @pytest.mark.asyncio
    async def test_response_contains_metadata(self, router):
        """Response should contain routing metadata."""
        request = LLMRequest(prompt="Test", complexity=TaskComplexity.SIMPLE, trust_score=0.9)

        response = await router.route(request)

        assert response.routing_decision is not None
        assert response.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_fallback_on_provider_failure(
        self, router, mock_standard_provider, mock_local_provider
    ):
        """Falls back when primary provider fails."""
        # Make standard provider fail
        mock_standard_provider.generate = AsyncMock(side_effect=Exception("Provider error"))

        request = LLMRequest(prompt="Test", complexity=TaskComplexity.MODERATE, trust_score=0.5)

        response = await router.route(request)

        # Should have fallen back to local
        assert response.tier_used == ModelTier.LOCAL

    @pytest.mark.asyncio
    async def test_fallback_when_unavailable(
        self, router, mock_standard_provider, mock_local_provider
    ):
        """Falls back when primary provider unavailable."""
        mock_standard_provider.is_available = AsyncMock(return_value=False)

        request = LLMRequest(prompt="Test", complexity=TaskComplexity.MODERATE, trust_score=0.5)

        response = await router.route(request)

        # Should have fallen back
        mock_local_provider.generate.assert_called()


# ============================================================================
# Metrics Tests
# ============================================================================


class TestMetrics:
    """Tests for router metrics."""

    @pytest.mark.asyncio
    async def test_tracks_request_count(self, router):
        """Should track total request count."""
        request = LLMRequest(prompt="Test", complexity=TaskComplexity.SIMPLE)

        await router.route(request)
        await router.route(request)
        await router.route(request)

        metrics = router.get_metrics()
        assert metrics["total_requests"] == 3

    @pytest.mark.asyncio
    async def test_tracks_tier_usage(self, router):
        """Should track tier usage."""
        simple = LLMRequest(prompt="Simple", complexity=TaskComplexity.SIMPLE, trust_score=0.9)
        complex = LLMRequest(prompt="Complex", complexity=TaskComplexity.COMPLEX)

        await router.route(simple)
        await router.route(complex)

        metrics = router.get_metrics()
        assert metrics["tier_usage"]["local"] >= 1
        assert metrics["tier_usage"]["powerful"] >= 1


# ============================================================================
# Factory Tests
# ============================================================================


class TestFactory:
    """Tests for factory functions."""

    def test_create_hybrid_router(self):
        """Test factory creates router."""
        router = create_hybrid_router(local_model="qwen3:7b", ollama_host="http://localhost:11434")

        assert router is not None
        assert ModelTier.LOCAL in router._providers
        assert ModelTier.STANDARD in router._providers


# ============================================================================
# Provider Tests
# ============================================================================


class TestOllamaProvider:
    """Tests for OllamaProvider."""

    def test_provider_properties(self):
        """Test provider properties."""
        provider = OllamaProvider(model="qwen3:14b")

        assert provider.name == "ollama/qwen3:14b"
        assert provider.tier == ModelTier.LOCAL


class TestOumiProvider:
    """Tests for OumiProvider."""

    def test_provider_properties(self):
        """Test provider properties."""
        provider = OumiProvider(model="coalm-8b", tier=ModelTier.STANDARD)

        assert provider.name == "oumi/coalm-8b"
        assert provider.tier == ModelTier.STANDARD

    def test_provider_tiers(self):
        """Test different provider tiers."""
        standard = OumiProvider(model="coalm-8b", tier=ModelTier.STANDARD)
        powerful = OumiProvider(model="coalm-70b", tier=ModelTier.POWERFUL)
        maximum = OumiProvider(model="coalm-405b", tier=ModelTier.MAXIMUM)

        assert standard.tier == ModelTier.STANDARD
        assert powerful.tier == ModelTier.POWERFUL
        assert maximum.tier == ModelTier.MAXIMUM
