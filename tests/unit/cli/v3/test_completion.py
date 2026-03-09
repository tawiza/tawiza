"""Tests for CLI v3 completion system."""

import tempfile
from pathlib import Path

import pytest

from src.cli.v3.completion.base import CompletionResult
from src.cli.v3.completion.cache import CompletionCache
from src.cli.v3.completion.providers.contextual import HistoryProvider
from src.cli.v3.completion.providers.static import STATIC_COMPLETIONS, StaticProvider
from src.cli.v3.completion.registry import complete, register_completer


class TestStaticProvider:
    """Tests for StaticProvider."""

    def test_get_agents(self):
        """Should return agent completions."""
        provider = StaticProvider("agents")
        results = provider.get_completions("")

        values = [r.value for r in results]
        assert "manus" in values
        assert "s3" in values
        assert "analyst" in values

    def test_filter_by_prefix(self):
        """Should filter by incomplete string."""
        provider = StaticProvider("agents")
        results = provider.get_completions("ma")

        values = [r.value for r in results]
        assert "manus" in values
        assert "s3" not in values  # Doesn't match "ma"

    def test_prefix_match_higher_score(self):
        """Prefix matches should have higher score."""
        provider = StaticProvider("agents")
        results = provider.get_completions("m")

        # Find manus (prefix match) and ml (prefix match)
        manus = next((r for r in results if r.value == "manus"), None)
        ml = next((r for r in results if r.value == "ml"), None)

        assert manus is not None
        assert manus.score == 2.0  # Prefix match bonus

    def test_includes_description(self):
        """Should include descriptions."""
        provider = StaticProvider("agents")
        results = provider.get_completions("manus")

        manus = next((r for r in results if r.value == "manus"), None)
        assert manus is not None
        assert manus.description is not None


class TestCompletionCache:
    """Tests for CompletionCache."""

    def test_set_and_get(self):
        """Should store and retrieve values."""
        cache = CompletionCache()
        cache.set("test_key", ["a", "b", "c"], ttl=60)

        result = cache.get("test_key")
        assert result == ["a", "b", "c"]

    def test_expired_entry(self):
        """Should return None for expired entries."""
        cache = CompletionCache()
        cache.set("test_key", ["a"], ttl=0)  # Expire immediately

        import time

        time.sleep(0.1)

        result = cache.get("test_key")
        assert result is None

    def test_invalidate_all(self):
        """Should clear all entries."""
        cache = CompletionCache()
        cache.set("key1", ["a"], ttl=60)
        cache.set("key2", ["b"], ttl=60)

        count = cache.invalidate()
        assert count == 2
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_invalidate_pattern(self):
        """Should clear matching entries."""
        cache = CompletionCache()
        cache.set("models:ollama", ["a"], ttl=60)
        cache.set("models:openai", ["b"], ttl=60)
        cache.set("agents:list", ["c"], ttl=60)

        count = cache.invalidate("models")
        assert count == 2
        assert cache.get("models:ollama") is None
        assert cache.get("agents:list") == ["c"]

    def test_stats(self):
        """Should return cache statistics."""
        cache = CompletionCache()
        cache.set("key1", ["a"], ttl=60)
        cache.set("key2", ["b"], ttl=60)

        stats = cache.stats()
        assert stats["total_entries"] == 2
        assert stats["valid_entries"] == 2


class TestHistoryProvider:
    """Tests for HistoryProvider."""

    @pytest.fixture
    def temp_history(self):
        """Create temporary history file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            history_file = Path(tmpdir) / "history.json"
            provider = HistoryProvider(history_file)
            yield provider

    def test_record_command(self, temp_history):
        """Should record command to history."""
        temp_history.record_command(
            command="agent-run",
            args={"agent": "manus", "task": "test task"},
            success=True,
            duration=10.5,
        )

        # File should be created
        assert temp_history.history_file.exists()

    def test_get_completions_from_history(self, temp_history):
        """Should return completions from history."""
        # Record some commands
        temp_history.record_command("agent-run", {"agent": "manus"})
        temp_history.record_command("agent-run", {"agent": "manus"})
        temp_history.record_command("agent-run", {"agent": "s3"})

        results = temp_history.get_completions(
            "", context={"command": "agent-run", "arg_name": "agent"}
        )

        # manus should appear (used more frequently)
        values = [r.value for r in results]
        assert "manus" in values


class TestCompletionRegistry:
    """Tests for completion registry."""

    def test_complete_agents(self):
        """Should return agent completions."""
        results = complete("agents", "")

        values = [r.value for r in results]
        assert "manus" in values

    def test_complete_with_filter(self):
        """Should filter by incomplete string."""
        results = complete("agents", "bro")

        values = [r.value for r in results]
        assert "browser" in values
        assert "manus" not in values

    def test_max_results(self):
        """Should respect max_results limit."""
        results = complete("agents", "", max_results=3)

        assert len(results) <= 3

    def test_deduplicates_results(self):
        """Should not have duplicate values."""
        results = complete("agents", "")

        values = [r.value for r in results]
        assert len(values) == len(set(values))
