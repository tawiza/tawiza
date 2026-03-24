"""SAFLA Bridge - Main integration point for TAJINE.

This module provides the unified interface for TAJINE to leverage SAFLA's
capabilities. It coordinates:
- Memory operations (store, recall, consolidate)
- Metacognitive functions (strategy, learning, monitoring)
- Safety and validation checks

The bridge is designed to be:
1. Non-blocking - Falls back gracefully if SAFLA unavailable
2. Persistent - Maintains state across sessions
3. Adaptive - Learns and improves over time
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from .memory_adapter import SAFLAMemoryAdapter, TAJINEMemoryItem
from .metacognitive_adapter import (
    PerformanceMetrics,
    SAFLAMetaCognitiveAdapter,
    StrategicInsight,
    StrategyType,
)


@dataclass
class SAFLAContext:
    """Context for SAFLA-enhanced TAJINE execution."""

    task_id: str
    query: str
    territory: str | None = None
    sector: str | None = None
    strategy: StrategyType | None = None
    start_time: datetime | None = None

    # Recalled context
    relevant_memories: list[TAJINEMemoryItem] | None = None
    territory_knowledge: dict[str, Any] | None = None
    strategic_insight: StrategicInsight | None = None


class SAFLABridge:
    """Main bridge integrating SAFLA with TAJINE.

    Provides a unified interface for TAJINE to leverage SAFLA's:
    - Hybrid memory system (persistent, semantic, episodic)
    - Metacognitive engine (self-awareness, strategy, learning)
    - Safety validation (constraints, rollback)

    Usage:
        bridge = SAFLABridge()
        await bridge.initialize()

        # Before task execution
        context = await bridge.prepare_context(task_id, query, territory)

        # After task execution
        await bridge.record_execution(context, result, success=True)

        # Get improvement suggestions
        suggestion = await bridge.get_improvement_suggestion()
    """

    def __init__(self, storage_path: Path | None = None):
        """Initialize the SAFLA bridge.

        Args:
            storage_path: Path for persistent storage
        """
        self.storage_path = storage_path or Path.home() / ".tawiza" / "safla"

        self.memory = SAFLAMemoryAdapter(storage_path=self.storage_path)
        self.metacognitive = SAFLAMetaCognitiveAdapter()

        self._initialized = False
        self._active_contexts: dict[str, SAFLAContext] = {}

        logger.info("SAFLABridge created")

    async def initialize(self) -> None:
        """Initialize all SAFLA components."""
        if self._initialized:
            return

        await asyncio.gather(
            self.memory.initialize(),
            self.metacognitive.initialize(),
        )

        self._initialized = True
        logger.info("SAFLABridge fully initialized")

    async def prepare_context(
        self,
        task_id: str,
        query: str,
        territory: str | None = None,
        sector: str | None = None,
    ) -> SAFLAContext:
        """Prepare context for a TAJINE task execution.

        Retrieves relevant memories, territory knowledge, and strategic
        recommendations to enhance the task execution.

        Args:
            task_id: Unique task identifier
            query: User's query
            territory: Territory code if applicable
            sector: Economic sector if applicable

        Returns:
            SAFLAContext with prepared information
        """
        await self.initialize()

        context = SAFLAContext(
            task_id=task_id,
            query=query,
            territory=territory,
            sector=sector,
            start_time=datetime.now(),
        )

        # Run preparations in parallel
        memory_task = self._recall_relevant_memories(query, territory, sector)
        knowledge_task = self._get_territory_knowledge(territory) if territory else asyncio.sleep(0)
        insight_task = self.metacognitive.get_strategic_insight(
            query=query,
            context={"territory": territory, "sector": sector},
        )

        results = await asyncio.gather(
            memory_task,
            knowledge_task,
            insight_task,
            return_exceptions=True,
        )

        # Process results
        if not isinstance(results[0], Exception):
            context.relevant_memories = results[0]
        else:
            logger.warning(f"Memory recall failed: {results[0]}")
            context.relevant_memories = []

        if territory and not isinstance(results[1], Exception):
            context.territory_knowledge = results[1]

        if not isinstance(results[2], Exception):
            context.strategic_insight = results[2]
            context.strategy = results[2].suggested_strategy
        else:
            logger.warning(f"Strategic insight failed: {results[2]}")

        # Update load tracking
        self._active_contexts[task_id] = context
        self.metacognitive.update_load(len(self._active_contexts))

        logger.debug(
            f"Prepared context for task {task_id}: "
            f"{len(context.relevant_memories or [])} memories, "
            f"strategy={context.strategy}"
        )

        return context

    async def record_execution(
        self,
        context: SAFLAContext,
        result: dict[str, Any],
        success: bool = True,
        error_message: str | None = None,
    ) -> None:
        """Record task execution for learning and memory.

        Stores the execution result and updates performance metrics
        to improve future recommendations.

        Args:
            context: The execution context
            result: Task result
            success: Whether task succeeded
            error_message: Error message if failed
        """
        await self.initialize()

        # Calculate duration
        duration_ms = 0.0
        if context.start_time:
            duration_ms = (datetime.now() - context.start_time).total_seconds() * 1000

        # Store task memory
        await self.memory.store_task_memory(
            task_id=context.task_id,
            query=context.query,
            result=result,
            territory=context.territory,
            sector=context.sector,
            success=success,
        )

        # Record performance metrics
        metrics = PerformanceMetrics(
            task_id=context.task_id,
            duration_ms=duration_ms,
            success=success,
            confidence=result.get("confidence", 0.5) if isinstance(result, dict) else 0.5,
            data_sources_used=result.get("sources_count", 1) if isinstance(result, dict) else 1,
            cache_hit=result.get("cache_hit", False) if isinstance(result, dict) else False,
            strategy_used=context.strategy or StrategyType.DATA_HUNT,
            error_message=error_message,
        )

        await self.metacognitive.record_performance(metrics)

        # Store any insights from the result
        if success and isinstance(result, dict):
            insights = result.get("insights", [])
            for insight in insights[:5]:  # Limit to 5 insights per task
                if isinstance(insight, str):
                    await self.memory.store_analysis_insight(
                        insight=insight,
                        analysis_type=result.get("analysis_type", "general"),
                        territory=context.territory,
                        confidence=result.get("confidence", 0.5),
                    )

        # Cleanup
        self._active_contexts.pop(context.task_id, None)
        self.metacognitive.update_load(len(self._active_contexts))

        logger.debug(
            f"Recorded execution for task {context.task_id}: "
            f"success={success}, duration={duration_ms:.0f}ms"
        )

    async def store_insight(
        self,
        insight: str,
        analysis_type: str,
        territory: str | None = None,
        confidence: float = 0.5,
    ) -> str:
        """Store an insight for future reference.

        Args:
            insight: The insight text
            analysis_type: Type of analysis
            territory: Territory code
            confidence: Confidence score

        Returns:
            Memory item ID
        """
        await self.initialize()

        return await self.memory.store_analysis_insight(
            insight=insight,
            analysis_type=analysis_type,
            territory=territory,
            confidence=confidence,
        )

    async def store_entity(
        self,
        entity_id: str,
        entity_type: str,
        name: str,
        attributes: dict[str, Any],
        territory: str | None = None,
    ) -> str:
        """Store an entity in memory.

        Args:
            entity_id: Unique identifier (e.g., SIREN)
            entity_type: Type of entity
            name: Entity name
            attributes: Entity attributes
            territory: Territory code

        Returns:
            Memory item ID
        """
        await self.initialize()

        return await self.memory.store_entity(
            entity_id=entity_id,
            entity_type=entity_type,
            name=name,
            attributes=attributes,
            territory=territory,
        )

    async def recall_for_query(
        self,
        query: str,
        territory: str | None = None,
        limit: int = 5,
    ) -> list[TAJINEMemoryItem]:
        """Recall relevant memories for a query.

        Args:
            query: Search query
            territory: Filter by territory
            limit: Maximum results

        Returns:
            List of relevant memory items
        """
        await self.initialize()

        return await self.memory.recall_similar(
            query=query,
            territory=territory,
            limit=limit,
        )

    async def get_improvement_suggestion(self) -> str | None:
        """Get a suggestion for improving TAJINE's performance.

        Returns:
            Improvement suggestion or None
        """
        await self.initialize()

        return await self.metacognitive.suggest_improvement()

    async def get_status(self) -> dict[str, Any]:
        """Get SAFLA integration status.

        Returns:
            Status dictionary with component health
        """
        await self.initialize()

        memory_stats = await self.memory.get_stats()
        meta_state = await self.metacognitive.get_system_state()

        return {
            "initialized": self._initialized,
            "active_contexts": len(self._active_contexts),
            "memory": memory_stats,
            "metacognitive": meta_state,
            "storage_path": str(self.storage_path),
        }

    async def _recall_relevant_memories(
        self,
        query: str,
        territory: str | None,
        sector: str | None,
    ) -> list[TAJINEMemoryItem]:
        """Internal method to recall relevant memories."""
        memories = await self.memory.recall_similar(
            query=query,
            territory=territory,
            limit=10,
        )

        # Also recall any sector-specific memories
        if sector:
            sector_memories = await self.memory.recall_similar(
                query=f"{sector} sector analysis",
                limit=5,
            )
            # Merge, avoiding duplicates
            seen_ids = {m.item_id for m in memories}
            for m in sector_memories:
                if m.item_id not in seen_ids:
                    memories.append(m)

        return memories[:10]  # Limit total

    async def _get_territory_knowledge(self, territory: str) -> dict[str, Any]:
        """Internal method to get territory knowledge."""
        return await self.memory.get_territory_knowledge(territory)


# Singleton instance
_bridge_instance: SAFLABridge | None = None


def get_safla_bridge() -> SAFLABridge:
    """Get the singleton SAFLA bridge instance."""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = SAFLABridge()
    return _bridge_instance
