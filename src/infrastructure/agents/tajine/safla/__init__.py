"""SAFLA Integration for TAJINE.

This module bridges SAFLA (Self-Aware Feedback Loop Algorithm) with TAJINE,
providing:
- Persistent hybrid memory (vector, episodic, semantic, working)
- Meta-cognitive self-improvement capabilities
- Adaptive learning from task execution
- Safety validation and constraint management

Usage:
    from src.infrastructure.agents.tajine.safla import SAFLABridge

    bridge = SAFLABridge()
    await bridge.initialize()

    # Store memory from TAJINE execution
    await bridge.store_execution_memory(task, result, context)

    # Retrieve relevant memories for new task
    memories = await bridge.recall_relevant(query, limit=5)

    # Get meta-cognitive insights
    insights = await bridge.get_strategic_insights(current_state)
"""

from .bridge import SAFLABridge
from .memory_adapter import SAFLAMemoryAdapter
from .metacognitive_adapter import SAFLAMetaCognitiveAdapter

__all__ = [
    "SAFLABridge",
    "SAFLAMemoryAdapter",
    "SAFLAMetaCognitiveAdapter",
]
