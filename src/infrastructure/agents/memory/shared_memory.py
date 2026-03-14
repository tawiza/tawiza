"""Shared Memory - Inter-agent communication and state sharing.

Provides a centralized memory system that allows agents to:
- Share data between execution steps
- Maintain conversation history
- Store intermediate results
- Coordinate on complex tasks

Memory types:
- Short-term: Current session data (cleared on reset)
- Working: Task-specific data (cleared per task)
- Long-term: Persistent data (survives restarts)
"""

import asyncio
import builtins
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, StrEnum
from typing import Any, Optional

from loguru import logger


class MemoryType(StrEnum):
    """Types of memory storage."""

    SHORT_TERM = "short_term"  # Session-scoped, volatile
    WORKING = "working"  # Task-scoped, cleared per task
    LONG_TERM = "long_term"  # Persistent across sessions


class MemoryScope(StrEnum):
    """Scope of memory access."""

    GLOBAL = "global"  # Accessible by all agents
    AGENT = "agent"  # Specific to one agent
    TASK = "task"  # Specific to one task
    CHAIN = "chain"  # Shared within an agent chain


@dataclass
class MemoryEntry:
    """Single memory entry with metadata."""

    key: str
    value: Any
    memory_type: MemoryType
    scope: MemoryScope
    owner: str | None = None  # Agent or task ID
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None
    tags: set[str] = field(default_factory=set)
    access_count: int = 0

    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "key": self.key,
            "value": self.value,
            "memory_type": self.memory_type.value,
            "scope": self.scope.value,
            "owner": self.owner,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "tags": list(self.tags),
            "access_count": self.access_count,
        }


class MemoryBackend(ABC):
    """Abstract backend for memory storage."""

    @abstractmethod
    async def get(self, key: str) -> MemoryEntry | None:
        """Retrieve a memory entry."""
        pass

    @abstractmethod
    async def set(self, entry: MemoryEntry) -> None:
        """Store a memory entry."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a memory entry."""
        pass

    @abstractmethod
    async def search(
        self,
        pattern: str | None = None,
        scope: MemoryScope | None = None,
        memory_type: MemoryType | None = None,
        tags: builtins.set[str] | None = None,
        owner: str | None = None,
    ) -> list[MemoryEntry]:
        """Search for memory entries."""
        pass

    @abstractmethod
    async def clear(
        self,
        scope: MemoryScope | None = None,
        memory_type: MemoryType | None = None,
        owner: str | None = None,
    ) -> int:
        """Clear memory entries matching criteria."""
        pass


class InMemoryBackend(MemoryBackend):
    """In-memory storage backend.

    Fast but volatile - data is lost on restart.
    Suitable for short-term and working memory.
    """

    def __init__(self):
        self._store: dict[str, MemoryEntry] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> MemoryEntry | None:
        async with self._lock:
            entry = self._store.get(key)
            if entry and entry.is_expired:
                del self._store[key]
                return None
            if entry:
                entry.access_count += 1
            return entry

    async def set(self, entry: MemoryEntry) -> None:
        async with self._lock:
            entry.updated_at = datetime.utcnow()
            self._store[entry.key] = entry

    async def delete(self, key: str) -> bool:
        async with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    async def search(
        self,
        pattern: str | None = None,
        scope: MemoryScope | None = None,
        memory_type: MemoryType | None = None,
        tags: builtins.set[str] | None = None,
        owner: str | None = None,
    ) -> list[MemoryEntry]:
        async with self._lock:
            results = []

            for entry in self._store.values():
                # Skip expired
                if entry.is_expired:
                    continue

                # Apply filters
                if pattern and pattern not in entry.key:
                    continue
                if scope and entry.scope != scope:
                    continue
                if memory_type and entry.memory_type != memory_type:
                    continue
                if owner and entry.owner != owner:
                    continue
                if tags and not tags.issubset(entry.tags):
                    continue

                results.append(entry)

            return results

    async def clear(
        self,
        scope: MemoryScope | None = None,
        memory_type: MemoryType | None = None,
        owner: str | None = None,
    ) -> int:
        async with self._lock:
            to_delete = []

            for key, entry in self._store.items():
                if scope and entry.scope != scope:
                    continue
                if memory_type and entry.memory_type != memory_type:
                    continue
                if owner and entry.owner != owner:
                    continue
                to_delete.append(key)

            for key in to_delete:
                del self._store[key]

            return len(to_delete)


class SharedMemory:
    """Centralized shared memory for inter-agent communication.

    Provides a unified interface for agents to share data:
    - Scoped access (global, agent, task, chain)
    - TTL support for automatic expiration
    - Event subscriptions for reactive patterns
    - Thread-safe async operations

    Example:
        >>> memory = SharedMemory()
        >>> await memory.set("analysis_result", {"score": 0.85}, scope=MemoryScope.CHAIN)
        >>> result = await memory.get("analysis_result")
        >>> print(result.value)  # {"score": 0.85}
    """

    _instance: Optional["SharedMemory"] = None

    def __new__(cls) -> "SharedMemory":
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, backend: MemoryBackend | None = None):
        if self._initialized:
            return

        self._backend = backend or InMemoryBackend()
        self._subscribers: dict[str, list[Callable]] = {}
        self._lock = asyncio.Lock()
        self._initialized = True

        logger.info("SharedMemory initialized")

    def _make_key(
        self,
        key: str,
        scope: MemoryScope = MemoryScope.GLOBAL,
        owner: str | None = None,
    ) -> str:
        """Generate scoped key."""
        parts = [scope.value]
        if owner:
            parts.append(owner)
        parts.append(key)
        return ":".join(parts)

    async def set(
        self,
        key: str,
        value: Any,
        scope: MemoryScope = MemoryScope.GLOBAL,
        memory_type: MemoryType = MemoryType.SHORT_TERM,
        owner: str | None = None,
        ttl_seconds: int | None = None,
        tags: set[str] | None = None,
    ) -> None:
        """Store a value in shared memory.

        Args:
            key: Unique identifier
            value: Data to store (must be JSON-serializable for persistence)
            scope: Access scope
            memory_type: Storage type
            owner: Owner agent/task ID
            ttl_seconds: Time-to-live in seconds
            tags: Optional tags for filtering
        """
        full_key = self._make_key(key, scope, owner)

        expires_at = None
        if ttl_seconds:
            expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)

        entry = MemoryEntry(
            key=full_key,
            value=value,
            memory_type=memory_type,
            scope=scope,
            owner=owner,
            expires_at=expires_at,
            tags=tags or set(),
        )

        await self._backend.set(entry)
        logger.debug(f"Memory set: {full_key} (scope={scope.value})")

        # Notify subscribers
        await self._notify(key, value, "set")

    async def get(
        self,
        key: str,
        scope: MemoryScope = MemoryScope.GLOBAL,
        owner: str | None = None,
        default: Any = None,
    ) -> Any:
        """Retrieve a value from shared memory.

        Args:
            key: Key to retrieve
            scope: Access scope
            owner: Owner filter
            default: Default value if not found

        Returns:
            Stored value or default
        """
        full_key = self._make_key(key, scope, owner)
        entry = await self._backend.get(full_key)

        if entry is None:
            return default

        return entry.value

    async def get_entry(
        self,
        key: str,
        scope: MemoryScope = MemoryScope.GLOBAL,
        owner: str | None = None,
    ) -> MemoryEntry | None:
        """Get full memory entry with metadata."""
        full_key = self._make_key(key, scope, owner)
        return await self._backend.get(full_key)

    async def delete(
        self,
        key: str,
        scope: MemoryScope = MemoryScope.GLOBAL,
        owner: str | None = None,
    ) -> bool:
        """Delete a memory entry."""
        full_key = self._make_key(key, scope, owner)
        deleted = await self._backend.delete(full_key)

        if deleted:
            logger.debug(f"Memory deleted: {full_key}")
            await self._notify(key, None, "delete")

        return deleted

    async def exists(
        self,
        key: str,
        scope: MemoryScope = MemoryScope.GLOBAL,
        owner: str | None = None,
    ) -> bool:
        """Check if a key exists."""
        full_key = self._make_key(key, scope, owner)
        entry = await self._backend.get(full_key)
        return entry is not None

    async def search(
        self,
        pattern: str | None = None,
        scope: MemoryScope | None = None,
        memory_type: MemoryType | None = None,
        tags: builtins.set[str] | None = None,
        owner: str | None = None,
    ) -> list[MemoryEntry]:
        """Search for memory entries.

        Args:
            pattern: Key pattern to match
            scope: Filter by scope
            memory_type: Filter by type
            tags: Filter by tags (all must match)
            owner: Filter by owner

        Returns:
            List of matching entries
        """
        return await self._backend.search(
            pattern=pattern,
            scope=scope,
            memory_type=memory_type,
            tags=tags,
            owner=owner,
        )

    async def clear(
        self,
        scope: MemoryScope | None = None,
        memory_type: MemoryType | None = None,
        owner: str | None = None,
    ) -> int:
        """Clear memory entries.

        Args:
            scope: Clear only this scope
            memory_type: Clear only this type
            owner: Clear only this owner's entries

        Returns:
            Number of entries cleared
        """
        count = await self._backend.clear(
            scope=scope,
            memory_type=memory_type,
            owner=owner,
        )

        logger.info(f"Cleared {count} memory entries")
        return count

    # Convenience methods for common patterns

    async def set_task_data(
        self,
        task_id: str,
        key: str,
        value: Any,
        ttl_seconds: int = 3600,
    ) -> None:
        """Store task-specific data."""
        await self.set(
            key=key,
            value=value,
            scope=MemoryScope.TASK,
            memory_type=MemoryType.WORKING,
            owner=task_id,
            ttl_seconds=ttl_seconds,
        )

    async def get_task_data(
        self,
        task_id: str,
        key: str,
        default: Any = None,
    ) -> Any:
        """Retrieve task-specific data."""
        return await self.get(
            key=key,
            scope=MemoryScope.TASK,
            owner=task_id,
            default=default,
        )

    async def set_agent_state(
        self,
        agent_id: str,
        key: str,
        value: Any,
    ) -> None:
        """Store agent-specific state."""
        await self.set(
            key=key,
            value=value,
            scope=MemoryScope.AGENT,
            memory_type=MemoryType.SHORT_TERM,
            owner=agent_id,
        )

    async def get_agent_state(
        self,
        agent_id: str,
        key: str,
        default: Any = None,
    ) -> Any:
        """Retrieve agent-specific state."""
        return await self.get(
            key=key,
            scope=MemoryScope.AGENT,
            owner=agent_id,
            default=default,
        )

    async def share_chain_data(
        self,
        chain_id: str,
        key: str,
        value: Any,
    ) -> None:
        """Share data within an agent chain."""
        await self.set(
            key=key,
            value=value,
            scope=MemoryScope.CHAIN,
            memory_type=MemoryType.WORKING,
            owner=chain_id,
        )

    async def get_chain_data(
        self,
        chain_id: str,
        key: str,
        default: Any = None,
    ) -> Any:
        """Get shared chain data."""
        return await self.get(
            key=key,
            scope=MemoryScope.CHAIN,
            owner=chain_id,
            default=default,
        )

    # Event subscription for reactive patterns

    def subscribe(self, key_pattern: str, callback: Callable) -> None:
        """Subscribe to memory changes.

        Args:
            key_pattern: Key or pattern to watch
            callback: Async function(key, value, event_type)
        """
        if key_pattern not in self._subscribers:
            self._subscribers[key_pattern] = []
        self._subscribers[key_pattern].append(callback)
        logger.debug(f"Subscribed to memory changes: {key_pattern}")

    def unsubscribe(self, key_pattern: str, callback: Callable) -> None:
        """Unsubscribe from memory changes."""
        if key_pattern in self._subscribers:
            self._subscribers[key_pattern] = [
                cb for cb in self._subscribers[key_pattern] if cb != callback
            ]

    async def _notify(
        self,
        key: str,
        value: Any,
        event_type: str,
    ) -> None:
        """Notify subscribers of a change."""
        for pattern, callbacks in self._subscribers.items():
            if pattern in key or pattern == "*":
                for callback in callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(key, value, event_type)
                        else:
                            callback(key, value, event_type)
                    except Exception as e:
                        logger.error(f"Subscriber callback failed: {e}")


class ConversationMemory:
    """Specialized memory for conversation history.

    Maintains ordered message history with:
    - Role-based messages (system, user, assistant)
    - Context window management
    - Summary generation for long conversations

    Example:
        >>> conv = ConversationMemory("agent-1")
        >>> await conv.add_message("user", "What's the weather?")
        >>> await conv.add_message("assistant", "It's sunny today.")
        >>> messages = await conv.get_messages(limit=10)
    """

    def __init__(
        self,
        conversation_id: str,
        shared_memory: SharedMemory | None = None,
        max_messages: int = 100,
    ):
        self.conversation_id = conversation_id
        self.memory = shared_memory or SharedMemory()
        self.max_messages = max_messages
        self._messages_key = f"conversation:{conversation_id}:messages"
        self._summary_key = f"conversation:{conversation_id}:summary"

    async def add_message(
        self,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a message to the conversation."""
        messages = await self.memory.get(
            self._messages_key,
            default=[],
        )

        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }

        messages.append(message)

        # Trim if over limit
        if len(messages) > self.max_messages:
            # Keep first (system) and last N messages
            messages = messages[:1] + messages[-(self.max_messages - 1) :]

        await self.memory.set(
            self._messages_key,
            messages,
            memory_type=MemoryType.SHORT_TERM,
        )

    async def get_messages(
        self,
        limit: int | None = None,
        roles: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Get conversation messages.

        Args:
            limit: Maximum messages to return
            roles: Filter by role (e.g., ["user", "assistant"])

        Returns:
            List of message dictionaries
        """
        messages = await self.memory.get(
            self._messages_key,
            default=[],
        )

        if roles:
            messages = [m for m in messages if m["role"] in roles]

        if limit:
            messages = messages[-limit:]

        return messages

    async def get_last_message(
        self,
        role: str | None = None,
    ) -> dict[str, Any] | None:
        """Get the last message."""
        messages = await self.get_messages(roles=[role] if role else None)
        return messages[-1] if messages else None

    async def clear(self) -> None:
        """Clear conversation history."""
        await self.memory.delete(self._messages_key)
        await self.memory.delete(self._summary_key)

    async def set_summary(self, summary: str) -> None:
        """Set conversation summary."""
        await self.memory.set(
            self._summary_key,
            summary,
            memory_type=MemoryType.SHORT_TERM,
        )

    async def get_summary(self) -> str | None:
        """Get conversation summary."""
        return await self.memory.get(self._summary_key)


# Global accessor
_shared_memory: SharedMemory | None = None


def get_shared_memory() -> SharedMemory:
    """Get the global shared memory instance."""
    global _shared_memory
    if _shared_memory is None:
        _shared_memory = SharedMemory()
    return _shared_memory
