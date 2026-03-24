"""
LLMProvider - Wrapper for LLM clients for cognitive processing.

Provides:
- Text generation with system prompts
- JSON extraction from LLM responses
- Graceful error handling
- Cognitive-specific prompts for each level
- HybridLLMRouter integration for intelligent model selection
"""

import json
import re
from typing import TYPE_CHECKING, Any, Optional

from loguru import logger

if TYPE_CHECKING:
    from src.infrastructure.agents.tajine.llm_router import HybridLLMRouter


# Cognitive level prompts for territorial intelligence
COGNITIVE_PROMPTS = {
    "discovery": """You are analyzing territorial economic data to detect weak signals and emerging patterns.

Given the following execution results, identify:
1. Growth/decline signals (type, description, strength 0-1, source)
2. Anomalies (unusual concentrations, outliers)
3. Emerging patterns (clusters, trends)

Results to analyze:
{results}

Previous context (if any):
{previous}

Respond in JSON format:
```json
{
  "signals": [{"type": "growth|decline|concentration", "description": "...", "strength": 0.0-1.0, "source": "..."}],
  "patterns": [{"name": "...", "description": "...", "confidence": 0.0-1.0}],
  "confidence": 0.0-1.0
}
```""",
    "causal": """You are analyzing cause-effect relationships in territorial economic data.

Given the discovered signals and patterns, identify:
1. Contributing factors (what causes these signals)
2. Potential effects (what outcomes will result)
3. Causal chains (A causes B which causes C)

Discovery results:
{discovery}

Original data:
{results}

Respond in JSON format:
```json
{
  "causes": [{"factor": "...", "contribution": 0.0-1.0, "evidence": "..."}],
  "effects": [{"outcome": "...", "magnitude": "low|medium|high", "timeframe": "..."}],
  "causal_chains": ["A -> B -> C"],
  "confidence": 0.0-1.0
}
```""",
    "scenario": """You are generating future scenarios for territorial economic development.

Based on the causal analysis, generate three scenarios:
1. Optimistic (best case, 20% probability)
2. Median (most likely, 60% probability)
3. Pessimistic (worst case, 20% probability)

Causal analysis:
{causal}

Previous levels:
{previous}

Respond in JSON format:
```json
{
  "optimistic": {"growth_rate": 0.0-1.0, "probability": 0.2, "key_assumptions": ["..."], "description": "..."},
  "median": {"growth_rate": 0.0-1.0, "probability": 0.6, "key_assumptions": ["..."], "description": "..."},
  "pessimistic": {"growth_rate": 0.0-1.0, "probability": 0.2, "key_assumptions": ["..."], "description": "..."},
  "confidence": 0.0-1.0
}
```""",
    "strategy": """You are recommending strategic actions for territorial development.

Based on the scenario analysis, recommend:
1. Immediate actions (0-6 months)
2. Medium-term strategies (6-24 months)
3. Long-term investments (2-5 years)
4. Risk mitigation measures

Scenarios:
{scenarios}

All previous analysis:
{previous}

Respond in JSON format:
```json
{
  "immediate_actions": [{"action": "...", "priority": "high|medium|low", "impact": "..."}],
  "medium_term": [{"strategy": "...", "resources_needed": "...", "expected_outcome": "..."}],
  "long_term": [{"investment": "...", "rationale": "...", "roi_estimate": "..."}],
  "risk_mitigation": [{"risk": "...", "mitigation": "...", "probability": 0.0-1.0}],
  "confidence": 0.0-1.0
}
```""",
    "theoretical": """You are validating the analysis against established economic theories.

Evaluate the strategic recommendations against:
1. Porter's competitive advantage theory
2. Regional development theory (clusters, agglomeration)
3. Innovation ecosystem theory
4. Economic geography principles

Strategy recommendations:
{strategy}

Full analysis chain:
{previous}

Respond in JSON format:
```json
{
  "theory_validations": [
    {"theory": "porter_competitive", "alignment": 0.0-1.0, "notes": "..."},
    {"theory": "regional_clusters", "alignment": 0.0-1.0, "notes": "..."},
    {"theory": "innovation_ecosystem", "alignment": 0.0-1.0, "notes": "..."}
  ],
  "theoretical_confidence": 0.0-1.0,
  "recommendations_validated": true,
  "caveats": ["..."],
  "confidence": 0.0-1.0
}
```""",
}


class LLMProvider:
    """
    Wrapper for LLM clients for cognitive processing.

    Supports two modes:
    1. Direct OllamaClient for simple, fast execution
    2. HybridLLMRouter for intelligent model selection based on complexity

    Provides structured generation with JSON extraction and
    graceful error handling for when LLM is unavailable.
    """

    # Map cognitive levels to task complexity
    LEVEL_COMPLEXITY = {
        "discovery": "moderate",
        "causal": "moderate",
        "scenario": "complex",
        "strategy": "complex",
        "theoretical": "critical",
    }

    def __init__(
        self,
        model: str = "qwen3.5:27b",
        base_url: str = "http://localhost:11434",
        client: Any | None = None,
        router: Optional["HybridLLMRouter"] = None,
        timeout: int = 120,
        tier_override: str | None = None,  # Force specific tier for all calls (COMPLETE mode)
    ):
        """
        Initialize LLMProvider.

        Args:
            model: Ollama model name (used when router is None)
            base_url: Ollama API base URL
            client: Optional pre-configured OllamaClient
            router: Optional HybridLLMRouter for intelligent model selection
            timeout: Request timeout in seconds
            tier_override: Force a specific tier for all calls ("local", "standard", "powerful", "maximum")
        """
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self._client = client
        self._router = router
        self._initialized = False
        self._tier_override = tier_override

        mode = "router" if router else "direct"
        tier_msg = f", tier_override={tier_override}" if tier_override else ""
        logger.debug(f"LLMProvider created with model={model}, mode={mode}{tier_msg}")

    async def _ensure_client(self) -> bool:
        """Ensure Ollama client is initialized."""
        if self._client is not None:
            return True

        try:
            from src.infrastructure.llm.ollama_client import OllamaClient

            self._client = OllamaClient(
                base_url=self.base_url, model=self.model, timeout=self.timeout
            )
            self._initialized = True
            logger.info("LLMProvider initialized with OllamaClient")
            return True
        except ImportError as e:
            logger.warning(f"OllamaClient import failed: {e}")
            return False
        except Exception as e:
            logger.warning(f"OllamaClient initialization failed: {e}")
            return False

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.7,
        complexity: str | None = None,
        **kwargs,  # Accept extra args like task_type for compatibility
    ) -> str:
        """
        Generate text completion.

        Args:
            prompt: User prompt
            system: Optional system prompt
            temperature: Sampling temperature
            complexity: Optional complexity hint for router (simple/moderate/complex/critical)

        Returns:
            Generated text or empty string on error
        """
        # Use router if available
        if self._router is not None:
            try:
                from src.infrastructure.agents.tajine.llm_router import (
                    LLMRequest,
                    ModelTier,
                    TaskComplexity,
                )

                # Map string complexity to enum
                complexity_map = {
                    "simple": TaskComplexity.SIMPLE,
                    "moderate": TaskComplexity.MODERATE,
                    "complex": TaskComplexity.COMPLEX,
                    "critical": TaskComplexity.CRITICAL,
                }
                task_complexity = complexity_map.get(
                    complexity or "moderate", TaskComplexity.MODERATE
                )

                # Build full prompt with system
                full_prompt = prompt
                if system:
                    full_prompt = f"{system}\n\n{prompt}"

                # Handle tier override (COMPLETE mode forces POWERFUL tier)
                tier_override_enum = None
                if self._tier_override:
                    tier_map = {
                        "local": ModelTier.LOCAL,
                        "standard": ModelTier.STANDARD,
                        "powerful": ModelTier.POWERFUL,
                        "maximum": ModelTier.MAXIMUM,
                    }
                    tier_override_enum = tier_map.get(self._tier_override.lower())
                    if tier_override_enum:
                        logger.info(
                            f"[COMPLETE mode] Forcing tier={tier_override_enum.value} for cognitive processing"
                        )

                request = LLMRequest(
                    prompt=full_prompt,
                    complexity=task_complexity,
                    tier_override=tier_override_enum,  # Pass tier override to router
                )

                response = await self._router.route(request)
                logger.debug(
                    f"Router used {response.tier_used.value} tier "
                    f"(latency={response.latency_ms:.0f}ms)"
                )
                return response.content

            except Exception as e:
                logger.warning(f"Router generation failed, falling back: {e}")

        # Fallback to direct client
        if not await self._ensure_client():
            return ""

        try:
            result = await self._client.generate(
                prompt=prompt, system=system, temperature=temperature
            )
            return result if result else ""
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return ""

    async def generate_json(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.3,  # Lower temp for structured output
        complexity: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate and parse JSON response.

        Args:
            prompt: User prompt requesting JSON output
            system: Optional system prompt
            temperature: Sampling temperature (lower for JSON)
            complexity: Optional complexity hint for router

        Returns:
            Parsed JSON dict or empty dict on error
        """
        response = await self.generate(prompt, system, temperature, complexity)

        if not response:
            return {}

        return self._extract_json(response)

    def _extract_json(self, text: str) -> dict[str, Any]:
        """
        Extract JSON from text, handling markdown code blocks.

        Args:
            text: Raw LLM response

        Returns:
            Parsed JSON dict or empty dict
        """
        # Try to find JSON in markdown code blocks
        json_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
        if json_match:
            text = json_match.group(1).strip()

        # Try direct JSON parsing
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to find JSON object in text
        brace_match = re.search(r"\{[\s\S]*\}", text)
        if brace_match:
            try:
                return json.loads(brace_match.group())
            except json.JSONDecodeError:
                pass

        logger.warning(f"Failed to extract JSON from response: {text[:100]}...")
        return {}

    def get_prompt(self, level: str) -> str:
        """
        Get cognitive prompt for a specific level.

        Args:
            level: Cognitive level name (discovery, causal, etc.)

        Returns:
            Prompt template string
        """
        return COGNITIVE_PROMPTS.get(level, "")

    async def process_level(
        self, level: str, results: Any, previous: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Process a cognitive level using LLM.

        Uses HybridLLMRouter when available to select appropriate model:
        - discovery/causal: MODERATE complexity → LOCAL or STANDARD model
        - scenario/strategy: COMPLEX complexity → POWERFUL model
        - theoretical: CRITICAL complexity → POWERFUL or MAXIMUM model

        Args:
            level: Cognitive level name
            results: Execution results
            previous: Previous level outputs

        Returns:
            LLM-generated analysis or empty dict
        """
        prompt_template = self.get_prompt(level)
        if not prompt_template:
            logger.warning(f"No prompt template for level: {level}")
            return {}

        # Format prompt using str.replace() to avoid conflicts with JSON braces
        # (.format() would try to substitute {causes}, {signals}, etc. as placeholders)
        prompt = prompt_template
        if level == "discovery":
            prompt = prompt.replace("{results}", json.dumps(results, indent=2))
            prompt = prompt.replace("{previous}", json.dumps(previous, indent=2))
        elif level == "causal":
            prompt = prompt.replace(
                "{discovery}", json.dumps(previous.get("discovery", {}), indent=2)
            )
            prompt = prompt.replace("{results}", json.dumps(results, indent=2))
        elif level == "scenario":
            prompt = prompt.replace("{causal}", json.dumps(previous.get("causal", {}), indent=2))
            prompt = prompt.replace("{previous}", json.dumps(previous, indent=2))
        elif level == "strategy":
            prompt = prompt.replace(
                "{scenarios}", json.dumps(previous.get("scenario", {}), indent=2)
            )
            prompt = prompt.replace("{previous}", json.dumps(previous, indent=2))
        elif level == "theoretical":
            prompt = prompt.replace(
                "{strategy}", json.dumps(previous.get("strategy", {}), indent=2)
            )
            prompt = prompt.replace("{previous}", json.dumps(previous, indent=2))

        system = "You are an expert in territorial economic analysis and intelligence."

        # Get complexity for this cognitive level
        complexity = self.LEVEL_COMPLEXITY.get(level, "moderate")
        logger.debug(f"Processing cognitive level '{level}' with complexity={complexity}")

        return await self.generate_json(prompt, system, complexity=complexity)
