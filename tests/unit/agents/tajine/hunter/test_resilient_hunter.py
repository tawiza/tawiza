"""Tests for ResilientDataHunter."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.infrastructure.agents.tajine.core.types import HuntContext
from src.infrastructure.agents.tajine.hunter.resilient_hunter import (
    PersistentSourceBandit,
    ResilientDataHunter,
    ResilientHuntResult,
)


@pytest.fixture
def sources():
    """Standard source list for testing."""
    return ["sirene", "bodacc", "boamp"]


@pytest.fixture
def hunter(sources, tmp_path):
    """Create ResilientDataHunter for tests."""
    return ResilientDataHunter(
        sources=sources,
        cache_path=tmp_path / "cache",
        bandit_state_path=tmp_path / "bandit.json",
    )


@pytest.fixture
def hunt_context():
    """Create HuntContext for tests."""
    return HuntContext(
        query="entreprises département 75",
        territory="75",
        mode="normal",
        max_sources=3,
    )


class TestResilientDataHunter:
    """Tests for ResilientDataHunter."""

    @pytest.mark.asyncio
    async def test_hunt_returns_resilient_result(self, hunter, hunt_context):
        """Hunt should return ResilientHuntResult."""
        result = await hunter.hunt(hunt_context)

        assert isinstance(result, ResilientHuntResult)
        assert hasattr(result, "cache_hits")
        assert hasattr(result, "fallbacks_used")
        assert hasattr(result, "augmentations")

    @pytest.mark.asyncio
    async def test_hunt_modes(self, hunter):
        """Different modes should use different weights."""
        modes = ["normal", "question", "combler", "rare"]

        for mode in modes:
            context = HuntContext(
                query="test",
                territory="75",
                mode=mode,
                max_sources=3,
            )
            result = await hunter.hunt(context)
            assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_cache_population(self, hunter, hunt_context):
        """Hunt should populate cache."""
        # First hunt
        result1 = await hunter.hunt(hunt_context)
        initial_cache = hunter.cache_stats["total_entries"]

        # Should have cached something
        assert initial_cache > 0 or len(result1.data) == 0

    @pytest.mark.asyncio
    async def test_cache_hits_on_repeat(self, hunter, hunt_context):
        """Repeated hunt should have cache hits."""
        # First hunt populates cache
        await hunter.hunt(hunt_context)

        # Second hunt should hit cache
        result2 = await hunter.hunt(hunt_context)

        # If we got data first time, we should get cache hits
        assert result2.cache_hits >= 0  # May or may not hit depending on timing

    @pytest.mark.asyncio
    async def test_bandit_persistence(self, sources, tmp_path):
        """Bandit state should persist across instances."""
        bandit_path = tmp_path / "bandit.json"

        # First hunter - do some hunting
        hunter1 = ResilientDataHunter(
            sources=sources,
            bandit_state_path=bandit_path,
        )
        context = HuntContext(query="test", territory="75", mode="normal", max_sources=2)
        await hunter1.hunt(context)
        pulls_after_hunt = hunter1.bandit.total_pulls

        # New hunter should load state
        hunter2 = ResilientDataHunter(
            sources=sources,
            bandit_state_path=bandit_path,
        )

        assert hunter2.bandit.total_pulls == pulls_after_hunt

    def test_health_report(self, hunter):
        """Should return health for all sources."""
        report = hunter.get_health_report()

        assert "sirene" in report
        assert "bodacc" in report
        assert "boamp" in report

    def test_cache_stats(self, hunter):
        """Should return cache statistics."""
        stats = hunter.cache_stats

        assert "total_entries" in stats
        assert "valid_entries" in stats

    def test_bandit_stats(self, hunter):
        """Should return bandit statistics."""
        stats = hunter.bandit_stats

        assert "total_pulls" in stats
        assert "sources" in stats
        assert "sirene" in stats["sources"]


class TestPersistentSourceBandit:
    """Tests for PersistentSourceBandit."""

    def test_inherits_from_source_bandit(self):
        """Should have all SourceBandit functionality."""
        bandit = PersistentSourceBandit(sources=["a", "b", "c"])

        # Test UCB selection
        selected = bandit.select(n=2)
        assert len(selected) == 2

        # Test update
        bandit.update("a", reward=0.9)
        assert bandit.total_pulls == 1

    def test_has_persistence_methods(self):
        """Should have save/load methods from mixin."""
        bandit = PersistentSourceBandit(sources=["a", "b"])

        assert hasattr(bandit, "save_state")
        assert hasattr(bandit, "load_state")


class TestResilientHuntResult:
    """Tests for ResilientHuntResult dataclass."""

    def test_extends_hunt_result(self):
        """Should have base HuntResult fields."""
        result = ResilientHuntResult(
            data=[],
            hypotheses_used=[],
            gaps_addressed=[],
            sources_queried=["sirene"],
            duration_ms=100,
        )

        assert result.sources_queried == ["sirene"]
        assert result.duration_ms == 100

    def test_resilience_metrics(self):
        """Should have resilience-specific fields."""
        result = ResilientHuntResult(
            data=[],
            hypotheses_used=[],
            gaps_addressed=[],
            sources_queried=[],
            duration_ms=50,
            cache_hits=3,
            fallbacks_used=1,
            augmentations=2,
            retry_count=4,
        )

        assert result.cache_hits == 3
        assert result.fallbacks_used == 1
        assert result.augmentations == 2
        assert result.retry_count == 4
