"""SAFLA MetaCognitive Adapter for TAJINE.

Bridges SAFLA's MetaCognitiveEngine with TAJINE's reasoning and learning:
- Self-awareness of system state and performance
- Adaptive strategy selection based on task characteristics
- Learning from execution outcomes
- Goal management and performance monitoring

This enables TAJINE to:
1. Adapt its approach based on past performance
2. Select optimal strategies for different task types
3. Monitor and improve its own effectiveness
4. Set and track goals for territorial analyses
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from safla.core.metacognitive import MetaCognitiveEngine


class TaskComplexity(StrEnum):
    """Task complexity levels for strategy selection."""

    SIMPLE = "simple"  # Direct data retrieval
    MODERATE = "moderate"  # Multi-source aggregation
    COMPLEX = "complex"  # Deep analysis with reasoning
    EXPERT = "expert"  # Multi-level cognitive processing


class StrategyType(StrEnum):
    """Strategy types for TAJINE operations."""

    FAST_LOOKUP = "fast_lookup"  # Quick cached response
    DATA_HUNT = "data_hunt"  # Active data collection
    DEEP_ANALYSIS = "deep_analysis"  # Full cognitive processing
    COLLABORATIVE = "collaborative"  # Multi-agent approach
    FALLBACK = "fallback"  # Degraded mode with cached data


@dataclass
class PerformanceMetrics:
    """Performance metrics for a task execution."""

    task_id: str
    duration_ms: float
    success: bool
    confidence: float
    data_sources_used: int
    cache_hit: bool
    strategy_used: StrategyType
    timestamp: datetime = field(default_factory=datetime.now)
    error_message: str | None = None


@dataclass
class StrategicInsight:
    """Insight from metacognitive analysis."""

    recommendation: str
    confidence: float
    rationale: str
    suggested_strategy: StrategyType
    estimated_duration_ms: int
    risk_factors: list[str] = field(default_factory=list)


class SAFLAMetaCognitiveAdapter:
    """Adapter bridging SAFLA's metacognitive engine with TAJINE.

    Provides self-awareness, strategy selection, and learning capabilities
    to enhance TAJINE's reasoning and decision-making.
    """

    def __init__(self):
        """Initialize the metacognitive adapter."""
        self._engine: MetaCognitiveEngine | None = None
        self._initialized = False

        # Performance history for learning
        self._performance_history: list[PerformanceMetrics] = []
        self._strategy_success_rates: dict[StrategyType, dict[str, float]] = {
            strategy: {"successes": 0, "total": 0, "avg_duration": 0} for strategy in StrategyType
        }

        # Current system state
        self._current_load = 0.0
        self._active_tasks = 0

        logger.info("SAFLAMetaCognitiveAdapter initialized")

    async def initialize(self) -> None:
        """Initialize the SAFLA metacognitive engine."""
        if self._initialized:
            return

        try:
            from safla.core.metacognitive import MetaCognitiveEngine

            self._engine = MetaCognitiveEngine()
            await self._engine.start()

            self._initialized = True
            logger.info("SAFLA metacognitive engine initialized")

        except ImportError as e:
            logger.warning(f"SAFLA metacognitive not available: {e}")
            self._engine = None
            self._initialized = True
        except Exception as e:
            logger.warning(f"Failed to initialize metacognitive engine: {e}")
            self._engine = None
            self._initialized = True

    async def get_strategic_insight(
        self,
        query: str,
        context: dict[str, Any] | None = None,
        available_sources: list[str] | None = None,
    ) -> StrategicInsight:
        """Get strategic insight for how to approach a task.

        Analyzes the query and context to recommend the best strategy,
        estimated duration, and potential risks.

        Args:
            query: The user's query
            context: Additional context (territory, sector, etc.)
            available_sources: Available data sources

        Returns:
            Strategic insight with recommendations
        """
        await self.initialize()

        context = context or {}
        available_sources = available_sources or []

        # Analyze query complexity
        complexity = self._assess_complexity(query, context)

        # Determine best strategy based on history and current state
        strategy = await self._select_strategy(complexity, context)

        # Estimate duration based on history
        estimated_duration = self._estimate_duration(strategy, complexity)

        # Identify risk factors
        risks = self._identify_risks(query, context, strategy)

        # Generate rationale
        rationale = self._generate_rationale(complexity, strategy, context)

        insight = StrategicInsight(
            recommendation=f"Use {strategy.value} strategy for this {complexity.value} task",
            confidence=self._calculate_confidence(strategy, complexity),
            rationale=rationale,
            suggested_strategy=strategy,
            estimated_duration_ms=estimated_duration,
            risk_factors=risks,
        )

        logger.debug(f"Strategic insight: {strategy.value} for '{query[:50]}...'")
        return insight

    async def record_performance(self, metrics: PerformanceMetrics) -> None:
        """Record task performance for learning.

        Updates strategy success rates and performance history
        to improve future recommendations.

        Args:
            metrics: Performance metrics from task execution
        """
        await self.initialize()

        # Add to history
        self._performance_history.append(metrics)

        # Keep history bounded
        if len(self._performance_history) > 1000:
            self._performance_history = self._performance_history[-500:]

        # Update strategy stats
        stats = self._strategy_success_rates[metrics.strategy_used]
        stats["total"] += 1
        if metrics.success:
            stats["successes"] += 1

        # Update rolling average duration
        old_avg = stats["avg_duration"]
        stats["avg_duration"] = old_avg * 0.9 + metrics.duration_ms * 0.1

        # If SAFLA engine available, let it learn
        if self._engine is not None:
            try:
                await self._engine.record_outcome(
                    task_id=metrics.task_id,
                    success=metrics.success,
                    metrics={
                        "duration_ms": metrics.duration_ms,
                        "confidence": metrics.confidence,
                        "strategy": metrics.strategy_used.value,
                    },
                )
            except Exception as e:
                logger.debug(f"SAFLA learning update failed: {e}")

        logger.debug(
            f"Recorded performance: {metrics.strategy_used.value} "
            f"({'success' if metrics.success else 'failure'})"
        )

    async def get_system_state(self) -> dict[str, Any]:
        """Get current system state for monitoring.

        Returns:
            Dictionary with system health metrics
        """
        await self.initialize()

        # Calculate success rates
        success_rates = {}
        for strategy, stats in self._strategy_success_rates.items():
            if stats["total"] > 0:
                success_rates[strategy.value] = stats["successes"] / stats["total"]
            else:
                success_rates[strategy.value] = None

        return {
            "initialized": self._initialized,
            "engine_available": self._engine is not None,
            "current_load": self._current_load,
            "active_tasks": self._active_tasks,
            "history_size": len(self._performance_history),
            "strategy_success_rates": success_rates,
            "avg_durations": {
                s.value: stats["avg_duration"]
                for s, stats in self._strategy_success_rates.items()
                if stats["total"] > 0
            },
        }

    async def suggest_improvement(self) -> str | None:
        """Get a suggestion for improving TAJINE's performance.

        Analyzes recent performance and suggests improvements.

        Returns:
            Improvement suggestion or None if no issues detected
        """
        await self.initialize()

        if len(self._performance_history) < 10:
            return None

        # Analyze recent failures
        recent = self._performance_history[-20:]
        failure_rate = sum(1 for m in recent if not m.success) / len(recent)

        if failure_rate > 0.3:
            # High failure rate - suggest strategy change
            failing_strategies = {}
            for m in recent:
                if not m.success:
                    failing_strategies[m.strategy_used] = (
                        failing_strategies.get(m.strategy_used, 0) + 1
                    )

            worst_strategy = max(failing_strategies.items(), key=lambda x: x[1])
            return f"Consider avoiding {worst_strategy[0].value} strategy - {worst_strategy[1]} recent failures"

        # Analyze slow responses
        avg_duration = sum(m.duration_ms for m in recent) / len(recent)
        if avg_duration > 5000:  # > 5 seconds average
            return (
                "Response times are high - consider enabling more caching or simplifying strategies"
            )

        # Check for low confidence scores
        avg_confidence = sum(m.confidence for m in recent) / len(recent)
        if avg_confidence < 0.5:
            return "Confidence scores are low - consider adding more data sources or improving analysis"

        return None

    def update_load(self, active_tasks: int) -> None:
        """Update current system load.

        Args:
            active_tasks: Number of currently active tasks
        """
        self._active_tasks = active_tasks
        self._current_load = min(1.0, active_tasks / 10)  # Normalize to 0-1

    def _assess_complexity(self, query: str, context: dict[str, Any]) -> TaskComplexity:
        """Assess the complexity of a query."""
        query_lower = query.lower()

        # Expert-level indicators
        expert_keywords = ["compare", "predict", "forecast", "strategy", "scenario", "simulate"]
        if any(kw in query_lower for kw in expert_keywords):
            return TaskComplexity.EXPERT

        # Complex indicators
        complex_keywords = ["analyze", "evaluate", "assess", "impact", "trend", "pattern"]
        if any(kw in query_lower for kw in complex_keywords):
            return TaskComplexity.COMPLEX

        # Moderate indicators
        moderate_keywords = ["list", "summarize", "aggregate", "count", "statistics"]
        if any(kw in query_lower for kw in moderate_keywords):
            return TaskComplexity.MODERATE

        # Default to simple
        return TaskComplexity.SIMPLE

    async def _select_strategy(
        self,
        complexity: TaskComplexity,
        context: dict[str, Any],
    ) -> StrategyType:
        """Select the best strategy based on complexity and context."""

        # If system is overloaded, use simpler strategies
        if self._current_load > 0.8:
            if complexity in [TaskComplexity.SIMPLE, TaskComplexity.MODERATE]:
                return StrategyType.FAST_LOOKUP
            return StrategyType.FALLBACK

        # Map complexity to strategy
        strategy_map = {
            TaskComplexity.SIMPLE: StrategyType.FAST_LOOKUP,
            TaskComplexity.MODERATE: StrategyType.DATA_HUNT,
            TaskComplexity.COMPLEX: StrategyType.DEEP_ANALYSIS,
            TaskComplexity.EXPERT: StrategyType.COLLABORATIVE,
        }

        suggested = strategy_map.get(complexity, StrategyType.DATA_HUNT)

        # Check success rate and potentially downgrade
        stats = self._strategy_success_rates[suggested]
        if stats["total"] > 5:
            success_rate = stats["successes"] / stats["total"]
            if success_rate < 0.5:
                # This strategy isn't working well, try a simpler one
                fallback_order = [
                    StrategyType.FAST_LOOKUP,
                    StrategyType.DATA_HUNT,
                    StrategyType.DEEP_ANALYSIS,
                ]
                for fallback in fallback_order:
                    if fallback != suggested:
                        fb_stats = self._strategy_success_rates[fallback]
                        if (
                            fb_stats["total"] < 5
                            or (fb_stats["successes"] / fb_stats["total"]) > success_rate
                        ):
                            return fallback

        return suggested

    def _estimate_duration(self, strategy: StrategyType, complexity: TaskComplexity) -> int:
        """Estimate task duration in milliseconds."""
        # Base estimates
        base_estimates = {
            StrategyType.FAST_LOOKUP: 200,
            StrategyType.DATA_HUNT: 2000,
            StrategyType.DEEP_ANALYSIS: 5000,
            StrategyType.COLLABORATIVE: 10000,
            StrategyType.FALLBACK: 500,
        }

        base = base_estimates.get(strategy, 1000)

        # Use historical data if available
        stats = self._strategy_success_rates[strategy]
        if stats["total"] > 5 and stats["avg_duration"] > 0:
            base = int(stats["avg_duration"])

        # Adjust for complexity
        complexity_multiplier = {
            TaskComplexity.SIMPLE: 0.5,
            TaskComplexity.MODERATE: 1.0,
            TaskComplexity.COMPLEX: 2.0,
            TaskComplexity.EXPERT: 3.0,
        }

        return int(base * complexity_multiplier.get(complexity, 1.0))

    def _identify_risks(
        self,
        query: str,
        context: dict[str, Any],
        strategy: StrategyType,
    ) -> list[str]:
        """Identify potential risks for the task."""
        risks = []

        # Load-related risks
        if self._current_load > 0.5:
            risks.append("System under moderate load - may experience delays")

        # Strategy-specific risks
        if strategy == StrategyType.COLLABORATIVE:
            risks.append("Multi-agent coordination may introduce latency")

        if strategy == StrategyType.DEEP_ANALYSIS:
            stats = self._strategy_success_rates[strategy]
            if stats["total"] > 5 and (stats["successes"] / stats["total"]) < 0.7:
                risks.append("Deep analysis has shown lower success rate recently")

        # Context-specific risks
        if context.get("real_time_required"):
            risks.append("Real-time data may not be available for all sources")

        return risks

    def _generate_rationale(
        self,
        complexity: TaskComplexity,
        strategy: StrategyType,
        context: dict[str, Any],
    ) -> str:
        """Generate human-readable rationale for the recommendation."""
        rationale_parts = [
            f"Query assessed as {complexity.value} complexity.",
        ]

        stats = self._strategy_success_rates[strategy]
        if stats["total"] > 5:
            success_rate = stats["successes"] / stats["total"]
            rationale_parts.append(
                f"{strategy.value} strategy has {success_rate:.0%} success rate "
                f"across {int(stats['total'])} executions."
            )
        else:
            rationale_parts.append(f"{strategy.value} is the default for this complexity level.")

        if self._current_load > 0.3:
            rationale_parts.append(f"Current system load: {self._current_load:.0%}")

        return " ".join(rationale_parts)

    def _calculate_confidence(self, strategy: StrategyType, complexity: TaskComplexity) -> float:
        """Calculate confidence in the recommendation."""
        base_confidence = 0.7

        # Boost confidence if we have good historical data
        stats = self._strategy_success_rates[strategy]
        if stats["total"] > 10:
            success_rate = stats["successes"] / stats["total"]
            base_confidence = 0.5 + (success_rate * 0.4)

        # Reduce confidence for expert-level tasks
        if complexity == TaskComplexity.EXPERT:
            base_confidence *= 0.9

        # Reduce confidence under high load
        if self._current_load > 0.7:
            base_confidence *= 0.8

        return min(1.0, max(0.1, base_confidence))
