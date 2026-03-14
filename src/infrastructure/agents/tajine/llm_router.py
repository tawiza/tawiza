"""HybridLLMRouter - Intelligent routing between local and powerful LLMs.

Routes requests between fast local models (Ollama/Qwen) and powerful cloud models
(Oumi.ai CoALM) based on task complexity, trust score, and confidence requirements.

Routing Strategy:
- Simple tasks, high trust → Local Qwen (fast, free)
- Complex reasoning → CoALM 8B/70B (agentic reasoning)
- High uncertainty → CoALM + human validation
- Critical decisions → CoALM 405B (maximum capability)
"""

import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from loguru import logger


class ModelTier(StrEnum):
    """Model capability tiers."""

    LOCAL = "local"  # Ollama local models (fast, free)
    STANDARD = "standard"  # CoALM 8B (balanced)
    POWERFUL = "powerful"  # CoALM 70B (high capability)
    MAXIMUM = "maximum"  # CoALM 405B (maximum capability)


class AnalysisMode(StrEnum):
    """User-selectable analysis modes mapped to model tiers."""

    FAST = "fast"  # Quick response, local model (llama3.1:8b or qwen3.5:27b)
    COMPLETE = "complete"  # Full PPDSL cycle with powerful model (32b+)


# Mode to tier mapping - key for differentiating Fast vs Complet
MODE_TIER_MAPPING: dict[AnalysisMode, ModelTier] = {
    AnalysisMode.FAST: ModelTier.LOCAL,  # qwen3.5:27b
    AnalysisMode.COMPLETE: ModelTier.POWERFUL,  # qwen3.5:27b or coalm-70b
}


# Ollama model mapping by tier
# Note: qwen3.5:27b used for LOCAL tier - llama3.1:8b was too restrictive
# (refused legitimate queries about "radiations" = business cessations)
OLLAMA_MODEL_BY_TIER: dict[ModelTier, str] = {
    ModelTier.LOCAL: "qwen3.5:27b",  # Fast streaming (mode rapide) - optimized prompt
    ModelTier.STANDARD: "qwen3.5:27b",  # Standard reasoning
    ModelTier.POWERFUL: "qwen3.5:27b",  # Complex analysis (mode complet) - 31 tok/s
    ModelTier.MAXIMUM: "qwen3.5:27b",  # Maximum capability - 31 tok/s on RX 7900 XTX
}

# Vision model for captcha solving, screenshots, computer use
OLLAMA_VISION_MODEL: str = "qwen3-vl:8b"  # 89 tok/s on RX 7900 XTX


class TaskComplexity(StrEnum):
    """Task complexity levels."""

    SIMPLE = "simple"  # Direct answer, no reasoning needed
    MODERATE = "moderate"  # Some reasoning, single step
    COMPLEX = "complex"  # Multi-step reasoning
    CRITICAL = "critical"  # High-stakes decision


@dataclass
class RoutingDecision:
    """Decision about which model to use."""

    tier: ModelTier
    model_name: str
    reason: str
    confidence: float
    fallback_tier: ModelTier | None = None
    requires_validation: bool = False


@dataclass
class LLMRequest:
    """Request to an LLM."""

    prompt: str
    system_prompt: str | None = None
    context: dict[str, Any] | None = None
    complexity: TaskComplexity = TaskComplexity.MODERATE
    trust_score: float = 0.5  # 0.0 to 1.0
    confidence_required: float = 0.7
    max_tokens: int = 2048
    temperature: float = 0.7
    task_type: str | None = None
    tier_override: ModelTier | None = None  # Force a specific tier (for COMPLETE mode)


@dataclass
class LLMResponse:
    """Response from an LLM."""

    content: str
    model_used: str
    tier_used: ModelTier
    tokens_used: int
    latency_ms: float
    confidence: float
    routing_decision: RoutingDecision
    metadata: dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    """Abstract LLM provider interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    @property
    @abstractmethod
    def tier(self) -> ModelTier:
        """Provider tier."""
        pass

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs,
    ) -> dict[str, Any]:
        """Generate response."""
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if provider is available."""
        pass


class OllamaProvider(LLMProvider):
    """Ollama local model provider."""

    def __init__(self, model: str = "qwen3.5:27b", host: str = "http://localhost:11434"):
        self._model = model
        self._host = host
        self._client = None

    @property
    def name(self) -> str:
        return f"ollama/{self._model}"

    @property
    def tier(self) -> ModelTier:
        return ModelTier.LOCAL

    async def _get_client(self):
        if self._client is None:
            from src.infrastructure.llm.ollama_client import OllamaClient

            self._client = OllamaClient(model=self._model, base_url=self._host)
        return self._client

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs,
    ) -> dict[str, Any]:
        client = await self._get_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        start = time.time()
        response = await client.chat(
            messages=messages, max_tokens=max_tokens, temperature=temperature
        )
        latency = (time.time() - start) * 1000

        # OllamaClient.chat() returns {"content": ..., "tool_calls": ..., ...}
        return {
            "content": response.get("content", ""),
            "tokens": response.get("eval_count", 0),
            "latency_ms": latency,
            "model": self._model,
        }

    async def is_available(self) -> bool:
        try:
            client = await self._get_client()
            return await client.is_available()
        except Exception:
            return False


class OumiProvider(LLMProvider):
    """Oumi.ai CoALM provider."""

    def __init__(
        self,
        model: str = "coalm-8b",
        api_key: str | None = None,
        tier: ModelTier = ModelTier.STANDARD,
    ):
        self._model = model
        self._api_key = api_key
        self._tier = tier
        self._available = True  # Assume available, check lazily

    @property
    def name(self) -> str:
        return f"oumi/{self._model}"

    @property
    def tier(self) -> ModelTier:
        return self._tier

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs,
    ) -> dict[str, Any]:
        """Generate using Oumi.ai API.

        Note: This is a placeholder. Real implementation would use the Oumi SDK:
        https://github.com/oumi-ai/oumi
        """
        # Placeholder - in production, use oumi SDK
        logger.info(f"Oumi generate called with model {self._model}")

        # Fallback to Ollama for now (TODO: integrate real Oumi SDK)
        ollama = OllamaProvider(model="qwen3.5:27b")
        return await ollama.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    async def is_available(self) -> bool:
        return self._available


class HybridLLMRouter:
    """Intelligent router between local and cloud LLM providers.

    Routing Logic:
    1. Assess task complexity and trust score
    2. Select appropriate tier
    3. Check provider availability
    4. Execute with fallback support
    5. Track metrics for continuous improvement

    Example:
        router = HybridLLMRouter()

        response = await router.route(LLMRequest(
            prompt="Analyze the tech sector in Nouvelle-Aquitaine",
            complexity=TaskComplexity.COMPLEX,
            trust_score=0.8,
            confidence_required=0.85
        ))
    """

    def __init__(
        self,
        local_provider: LLMProvider | None = None,
        standard_provider: LLMProvider | None = None,
        powerful_provider: LLMProvider | None = None,
        maximum_provider: LLMProvider | None = None,
        ollama_host: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    ):
        """Initialize router with providers.

        Args:
            local_provider: Local model provider (default: Ollama/Qwen)
            standard_provider: Standard cloud provider (default: CoALM 8B)
            powerful_provider: Powerful cloud provider (default: CoALM 70B)
            maximum_provider: Maximum capability provider (default: CoALM 405B)
            ollama_host: Ollama server host
        """
        self._providers: dict[ModelTier, LLMProvider] = {}

        # Set up providers
        # All tiers use Ollama qwen3.5:27b until cloud providers are configured
        _default_ollama = OllamaProvider(model="qwen3.5:27b", host=ollama_host)
        self._providers[ModelTier.LOCAL] = local_provider or _default_ollama
        self._providers[ModelTier.STANDARD] = standard_provider or _default_ollama
        self._providers[ModelTier.POWERFUL] = powerful_provider or _default_ollama
        self._providers[ModelTier.MAXIMUM] = maximum_provider or _default_ollama

        # Metrics tracking
        self._request_count = 0
        self._tier_usage: dict[ModelTier, int] = dict.fromkeys(ModelTier, 0)
        self._fallback_count = 0
        self._total_latency_ms = 0.0

    async def route(self, request: LLMRequest) -> LLMResponse:
        """Route request to appropriate LLM provider.

        Args:
            request: LLM request with complexity and requirements

        Returns:
            LLMResponse with generated content and metadata
        """
        self._request_count += 1

        # 1. Decide routing
        decision = self._make_routing_decision(request)
        logger.debug(
            f"Routing decision: {decision.tier.value} ({decision.model_name}) - {decision.reason}"
        )

        # 2. Try primary provider
        primary_provider = self._providers[decision.tier]
        response = await self._try_provider(primary_provider, request, decision)

        if response:
            self._tier_usage[decision.tier] += 1
            return response

        # 3. Try fallback if available
        if decision.fallback_tier:
            logger.warning(
                f"Primary provider {decision.tier.value} failed, "
                f"trying fallback {decision.fallback_tier.value}"
            )
            self._fallback_count += 1

            fallback_provider = self._providers[decision.fallback_tier]
            fallback_decision = RoutingDecision(
                tier=decision.fallback_tier,
                model_name=fallback_provider.name,
                reason=f"Fallback from {decision.tier.value}",
                confidence=decision.confidence * 0.9,
                requires_validation=True,
            )

            response = await self._try_provider(fallback_provider, request, fallback_decision)
            if response:
                self._tier_usage[decision.fallback_tier] += 1
                return response

        # 4. All failed - return error response
        logger.error("All providers failed")
        return LLMResponse(
            content="Error: All LLM providers unavailable",
            model_used="none",
            tier_used=ModelTier.LOCAL,
            tokens_used=0,
            latency_ms=0,
            confidence=0.0,
            routing_decision=decision,
            metadata={"error": "All providers failed"},
        )

    def _make_routing_decision(self, request: LLMRequest) -> RoutingDecision:
        """Determine which tier to use based on request parameters.

        Routing rules:
        0. If tier_override is set → use that tier (COMPLETE mode)
        1. Simple task + high trust → LOCAL
        2. Moderate task + medium trust → STANDARD
        3. Complex task → POWERFUL
        4. Critical task or low trust → MAXIMUM
        5. High confidence required → upgrade tier
        """
        # Check for tier override first (COMPLETE mode forces POWERFUL tier)
        if request.tier_override is not None:
            base_tier = request.tier_override
            logger.info(f"Using tier override: {base_tier.value}")
            provider = self._providers[base_tier]
            return RoutingDecision(
                tier=base_tier,
                model_name=provider.name,
                reason=f"Tier override requested ({base_tier.value})",
                confidence=self._estimate_confidence(base_tier, request.complexity),
                fallback_tier=self._downgrade_tier(base_tier)
                if base_tier != ModelTier.LOCAL
                else None,
                requires_validation=False,
            )

        complexity = request.complexity
        trust = request.trust_score
        confidence_needed = request.confidence_required

        # Base tier from complexity
        if complexity == TaskComplexity.SIMPLE:
            base_tier = ModelTier.LOCAL
        elif complexity == TaskComplexity.MODERATE:
            base_tier = ModelTier.STANDARD
        elif complexity == TaskComplexity.COMPLEX:
            base_tier = ModelTier.POWERFUL
        else:  # CRITICAL
            base_tier = ModelTier.MAXIMUM

        # Adjust for trust score
        if trust < 0.3:
            # Low trust - upgrade tier for validation
            base_tier = self._upgrade_tier(base_tier)
        elif trust > 0.8 and complexity != TaskComplexity.CRITICAL:
            # High trust - can use lower tier
            base_tier = self._downgrade_tier(base_tier)

        # Adjust for confidence requirement
        if confidence_needed > 0.9 and base_tier != ModelTier.MAXIMUM:
            base_tier = self._upgrade_tier(base_tier)

        # Determine fallback
        fallback = self._downgrade_tier(base_tier)
        if fallback == base_tier:
            fallback = None

        # Build decision
        provider = self._providers[base_tier]
        return RoutingDecision(
            tier=base_tier,
            model_name=provider.name,
            reason=self._build_reason(complexity, trust, confidence_needed),
            confidence=self._estimate_confidence(base_tier, complexity),
            fallback_tier=fallback,
            requires_validation=trust < 0.5 or complexity == TaskComplexity.CRITICAL,
        )

    def _upgrade_tier(self, tier: ModelTier) -> ModelTier:
        """Upgrade to next tier."""
        order = [ModelTier.LOCAL, ModelTier.STANDARD, ModelTier.POWERFUL, ModelTier.MAXIMUM]
        idx = order.index(tier)
        return order[min(idx + 1, len(order) - 1)]

    def _downgrade_tier(self, tier: ModelTier) -> ModelTier:
        """Downgrade to previous tier."""
        order = [ModelTier.LOCAL, ModelTier.STANDARD, ModelTier.POWERFUL, ModelTier.MAXIMUM]
        idx = order.index(tier)
        return order[max(idx - 1, 0)]

    def _build_reason(self, complexity: TaskComplexity, trust: float, confidence: float) -> str:
        """Build human-readable routing reason."""
        parts = []

        if complexity == TaskComplexity.SIMPLE:
            parts.append("Simple task")
        elif complexity == TaskComplexity.MODERATE:
            parts.append("Moderate complexity")
        elif complexity == TaskComplexity.COMPLEX:
            parts.append("Complex reasoning needed")
        else:
            parts.append("Critical decision")

        if trust > 0.8:
            parts.append("high trust")
        elif trust < 0.3:
            parts.append("low trust - needs validation")
        else:
            parts.append(f"trust={trust:.1f}")

        if confidence > 0.9:
            parts.append("high confidence required")

        return ", ".join(parts)

    def _estimate_confidence(self, tier: ModelTier, complexity: TaskComplexity) -> float:
        """Estimate expected confidence from tier/complexity combination."""
        # Base confidence by tier
        tier_confidence = {
            ModelTier.LOCAL: 0.7,
            ModelTier.STANDARD: 0.8,
            ModelTier.POWERFUL: 0.9,
            ModelTier.MAXIMUM: 0.95,
        }

        # Reduce for higher complexity
        complexity_penalty = {
            TaskComplexity.SIMPLE: 0.0,
            TaskComplexity.MODERATE: 0.05,
            TaskComplexity.COMPLEX: 0.1,
            TaskComplexity.CRITICAL: 0.15,
        }

        base = tier_confidence[tier]
        penalty = complexity_penalty[complexity]

        return max(0.5, base - penalty)

    async def _try_provider(
        self, provider: LLMProvider, request: LLMRequest, decision: RoutingDecision
    ) -> LLMResponse | None:
        """Try to get response from a provider.

        Returns None if provider fails.
        """
        try:
            # Check availability
            if not await provider.is_available():
                logger.warning(f"Provider {provider.name} not available")
                return None

            # Generate
            start = time.time()
            result = await provider.generate(
                prompt=request.prompt,
                system_prompt=request.system_prompt,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
            )
            latency = (time.time() - start) * 1000

            self._total_latency_ms += latency

            return LLMResponse(
                content=result["content"],
                model_used=result.get("model", provider.name),
                tier_used=decision.tier,
                tokens_used=result.get("tokens", 0),
                latency_ms=latency,
                confidence=decision.confidence,
                routing_decision=decision,
                metadata={
                    "provider": provider.name,
                    "requires_validation": decision.requires_validation,
                },
            )

        except Exception as e:
            logger.error(f"Provider {provider.name} failed: {e}")
            return None

    def get_metrics(self) -> dict[str, Any]:
        """Get router metrics."""
        return {
            "total_requests": self._request_count,
            "tier_usage": {t.value: c for t, c in self._tier_usage.items()},
            "fallback_count": self._fallback_count,
            "fallback_rate": (
                self._fallback_count / self._request_count if self._request_count > 0 else 0
            ),
            "avg_latency_ms": (
                self._total_latency_ms / self._request_count if self._request_count > 0 else 0
            ),
        }

    def get_tier_for_mode(self, mode: str) -> ModelTier:
        """Map analysis mode string to model tier.

        This method provides a clean interface for mode-to-tier mapping
        that is used by the TAJINE agent to select appropriate models.

        Mapping:
        - rapide/fast → LOCAL (8b models, quick responses)
        - standard → STANDARD (14b models, balanced)
        - complet/complete → POWERFUL (32b+ models, comprehensive)
        - expert → MAXIMUM (70b+ models, maximum capability)

        Args:
            mode: Analysis mode string (case-insensitive)

        Returns:
            Appropriate ModelTier for the mode
        """
        mode_lower = mode.lower()

        mode_mapping = {
            # French mode names
            "rapide": ModelTier.LOCAL,
            "complet": ModelTier.POWERFUL,
            "expert": ModelTier.MAXIMUM,
            "standard": ModelTier.STANDARD,
            # English aliases
            "fast": ModelTier.LOCAL,
            "complete": ModelTier.POWERFUL,
            "quick": ModelTier.LOCAL,
        }

        tier = mode_mapping.get(mode_lower, ModelTier.STANDARD)
        logger.debug(f"Mode '{mode}' → tier={tier.value}")
        return tier


# ============================================================================
# Factory Functions
# ============================================================================


def get_model_for_mode(
    mode: str, ollama_host: str = "http://localhost:11434"
) -> tuple[str, ModelTier]:
    """Get the appropriate Ollama model name and tier for an analysis mode.

    This is the KEY function that differentiates Fast vs Complet mode!

    Args:
        mode: "fast" or "complete"
        ollama_host: Ollama server URL (for validation)

    Returns:
        tuple of (model_name, tier)

    Example:
        >>> model, tier = get_model_for_mode("fast")
        >>> print(model, tier)
        llama3.1:8b ModelTier.LOCAL

        >>> model, tier = get_model_for_mode("complete")
        >>> print(model, tier)
        qwen3.5:27b ModelTier.POWERFUL
    """
    try:
        analysis_mode = AnalysisMode(mode.lower())
    except ValueError:
        logger.warning(f"Unknown mode '{mode}', defaulting to FAST")
        analysis_mode = AnalysisMode.FAST

    tier = MODE_TIER_MAPPING[analysis_mode]
    model = OLLAMA_MODEL_BY_TIER[tier]

    logger.info(f"Mode '{mode}' → tier={tier.value}, model={model}")
    return model, tier


def create_hybrid_router(
    local_model: str = "qwen3.5:27b",
    ollama_host: str = "http://localhost:11434",
    oumi_api_key: str | None = None,
) -> HybridLLMRouter:
    """Create a HybridLLMRouter with default configuration.

    Args:
        local_model: Ollama model for local inference
        ollama_host: Ollama server host
        oumi_api_key: Optional Oumi.ai API key

    Returns:
        Configured HybridLLMRouter
    """
    # All tiers use Ollama until cloud providers (Oumi) are configured
    ollama = OllamaProvider(model=local_model, host=ollama_host)
    return HybridLLMRouter(
        local_provider=ollama,
        standard_provider=ollama,
        powerful_provider=ollama,
        maximum_provider=ollama,
        ollama_host=ollama_host,
    )
