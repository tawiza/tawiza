"""Tests for SharedMemory - Inter-agent communication."""

import asyncio
from datetime import datetime, timedelta

import pytest

from src.infrastructure.agents.memory.shared_memory import (
    ConversationMemory,
    InMemoryBackend,
    MemoryEntry,
    MemoryScope,
    MemoryType,
    SharedMemory,
    get_shared_memory,
)


class TestMemoryEntry:
    """Tests for MemoryEntry dataclass."""

    def test_create_entry(self):
        """Test creating a memory entry."""
        entry = MemoryEntry(
            key="test_key",
            value={"data": 123},
            memory_type=MemoryType.SHORT_TERM,
            scope=MemoryScope.GLOBAL,
        )

        assert entry.key == "test_key"
        assert entry.value == {"data": 123}
        assert entry.memory_type == MemoryType.SHORT_TERM
        assert entry.scope == MemoryScope.GLOBAL
        assert entry.access_count == 0

    def test_is_expired_no_expiry(self):
        """Test entry without expiry never expires."""
        entry = MemoryEntry(
            key="test",
            value="data",
            memory_type=MemoryType.SHORT_TERM,
            scope=MemoryScope.GLOBAL,
            expires_at=None,
        )

        assert entry.is_expired is False

    def test_is_expired_future(self):
        """Test entry with future expiry is not expired."""
        entry = MemoryEntry(
            key="test",
            value="data",
            memory_type=MemoryType.SHORT_TERM,
            scope=MemoryScope.GLOBAL,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )

        assert entry.is_expired is False

    def test_is_expired_past(self):
        """Test entry with past expiry is expired."""
        entry = MemoryEntry(
            key="test",
            value="data",
            memory_type=MemoryType.SHORT_TERM,
            scope=MemoryScope.GLOBAL,
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )

        assert entry.is_expired is True

    def test_to_dict(self):
        """Test conversion to dictionary."""
        entry = MemoryEntry(
            key="test",
            value={"count": 5},
            memory_type=MemoryType.WORKING,
            scope=MemoryScope.TASK,
            owner="task-1",
            tags={"tag1", "tag2"},
        )

        result = entry.to_dict()

        assert result["key"] == "test"
        assert result["value"] == {"count": 5}
        assert result["memory_type"] == "working"
        assert result["scope"] == "task"
        assert result["owner"] == "task-1"
        assert set(result["tags"]) == {"tag1", "tag2"}


class TestInMemoryBackend:
    """Tests for InMemoryBackend."""

    @pytest.fixture
    def backend(self):
        """Create fresh backend for each test."""
        return InMemoryBackend()

    @pytest.mark.asyncio
    async def test_set_and_get(self, backend):
        """Test basic set and get."""
        entry = MemoryEntry(
            key="test_key",
            value="test_value",
            memory_type=MemoryType.SHORT_TERM,
            scope=MemoryScope.GLOBAL,
        )

        await backend.set(entry)
        result = await backend.get("test_key")

        assert result is not None
        assert result.value == "test_value"
        assert result.access_count == 1

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, backend):
        """Test getting nonexistent key."""
        result = await backend.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, backend):
        """Test deleting an entry."""
        entry = MemoryEntry(
            key="to_delete",
            value="data",
            memory_type=MemoryType.SHORT_TERM,
            scope=MemoryScope.GLOBAL,
        )

        await backend.set(entry)
        deleted = await backend.delete("to_delete")
        result = await backend.get("to_delete")

        assert deleted is True
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, backend):
        """Test deleting nonexistent key."""
        deleted = await backend.delete("nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_expired_entries_removed_on_get(self, backend):
        """Test that expired entries are removed on get."""
        entry = MemoryEntry(
            key="expired",
            value="data",
            memory_type=MemoryType.SHORT_TERM,
            scope=MemoryScope.GLOBAL,
            expires_at=datetime.utcnow() - timedelta(seconds=1),
        )

        await backend.set(entry)
        result = await backend.get("expired")

        assert result is None

    @pytest.mark.asyncio
    async def test_search_by_scope(self, backend):
        """Test searching by scope."""
        # Add entries with different scopes
        for scope in [MemoryScope.GLOBAL, MemoryScope.AGENT, MemoryScope.TASK]:
            entry = MemoryEntry(
                key=f"key_{scope.value}",
                value=f"value_{scope.value}",
                memory_type=MemoryType.SHORT_TERM,
                scope=scope,
            )
            await backend.set(entry)

        results = await backend.search(scope=MemoryScope.TASK)

        assert len(results) == 1
        assert results[0].scope == MemoryScope.TASK

    @pytest.mark.asyncio
    async def test_search_by_pattern(self, backend):
        """Test searching by key pattern."""
        for i in range(3):
            entry = MemoryEntry(
                key=f"user_{i}_data",
                value=i,
                memory_type=MemoryType.SHORT_TERM,
                scope=MemoryScope.GLOBAL,
            )
            await backend.set(entry)

        entry = MemoryEntry(
            key="other_key",
            value="other",
            memory_type=MemoryType.SHORT_TERM,
            scope=MemoryScope.GLOBAL,
        )
        await backend.set(entry)

        results = await backend.search(pattern="user_")

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_clear_all(self, backend):
        """Test clearing all entries."""
        for i in range(5):
            entry = MemoryEntry(
                key=f"key_{i}",
                value=i,
                memory_type=MemoryType.SHORT_TERM,
                scope=MemoryScope.GLOBAL,
            )
            await backend.set(entry)

        count = await backend.clear()
        results = await backend.search()

        assert count == 5
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_clear_by_owner(self, backend):
        """Test clearing by owner."""
        for owner in ["agent-1", "agent-2"]:
            for i in range(2):
                entry = MemoryEntry(
                    key=f"{owner}_key_{i}",
                    value=i,
                    memory_type=MemoryType.SHORT_TERM,
                    scope=MemoryScope.AGENT,
                    owner=owner,
                )
                await backend.set(entry)

        count = await backend.clear(owner="agent-1")
        results = await backend.search()

        assert count == 2
        assert len(results) == 2
        assert all(r.owner == "agent-2" for r in results)


class TestSharedMemory:
    """Tests for SharedMemory."""

    @pytest.fixture
    def memory(self):
        """Create fresh memory instance."""
        # Reset singleton for testing
        SharedMemory._instance = None
        return SharedMemory()

    @pytest.mark.asyncio
    async def test_set_and_get(self, memory):
        """Test basic set and get."""
        await memory.set("key1", {"data": "value"})
        result = await memory.get("key1")

        assert result == {"data": "value"}

    @pytest.mark.asyncio
    async def test_get_default(self, memory):
        """Test get with default value."""
        result = await memory.get("nonexistent", default="default_value")
        assert result == "default_value"

    @pytest.mark.asyncio
    async def test_exists(self, memory):
        """Test exists check."""
        await memory.set("exists_key", "value")

        assert await memory.exists("exists_key") is True
        assert await memory.exists("not_exists") is False

    @pytest.mark.asyncio
    async def test_delete(self, memory):
        """Test deletion."""
        await memory.set("to_delete", "value")
        deleted = await memory.delete("to_delete")

        assert deleted is True
        assert await memory.exists("to_delete") is False

    @pytest.mark.asyncio
    async def test_scoped_keys(self, memory):
        """Test that different scopes create different keys."""
        await memory.set("key", "global", scope=MemoryScope.GLOBAL)
        await memory.set("key", "agent", scope=MemoryScope.AGENT, owner="agent-1")
        await memory.set("key", "task", scope=MemoryScope.TASK, owner="task-1")

        global_val = await memory.get("key", scope=MemoryScope.GLOBAL)
        agent_val = await memory.get("key", scope=MemoryScope.AGENT, owner="agent-1")
        task_val = await memory.get("key", scope=MemoryScope.TASK, owner="task-1")

        assert global_val == "global"
        assert agent_val == "agent"
        assert task_val == "task"

    @pytest.mark.asyncio
    async def test_ttl_expiration(self, memory):
        """Test TTL expiration."""
        # Use a very short TTL that will expire by the time we check
        await memory.set("ttl_key", "value", ttl_seconds=1)

        # Verify it exists initially
        result = await memory.get("ttl_key")
        assert result == "value"

        # Wait for expiration
        await asyncio.sleep(1.1)

        # Now should be expired
        result = await memory.get("ttl_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_task_data_convenience(self, memory):
        """Test task data convenience methods."""
        await memory.set_task_data("task-1", "result", {"score": 0.95})
        result = await memory.get_task_data("task-1", "result")

        assert result == {"score": 0.95}

    @pytest.mark.asyncio
    async def test_agent_state_convenience(self, memory):
        """Test agent state convenience methods."""
        await memory.set_agent_state("agent-1", "status", "running")
        result = await memory.get_agent_state("agent-1", "status")

        assert result == "running"

    @pytest.mark.asyncio
    async def test_chain_data_convenience(self, memory):
        """Test chain data convenience methods."""
        await memory.share_chain_data("chain-1", "intermediate", [1, 2, 3])
        result = await memory.get_chain_data("chain-1", "intermediate")

        assert result == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_subscribe_and_notify(self, memory):
        """Test event subscription."""
        notifications = []

        async def callback(key, value, event):
            notifications.append((key, value, event))

        memory.subscribe("test_key", callback)
        await memory.set("test_key", "value1")
        await memory.delete("test_key")

        assert len(notifications) == 2
        assert notifications[0] == ("test_key", "value1", "set")
        assert notifications[1] == ("test_key", None, "delete")

    @pytest.mark.asyncio
    async def test_search(self, memory):
        """Test search functionality."""
        await memory.set("search_a", 1)
        await memory.set("search_b", 2)
        await memory.set("other", 3)

        results = await memory.search(pattern="search")

        assert len(results) == 2


class TestConversationMemory:
    """Tests for ConversationMemory."""

    @pytest.fixture
    def conv_memory(self):
        """Create fresh conversation memory."""
        SharedMemory._instance = None
        return ConversationMemory("conv-1")

    @pytest.mark.asyncio
    async def test_add_and_get_messages(self, conv_memory):
        """Test adding and retrieving messages."""
        await conv_memory.add_message("user", "Hello")
        await conv_memory.add_message("assistant", "Hi there!")

        messages = await conv_memory.get_messages()

        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == "Hi there!"

    @pytest.mark.asyncio
    async def test_get_messages_with_limit(self, conv_memory):
        """Test getting messages with limit."""
        for i in range(5):
            await conv_memory.add_message("user", f"Message {i}")

        messages = await conv_memory.get_messages(limit=2)

        assert len(messages) == 2
        assert messages[0]["content"] == "Message 3"
        assert messages[1]["content"] == "Message 4"

    @pytest.mark.asyncio
    async def test_get_messages_by_role(self, conv_memory):
        """Test filtering messages by role."""
        await conv_memory.add_message("user", "Question")
        await conv_memory.add_message("assistant", "Answer")
        await conv_memory.add_message("user", "Follow-up")

        user_messages = await conv_memory.get_messages(roles=["user"])

        assert len(user_messages) == 2
        assert all(m["role"] == "user" for m in user_messages)

    @pytest.mark.asyncio
    async def test_get_last_message(self, conv_memory):
        """Test getting the last message."""
        await conv_memory.add_message("user", "First")
        await conv_memory.add_message("assistant", "Last")

        last = await conv_memory.get_last_message()

        assert last["role"] == "assistant"
        assert last["content"] == "Last"

    @pytest.mark.asyncio
    async def test_get_last_message_by_role(self, conv_memory):
        """Test getting last message by specific role."""
        await conv_memory.add_message("user", "First user")
        await conv_memory.add_message("assistant", "Response")
        await conv_memory.add_message("user", "Last user")

        last_user = await conv_memory.get_last_message(role="user")

        assert last_user["content"] == "Last user"

    @pytest.mark.asyncio
    async def test_clear(self, conv_memory):
        """Test clearing conversation."""
        await conv_memory.add_message("user", "Test")
        await conv_memory.set_summary("Test summary")

        await conv_memory.clear()

        messages = await conv_memory.get_messages()
        summary = await conv_memory.get_summary()

        assert len(messages) == 0
        assert summary is None

    @pytest.mark.asyncio
    async def test_summary(self, conv_memory):
        """Test summary management."""
        await conv_memory.set_summary("This is a summary")
        summary = await conv_memory.get_summary()

        assert summary == "This is a summary"

    @pytest.mark.asyncio
    async def test_message_metadata(self, conv_memory):
        """Test message with metadata."""
        await conv_memory.add_message(
            "user", "Message with metadata", metadata={"source": "api", "priority": 1}
        )

        messages = await conv_memory.get_messages()

        assert messages[0]["metadata"]["source"] == "api"
        assert messages[0]["metadata"]["priority"] == 1


class TestGetSharedMemory:
    """Tests for the global accessor."""

    def test_returns_singleton(self):
        """Test that get_shared_memory returns same instance."""
        SharedMemory._instance = None

        mem1 = get_shared_memory()
        mem2 = get_shared_memory()

        assert mem1 is mem2
