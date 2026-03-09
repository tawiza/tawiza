"""
CognitiveEngine - 5-level cognitive processing system.

Levels:
1. Discovery - Detect weak signals
2. Causal - Analyze cause-effect relationships
3. Scenario - Generate scenarios
4. Strategy - Recommend actions
5. Theoretical - Validate with theory

Modes:
- Fast: Retourne seulement l'analyse strategy
- Unified: Fusionne les 5 niveaux via UnifiedSynthesizer
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

from loguru import logger

from src.infrastructure.agents.tajine.cognitive.levels import (
    CausalLevel,
    DiscoveryLevel,
    ScenarioLevel,
    StrategyLevel,
    TheoreticalLevel,
)
from src.infrastructure.agents.tajine.cognitive.synthesizer import (
    UnifiedSynthesis,
    UnifiedSynthesizer,
)

if TYPE_CHECKING:
    from src.infrastructure.agents.tajine.cognitive.llm_provider import LLMProvider
    from src.infrastructure.agents.tajine.llm_router import HybridLLMRouter


@dataclass
class CognitiveResult:
    """Result from a cognitive level."""
    level: int
    name: str
    output: dict[str, Any]
    confidence: float


class CognitiveEngine:
    """
    5-level cognitive processing engine.

    Processes execution results through progressively
    higher levels of abstraction and reasoning.

    Supports three modes:
    1. Rule-based: No LLM, uses keyword/pattern analysis
    2. Direct LLM: Uses LLMProvider with fixed model
    3. Routed LLM: Uses HybridLLMRouter for intelligent model selection
    """

    def __init__(
        self,
        llm_provider: Optional['LLMProvider'] = None,
        llm_router: Optional['HybridLLMRouter'] = None
    ):
        """
        Initialize CognitiveEngine with 5 levels.

        Args:
            llm_provider: Optional LLMProvider for AI-powered processing
            llm_router: Optional HybridLLMRouter for intelligent model selection
        """
        self._llm_provider = llm_provider
        self._llm_router = llm_router

        # Create LLMProvider with router if router provided but no provider
        if llm_router and not llm_provider:
            from src.infrastructure.agents.tajine.cognitive.llm_provider import LLMProvider
            llm_provider = LLMProvider(router=llm_router)
            self._llm_provider = llm_provider

        # Initialize levels with optional LLM provider
        self.levels = [
            ("discovery", DiscoveryLevel(llm_provider=llm_provider)),
            ("causal", CausalLevel(llm_provider=llm_provider)),
            ("scenario", ScenarioLevel(llm_provider=llm_provider)),
            ("strategy", StrategyLevel(llm_provider=llm_provider)),
            ("theoretical", TheoreticalLevel(llm_provider=llm_provider)),
        ]

        # Initialize UnifiedSynthesizer
        self._synthesizer = UnifiedSynthesizer(llm_provider=llm_provider)

        if llm_router:
            mode = "routed-LLM"
        elif llm_provider:
            mode = "direct-LLM"
        else:
            mode = "rule-based"
        logger.info(f"CognitiveEngine initialized with 5 levels + UnifiedSynthesizer ({mode} mode)")

    def _assess_data_quality(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        """Assess data quality to determine if real data was collected.

        Returns:
            Dict with has_real_data, data_count, sources, quality_score
        """
        data_count = 0
        sources = set()
        has_sirene = False
        has_bodacc = False

        for r in results:
            result_data = r.get('result', {})
            if not isinstance(result_data, dict):
                continue

            # Check for DataHunter results with real data
            if hunt_data := result_data.get('data'):
                if isinstance(hunt_data, list):
                    data_count += len(hunt_data)
                    for item in hunt_data:
                        if source := item.get('source'):
                            sources.add(source)
                            if 'sirene' in source.lower():
                                has_sirene = True
                            if 'bodacc' in source.lower():
                                has_bodacc = True

            # Check for sources_used metadata
            if src_list := result_data.get('sources_used'):
                sources.update(src_list)

            # Check direct count
            if count := result_data.get('data_count', result_data.get('count')):
                data_count = max(data_count, count)

        # Calculate quality score
        quality_score = 0.0
        if data_count >= 5:
            quality_score += 0.4
        elif data_count >= 1:
            quality_score += 0.2
        if has_sirene:
            quality_score += 0.3
        if has_bodacc:
            quality_score += 0.2
        if len(sources) >= 2:
            quality_score += 0.1

        return {
            'has_real_data': data_count > 0 and len(sources) > 0,
            'data_count': data_count,
            'sources': list(sources),
            'quality_score': min(quality_score, 1.0),
            'has_sirene': has_sirene,
            'has_bodacc': has_bodacc,
        }

    async def process(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Process results through all cognitive levels.

        IMPORTANT: Checks data quality before advancing to higher levels.
        If Discovery finds no real data, Scenario/Strategy levels are flagged.

        Args:
            results: List of execution results

        Returns:
            Synthesis with analysis, confidence, cognitive_levels, data_quality
        """
        # First, assess data quality
        data_quality = self._assess_data_quality(results)
        logger.info(f"Data quality assessment: {data_quality['data_count']} items, sources={data_quality['sources']}, quality={data_quality['quality_score']:.2f}")

        cognitive_outputs = {}
        confidences = []

        for level_num, (name, level) in enumerate(self.levels, 1):
            logger.debug(f"Processing level {level_num}: {name}")

            # Skip or flag advanced levels if no real data
            if name in ('scenario', 'strategy', 'theoretical') and not data_quality['has_real_data']:
                logger.warning(f"Skipping {name} level: insufficient real data (count={data_quality['data_count']})")
                output = {
                    'skipped': True,
                    'reason': 'Insufficient real data from Discovery phase',
                    'data_required': True,
                    'confidence': 0.1,
                }
                cognitive_outputs[name] = output
                confidences.append(0.1)
                continue

            output = await level.process(results, cognitive_outputs)
            cognitive_outputs[name] = output
            confidences.append(output.get('confidence', 0.5))

            # After Discovery, check if we have enough signals
            if name == 'discovery':
                signals = output.get('signals', [])
                if not signals and not data_quality['has_real_data']:
                    logger.warning("Discovery found no signals and no real data - flagging subsequent levels")

        # Aggregate confidence (weighted average, higher levels weighted more)
        weights = [1, 2, 3, 4, 5]
        avg_confidence = sum(c * w for c, w in zip(confidences, weights, strict=False)) / sum(weights)

        # Reduce confidence if data quality is low
        if not data_quality['has_real_data']:
            avg_confidence *= 0.5
            logger.warning(f"Reduced confidence to {avg_confidence:.2f} due to lack of real data")

        return {
            'analysis': cognitive_outputs.get('strategy', {}),
            'confidence': avg_confidence,
            'cognitive_levels': cognitive_outputs,
            'data_quality': data_quality,
        }

    async def process_unified(
        self,
        results: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
        tier_override: str | None = None
    ) -> UnifiedSynthesis:
        """
        Process results through all levels and synthesize into unified response.

        This is the COMPLETE mode that fuses all 5 cognitive levels into
        a structured, coherent response with executive summary and recommendations.

        IMPORTANT: Includes data quality checks to prevent synthetic data in analysis.

        Args:
            results: List of execution results
            context: Optional context (territory, sector, query)
            tier_override: Force specific tier for all LLM calls (e.g., "powerful" for COMPLETE mode)

        Returns:
            UnifiedSynthesis with structured multi-level analysis
        """
        context = context or {}

        # First, assess data quality
        data_quality = self._assess_data_quality(results)
        logger.info(f"[COMPLETE mode] Data quality: {data_quality['data_count']} items from {data_quality['sources']}")

        # Add data quality to context for synthesis
        context['data_quality'] = data_quality

        # If tier_override is specified, reconfigure LLM provider for COMPLETE mode
        if tier_override and self._llm_provider:
            self._llm_provider._tier_override = tier_override
            logger.info(f"[COMPLETE mode] Setting tier_override={tier_override} for all cognitive levels")

        # First, process through all cognitive levels
        cognitive_outputs = {}
        for level_num, (name, level) in enumerate(self.levels, 1):
            logger.debug(f"Processing level {level_num}: {name}")

            # Skip or flag advanced levels if no real data
            if name in ('scenario', 'strategy', 'theoretical') and not data_quality['has_real_data']:
                logger.warning(f"[COMPLETE mode] Flagging {name} level: insufficient real data")
                output = {
                    'skipped': True,
                    'reason': 'Insufficient real data from Discovery phase',
                    'data_required': True,
                    'confidence': 0.1,
                    'warning': 'This level requires real data to produce reliable projections'
                }
                cognitive_outputs[name] = output
                continue

            output = await level.process(results, cognitive_outputs)
            cognitive_outputs[name] = output

        # Add data quality info to cognitive outputs for synthesis
        cognitive_outputs['_data_quality'] = data_quality

        # Then synthesize all levels into unified response
        logger.debug("Synthesizing all cognitive levels")
        synthesis = await self._synthesizer.synthesize(cognitive_outputs, context)

        # Reset tier override after processing
        if tier_override and self._llm_provider:
            self._llm_provider._tier_override = None

        return synthesis

    async def process_level(
        self,
        level_name: str,
        results: list[dict[str, Any]],
        previous: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Process a single cognitive level.

        Useful for FAST mode where only one level is needed.

        Args:
            level_name: Name of the level (discovery, causal, scenario, strategy, theoretical)
            results: List of execution results
            previous: Previous levels outputs (for context)

        Returns:
            Output from the specified level
        """
        previous = previous or {}

        for name, level in self.levels:
            if name == level_name:
                return await level.process(results, previous)

        raise ValueError(f"Unknown cognitive level: {level_name}")
