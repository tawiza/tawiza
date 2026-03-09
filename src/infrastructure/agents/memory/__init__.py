"""Agent Memory - Shared memory and conversation history.

This module provides a centralized memory system for inter-agent communication:
- Short-term session memory
- Working memory for tasks
- Conversation history management
- Event-based memory subscriptions

Main components:
- SharedMemory: Centralized shared memory singleton
- ConversationMemory: Specialized memory for conversation history
- MemoryEntry: Single memory entry with metadata
- MemoryScope: Access scope (global, agent, task, chain)
- MemoryType: Storage type (short_term, working, long_term)

Example:
    >>> from src.infrastructure.agents.memory import (
    ...     SharedMemory,
    ...     MemoryScope,
    ...     get_shared_memory,
    ... )
    >>>
    >>> # Get shared memory instance
    >>> memory = get_shared_memory()
    >>>
    >>> # Store data for a chain
    >>> await memory.share_chain_data("chain-1", "analysis", {"score": 0.85})
    >>>
    >>> # Retrieve data
    >>> result = await memory.get_chain_data("chain-1", "analysis")
    >>>
    >>> # Subscribe to changes
    >>> def on_change(key, value, event):
    ...     print(f"{event}: {key} = {value}")
    >>> memory.subscribe("analysis", on_change)
"""

from src.infrastructure.agents.memory.shared_memory import (
    ConversationMemory,
    InMemoryBackend,
    MemoryBackend,
    MemoryEntry,
    MemoryScope,
    MemoryType,
    SharedMemory,
    get_shared_memory,
)

__all__ = [
    "ConversationMemory",
    "InMemoryBackend",
    "MemoryBackend",
    "MemoryEntry",
    "MemoryScope",
    "MemoryType",
    "SharedMemory",
    "get_shared_memory",
]
