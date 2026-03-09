"""
HybridLLMRouter - Intelligent LLM routing for TAJINE.

Routes requests between local fast models and powerful cloud models
based on task complexity and trust score.

Routing Strategy:
- Simple tasks + high trust → Local model (fast, free)
- Complex/strategic tasks → Powerful model (reasoning)
- Low trust → Always powerful (validation needed)
- Oumi fine-tuned → When available and appropriate
"""

import re
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from loguru import logger

from src.infrastructure.llm.multi_provider import (
    BaseLLMClient,
    ChatMessage,
    OllamaLLMClient,
    ProviderConfig,
    ProviderType,
)


class TaskComplexity(IntEnum):
    """Task complexity levels for routing decisions."""
    SIMPLE = 1      # Basic queries, lookups
    MODERATE = 2    # Standard analysis, formatting
    COMPLEX = 3     # Multi-step reasoning, analysis
    STRATEGIC = 4   # High-level strategy, causal analysis


@dataclass
class ComplexityAnalysisResult:
    """Result of task complexity analysis."""
    complexity: TaskComplexity
    confidence: float
    features: dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""


@dataclass
class RoutingDecision:
    """Decision on how to route a request."""
    model_type: str  # "local" or "powerful"
    model_name: str
    reasoning: str
    complexity: TaskComplexity
    trust_factor: float
    confidence: float


@dataclass
class RoutingMetrics:
    """Metrics for routing decisions."""
    total_requests: int = 0
    local_count: int = 0
    powerful_count: int = 0
    fallback_count: int = 0
    total_complexity: float = 0.0


class TaskComplexityAnalyzer:
    """
    Analyzes task complexity using heuristics and patterns.

    Uses keyword matching, sentence structure analysis,
    and domain-specific indicators to estimate complexity.
    """

    # Keywords indicating strategic/complex tasks
    STRATEGIC_KEYWORDS = {
        'stratégie', 'strategy', 'stratégique', 'strategic',
        'causal', 'causale', 'causality',
        'scénario', 'scenario', 'scenarios',
        'prospective', 'forecasting', 'projection',
        'investissement', 'investment',
        'théorique', 'theoretical', 'validation',
        'multi-territorial', 'cross-regional',
    }

    COMPLEX_KEYWORDS = {
        'analyse', 'analyze', 'analysis',
        'compare', 'comparison', 'comparer',
        'tendance', 'trend', 'trends',
        'facteur', 'factor', 'factors',
        'impact', 'effet', 'effect',
        'corrélation', 'correlation',
        'potentiel', 'potential',
    }

    SIMPLE_PATTERNS = [
        r'^what is\b',
        r'^qu\'est-ce que\b',
        r'^list\b',
        r'^show\b',
        r'^get\b',
        r'^find\b',
        r'^\d+\s*[\+\-\*\/]\s*\d+',  # Simple math
    ]

    def __init__(self):
        """Initialize the complexity analyzer."""
        self._simple_patterns = [re.compile(p, re.IGNORECASE) for p in self.SIMPLE_PATTERNS]
        logger.debug("TaskComplexityAnalyzer initialized")

    def analyze(self, prompt: str) -> ComplexityAnalysisResult:
        """
        Analyze prompt complexity.

        Args:
            prompt: The task prompt to analyze

        Returns:
            ComplexityAnalysisResult with complexity level and confidence
        """
        prompt_lower = prompt.lower()
        features = self._extract_features(prompt, prompt_lower)

        # Score based on features
        score = self._compute_complexity_score(features)

        # Map score to complexity level
        if score >= 0.6:
            complexity = TaskComplexity.STRATEGIC
        elif score >= 0.4:
            complexity = TaskComplexity.COMPLEX
        elif score >= 0.2:
            complexity = TaskComplexity.MODERATE
        else:
            complexity = TaskComplexity.SIMPLE

        # Compute confidence based on feature clarity
        confidence = min(1.0, 0.6 + features.get('feature_count', 0) * 0.1)

        reasoning = self._build_reasoning(features, complexity)

        return ComplexityAnalysisResult(
            complexity=complexity,
            confidence=confidence,
            features=features,
            reasoning=reasoning
        )

    def _extract_features(self, prompt: str, prompt_lower: str) -> dict[str, Any]:
        """Extract features from prompt for complexity analysis."""
        features = {
            'length': len(prompt),
            'word_count': len(prompt.split()),
            'sentence_count': len(re.split(r'[.!?]+', prompt)),
            'strategic_keywords': 0,
            'complex_keywords': 0,
            'is_simple_pattern': False,
            'has_numbers': bool(re.search(r'\d+', prompt)),
            'has_temporal': bool(re.search(r'(année|year|mois|month|jour|day|futur|future)', prompt_lower)),
            'feature_count': 0,
        }

        # Check for simple patterns
        for pattern in self._simple_patterns:
            if pattern.search(prompt_lower):
                features['is_simple_pattern'] = True
                break

        # Count strategic keywords
        for keyword in self.STRATEGIC_KEYWORDS:
            if keyword in prompt_lower:
                features['strategic_keywords'] += 1

        # Count complex keywords
        for keyword in self.COMPLEX_KEYWORDS:
            if keyword in prompt_lower:
                features['complex_keywords'] += 1

        features['feature_count'] = (
            features['strategic_keywords'] +
            features['complex_keywords'] +
            int(features['has_temporal'])
        )

        return features

    def _compute_complexity_score(self, features: dict[str, Any]) -> float:
        """Compute complexity score from features (0-1)."""
        score = 0.0

        # Simple pattern detection
        if features['is_simple_pattern']:
            return 0.1

        # Length-based scoring
        if features['word_count'] > 50:
            score += 0.15
        elif features['word_count'] > 20:
            score += 0.1

        # Strategic keywords have highest weight
        strategic_count = features['strategic_keywords']
        if strategic_count >= 3:
            score += 0.5  # Strong strategic signal
        elif strategic_count >= 1:
            score += 0.3

        # Complex keywords add moderate weight
        complex_count = features['complex_keywords']
        if complex_count >= 3:
            score += 0.25
        elif complex_count >= 1:
            score += 0.15

        # Temporal reasoning adds complexity
        if features['has_temporal']:
            score += 0.15

        # Multi-sentence adds complexity
        if features['sentence_count'] > 2:
            score += 0.1

        return min(1.0, score)

    def _build_reasoning(
        self,
        features: dict[str, Any],
        complexity: TaskComplexity
    ) -> str:
        """Build reasoning string for the complexity decision."""
        reasons = []

        if features['is_simple_pattern']:
            reasons.append("Matches simple query pattern")

        if features['strategic_keywords'] > 0:
            reasons.append(f"{features['strategic_keywords']} strategic keywords detected")

        if features['complex_keywords'] > 0:
            reasons.append(f"{features['complex_keywords']} complex keywords detected")

        if features['has_temporal']:
            reasons.append("Contains temporal reasoning")

        if not reasons:
            reasons.append("Standard complexity based on length and structure")

        return f"{complexity.name}: {'; '.join(reasons)}"


class OumiClient:
    """
    Client for Oumi.ai fine-tuned models.

    Currently a stub that falls back to Ollama.
    Will be implemented when Oumi integration is ready.
    """

    def __init__(
        self,
        model: str = "coalm-8b",
        base_url: str | None = None,
        fallback_client: BaseLLMClient | None = None
    ):
        """
        Initialize OumiClient.

        Args:
            model: Oumi model name
            base_url: Oumi API base URL
            fallback_client: Client to use when Oumi unavailable
        """
        self.model = model
        self.base_url = base_url
        self._fallback = fallback_client
        self._is_available = False

        logger.info(f"OumiClient initialized (model={model}, stub mode)")

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        fallback_to_ollama: bool = True,
    ) -> str:
        """
        Generate response using Oumi model.

        Args:
            prompt: Input prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            fallback_to_ollama: Use Ollama if Oumi unavailable

        Returns:
            Generated text
        """
        if self._is_available:
            # TODO: Implement real Oumi API call
            pass

        if fallback_to_ollama and self._fallback:
            logger.debug("OumiClient: Falling back to Ollama")
            return await self._fallback.generate(
                messages=[ChatMessage(role="user", content=prompt)],
                temperature=temperature,
                max_tokens=max_tokens,
            )

        # Return stub response
        return f"[Oumi stub response for: {prompt[:50]}...]"

    async def health_check(self) -> bool:
        """Check if Oumi is available."""
        return self._is_available


class HybridLLMRouter:
    """
    Intelligent LLM router for TAJINE.

    Routes requests between:
    - Local model: Fast, free, good for simple tasks
    - Powerful model: Better reasoning, for complex tasks
    - Oumi model: Fine-tuned for territorial intelligence

    Routing factors:
    - Task complexity (detected automatically)
    - Trust score (from TrustManager)
    - Model availability
    - Cost optimization
    """

    # Trust thresholds
    LOW_TRUST_THRESHOLD = 0.3
    HIGH_TRUST_THRESHOLD = 0.7

    # Complexity thresholds for routing
    LOCAL_MAX_COMPLEXITY = TaskComplexity.MODERATE

    def __init__(
        self,
        local_model: str = "qwen3.5:27b",
        powerful_model: str | None = None,
        oumi_model: str = "coalm-8b",
        ollama_base_url: str | None = None,
    ):
        """
        Initialize HybridLLMRouter.

        Args:
            local_model: Fast local model for simple tasks
            powerful_model: Powerful model for complex tasks
            oumi_model: Fine-tuned Oumi model
            ollama_base_url: Ollama API base URL
        """
        import os
        self.local_model = local_model
        self.powerful_model = powerful_model or os.getenv("OLLAMA_MODEL_POWERFUL", local_model)
        self.oumi_model = oumi_model

        # Resolve Ollama URL from env or default
        _ollama_url = ollama_base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        # Initialize clients
        self._local_client = OllamaLLMClient(ProviderConfig(
            provider_type=ProviderType.OLLAMA,
            model=local_model,
            base_url=_ollama_url,
        ))

        self._powerful_client = OllamaLLMClient(ProviderConfig(
            provider_type=ProviderType.OLLAMA,
            model=powerful_model,
            base_url=_ollama_url,
        ))

        self._oumi_client = OumiClient(
            model=oumi_model,
            fallback_client=self._powerful_client
        )

        # Complexity analyzer
        self.complexity_analyzer = TaskComplexityAnalyzer()

        # Metrics
        self._metrics = RoutingMetrics()

        logger.info(
            f"HybridLLMRouter initialized: local={local_model}, "
            f"powerful={powerful_model}, oumi={oumi_model}"
        )

    async def decide_route(
        self,
        prompt: str,
        trust_score: float = 0.5,
        force_complexity: TaskComplexity | None = None,
    ) -> RoutingDecision:
        """
        Decide which model to route the request to.

        Args:
            prompt: The task prompt
            trust_score: Current trust score (0-1)
            force_complexity: Override complexity detection

        Returns:
            RoutingDecision with model selection and reasoning
        """
        # Analyze complexity
        if force_complexity:
            complexity = force_complexity
            analysis_confidence = 1.0
        else:
            analysis = self.complexity_analyzer.analyze(prompt)
            complexity = analysis.complexity
            analysis_confidence = analysis.confidence

        # Decision logic
        reasoning_parts = []

        # Low trust always goes to powerful
        if trust_score < self.LOW_TRUST_THRESHOLD:
            model_type = "powerful"
            reasoning_parts.append(f"Low trust ({trust_score:.2f}) requires powerful model")
        # Strategic tasks always go to powerful
        elif complexity >= TaskComplexity.STRATEGIC:
            model_type = "powerful"
            reasoning_parts.append("Strategic complexity requires powerful model")
        # Complex tasks go to powerful unless high trust
        elif complexity >= TaskComplexity.COMPLEX:
            if trust_score >= self.HIGH_TRUST_THRESHOLD:
                model_type = "local"
                reasoning_parts.append(
                    f"Complex task but high trust ({trust_score:.2f}) allows local"
                )
            else:
                model_type = "powerful"
                reasoning_parts.append("Complex task with moderate trust needs powerful")
        # Simple/moderate tasks go to local
        else:
            model_type = "local"
            reasoning_parts.append(
                f"Simple task ({complexity.name}) routes to local model"
            )

        # Select model name
        model_name = self.local_model if model_type == "local" else self.powerful_model

        reasoning = "; ".join(reasoning_parts)

        return RoutingDecision(
            model_type=model_type,
            model_name=model_name,
            reasoning=reasoning,
            complexity=complexity,
            trust_factor=trust_score,
            confidence=analysis_confidence
        )

    async def generate(
        self,
        prompt: str,
        trust_score: float = 0.5,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        force_model: str | None = None,
        allow_fallback: bool = True,
        include_metadata: bool = False,
    ) -> str | dict[str, Any]:
        """
        Generate response with automatic routing.

        Args:
            prompt: Input prompt
            trust_score: Current trust score
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            force_model: Force specific model ("local", "powerful", "oumi")
            allow_fallback: Allow fallback on failure
            include_metadata: Include routing metadata in response

        Returns:
            Generated text or dict with content and metadata
        """
        self._metrics.total_requests += 1

        # Determine routing
        if force_model:
            if force_model == "powerful":
                client = self._powerful_client
                model_type = "powerful"
            elif force_model == "oumi":
                response = await self._oumi_client.generate(
                    prompt, temperature, max_tokens
                )
                if include_metadata:
                    return {"content": response, "routing": {"model": "oumi"}}
                return response
            else:
                client = self._local_client
                model_type = "local"
            decision = None
        else:
            decision = await self.decide_route(prompt, trust_score)
            if decision.model_type == "local":
                client = self._local_client
                model_type = "local"
                self._metrics.local_count += 1
            else:
                client = self._powerful_client
                model_type = "powerful"
                self._metrics.powerful_count += 1

            self._metrics.total_complexity += decision.complexity.value

        # Generate response
        messages = [ChatMessage(role="user", content=prompt)]

        try:
            response = await client.generate(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.content
        except Exception as e:
            logger.warning(f"Generation failed with {model_type}: {e}")

            if not allow_fallback:
                raise

            # Fallback
            self._metrics.fallback_count += 1
            fallback_client = (
                self._local_client if model_type == "powerful"
                else self._powerful_client
            )

            response = await fallback_client.generate(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.content
            logger.info("Fallback successful")

        if include_metadata:
            return {
                "content": content,
                "routing": {
                    "model_type": model_type,
                    "model_name": client.config.model,
                    "decision": decision.__dict__ if decision else None,
                }
            }

        return content

    async def chat(
        self,
        messages: list[ChatMessage],
        trust_score: float = 0.5,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict[str, Any]] | None = None,
        force_model: str | None = None,
    ) -> dict[str, Any]:
        """
        Chat with automatic routing.

        Args:
            messages: Chat messages
            trust_score: Current trust score
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            tools: Tool definitions
            force_model: Force specific model

        Returns:
            Response dict with content and optional tool_calls
        """
        # Analyze complexity from all messages
        full_prompt = " ".join(m.content for m in messages if m.role != "system")

        if force_model:
            client = (
                self._powerful_client if force_model == "powerful"
                else self._local_client
            )
        else:
            decision = await self.decide_route(full_prompt, trust_score)
            client = (
                self._local_client if decision.model_type == "local"
                else self._powerful_client
            )

        response = await client.generate(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
        )

        return {
            "content": response.content,
            "role": "assistant",
            "tool_calls": response.tool_calls,
        }

    def get_metrics(self) -> dict[str, Any]:
        """Get routing metrics."""
        return {
            "total_requests": self._metrics.total_requests,
            "local_count": self._metrics.local_count,
            "powerful_count": self._metrics.powerful_count,
            "fallback_count": self._metrics.fallback_count,
            "local_ratio": (
                self._metrics.local_count / self._metrics.total_requests
                if self._metrics.total_requests > 0 else 0
            ),
        }

    def get_routing_stats(self) -> dict[str, Any]:
        """Get detailed routing statistics."""
        avg_complexity = (
            self._metrics.total_complexity / self._metrics.total_requests
            if self._metrics.total_requests > 0 else 0
        )

        return {
            "local_count": self._metrics.local_count,
            "powerful_count": self._metrics.powerful_count,
            "avg_complexity": avg_complexity,
            "fallback_rate": (
                self._metrics.fallback_count / self._metrics.total_requests
                if self._metrics.total_requests > 0 else 0
            ),
        }

    async def health_check(self) -> dict[str, bool]:
        """Check health of all models."""
        return {
            "local": await self._local_client.health_check(),
            "powerful": await self._powerful_client.health_check(),
            "oumi": await self._oumi_client.health_check(),
        }

    async def close(self):
        """Close all clients."""
        await self._local_client.close()
        await self._powerful_client.close()
