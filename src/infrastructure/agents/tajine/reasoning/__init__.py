"""TAJINE reasoning system.

Provides explicit reasoning capabilities:
- Chain-of-Thought: Step-by-step reasoning
- Tree-of-Thoughts: Multi-path exploration for complex decisions
"""

from src.infrastructure.agents.tajine.reasoning.chain_of_thought import (
    ChainOfThought,
    ThoughtStep,
    ThoughtType,
    quick_reason,
)
from src.infrastructure.agents.tajine.reasoning.tree_of_thoughts import (
    SearchStrategy,
    ThoughtNode,
    TreeOfThoughts,
    explore_solutions,
)

__all__ = [
    # Chain-of-Thought
    "ChainOfThought",
    "ThoughtStep",
    "ThoughtType",
    "quick_reason",
    # Tree-of-Thoughts
    "TreeOfThoughts",
    "ThoughtNode",
    "SearchStrategy",
    "explore_solutions",
]
