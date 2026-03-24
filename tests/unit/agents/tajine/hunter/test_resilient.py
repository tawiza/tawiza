"""Tests for Resilient DataHunter components."""

import json
import tempfile
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.infrastructure.agents.tajine.core.types import RawData
from src.infrastructure.agents.tajine.hunter.bandit import SourceBandit
from src.infrastructure.agents.tajine.hunter.resilient import (
    FALLBACK_CHAINS,
    AugmentedData,
    CacheEntry,
    DataCache,
    FallbackSourceChain,
    FetchResult,
    PersistentBanditMixin,
    RareDataAugmenter,
    ResilientFetcher,
)

# === Fixtures ===


@pytest.fixture
def sample_raw_data():
    """Create sample RawData for tests."""
    return RawData(
        source="sirene",
        content={"siren": "123456782", "nom": "Test Company"},
        url="https://api.sirene.fr/test",
        fetched_at=datetime.now(UTC),
        quality_hint=0.8,
    )


@pytest.fixture
def temp_cache_path(tmp_path):
    """Create temporary path for cache tests."""
    return tmp_path / "cache.json"


@pytest.fixture
def temp_bandit_path(tmp_path):
    """Create temporary path for bandit state tests."""
    return tmp_path / "bandit_state.json"


# === ResilientFetcher Tests ===


class TestResilientFetcher:
    """Tests for ResilientFetcher."""

    @pytest.mark.asyncio
    async def test_successful_fetch(self):
        """Successful fetch should return success result."""
        fetcher = ResilientFetcher()

        async def mock_fetch():
            return RawData(
                source="test",
                content={"data": "value"},
                url="https://test.com",
                fetched_at=datetime.now(UTC),
                quality_hint=0.9,
            )

        result = await fetcher.fetch(mock_fetch, source="test")

        assert result.success
        assert result.data is not None
        assert result.source_used == "test"

    @pytest.mark.asyncio
    async def test_failed_fetch_records_failure(self):
        """Failed fetch should return failure result."""
        fetcher = ResilientFetcher(retry_attempts=2)

        async def failing_fetch():
            raise ConnectionError("Network error")

        result = await fetcher.fetch(failing_fetch, source="failing")

        assert not result.success
        assert result.error is not None
        assert "Network error" in result.error

    @pytest.mark.asyncio
    async def test_source_health_tracking(self):
        """Source health should be tracked."""
        fetcher = ResilientFetcher()

        async def mock_fetch():
            return RawData(
                source="tracked",
                content={},
                url="",
                fetched_at=datetime.now(UTC),
                quality_hint=0.5,
            )

        await fetcher.fetch(mock_fetch, source="tracked")

        health = fetcher.get_source_health("tracked")
        assert "status" in health
        assert health["healthy"]

    def test_unknown_source_health(self):
        """Unknown source should return unknown status."""
        fetcher = ResilientFetcher()
        health = fetcher.get_source_health("unknown")

        assert health["status"] == "unknown"
        assert health["healthy"]


# === FallbackSourceChain Tests ===


class TestFallbackSourceChain:
    """Tests for FallbackSourceChain."""

    def test_get_fallbacks_known_source(self):
        """Should return fallbacks for known sources."""
        chain = FallbackSourceChain()

        fallbacks = chain.get_fallbacks("sirene")

        assert len(fallbacks) > 0
        assert "insee_api" in fallbacks or "pappers" in fallbacks

    def test_get_fallbacks_unknown_source(self):
        """Should return default fallbacks for unknown sources."""
        chain = FallbackSourceChain()

        fallbacks = chain.get_fallbacks("unknown_source")

        assert len(fallbacks) > 0  # Should use default chain

    @pytest.mark.asyncio
    async def test_fallback_on_primary_failure(self):
        """Should try fallback when primary fails."""
        chain = FallbackSourceChain()
        call_log = []

        async def mock_fetch(source: str):
            call_log.append(source)
            if source == "sirene":
                raise ConnectionError("Primary failed")
            return RawData(
                source=source,
                content={"from": "fallback"},
                url="",
                fetched_at=datetime.now(UTC),
                quality_hint=0.7,
            )

        result = await chain.fetch_with_fallback(
            mock_fetch,
            source="sirene",
            max_fallbacks=1,
        )

        assert result.success
        assert len(result.fallbacks_tried) > 0
        assert "sirene" in call_log


# === DataCache Tests ===


class TestDataCache:
    """Tests for DataCache."""

    def test_put_and_get(self, sample_raw_data):
        """Should store and retrieve data."""
        cache = DataCache()

        cache.put(sample_raw_data, query="test query", territory="75")

        result = cache.get("sirene", "test query", "75")

        assert result is not None
        assert result.source == "sirene"

    def test_cache_miss(self):
        """Should return None for missing entries."""
        cache = DataCache()

        result = cache.get("unknown", "query", "territory")

        assert result is None

    def test_ttl_expiration(self, sample_raw_data):
        """Expired entries should not be returned."""
        cache = DataCache()

        # Create expired entry directly
        key = cache._make_key("sirene", "query", "")
        cache._cache[key] = CacheEntry(
            data=sample_raw_data,
            cached_at=datetime.now(UTC) - timedelta(hours=48),
            ttl_seconds=3600,  # 1 hour TTL, expired
        )

        result = cache.get("sirene", "query", "")

        assert result is None
        assert key not in cache._cache  # Should be evicted

    def test_max_entries_eviction(self, sample_raw_data):
        """Should evict oldest when at capacity."""
        cache = DataCache(max_entries=3)

        for i in range(5):
            data = RawData(
                source=f"source_{i}",
                content={"i": i},
                url="",
                fetched_at=datetime.now(UTC),
                quality_hint=0.5,
            )
            cache.put(data, query=f"query_{i}")

        assert len(cache._cache) <= 3

    def test_persistence(self, sample_raw_data, temp_cache_path):
        """Should persist and load cache."""
        # Save
        cache1 = DataCache(persist_path=temp_cache_path)
        cache1.put(sample_raw_data, query="persistent query")

        # Load in new instance
        cache2 = DataCache(persist_path=temp_cache_path)

        result = cache2.get("sirene", "persistent query", "")

        assert result is not None
        assert result.source == "sirene"

    def test_cache_stats(self, sample_raw_data):
        """Should report accurate statistics."""
        cache = DataCache()
        cache.put(sample_raw_data, query="q1")
        cache.put(sample_raw_data, query="q2")

        stats = cache.stats

        assert stats["total_entries"] == 2
        assert stats["valid_entries"] == 2

    def test_clear_cache(self, sample_raw_data):
        """Should clear all entries."""
        cache = DataCache()
        cache.put(sample_raw_data, query="to_clear")

        cache.clear()

        assert len(cache._cache) == 0


# === RareDataAugmenter Tests ===


class TestRareDataAugmenter:
    """Tests for RareDataAugmenter."""

    @pytest.mark.asyncio
    async def test_augment_with_complete_primary(self, sample_raw_data):
        """Complete primary data should need no augmentation."""
        augmenter = RareDataAugmenter()

        result = await augmenter.augment(
            primary=sample_raw_data,
            supplementary=[],
            target_fields=["siren", "nom"],
        )

        assert result.primary == sample_raw_data
        assert result.augmentation_method == "none"
        assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_augment_triangulates_sources(self):
        """Should merge data from multiple sources."""
        augmenter = RareDataAugmenter()

        primary = RawData(
            source="source1",
            content={"field1": "value1"},
            url="",
            fetched_at=datetime.now(UTC),
            quality_hint=0.7,
        )

        supplement = RawData(
            source="source2",
            content={"field2": "value2"},
            url="",
            fetched_at=datetime.now(UTC),
            quality_hint=0.6,
        )

        result = await augmenter.augment(
            primary=primary,
            supplementary=[supplement],
        )

        # Should have merged content
        assert result.primary.content.get("field1") == "value1"
        assert result.primary.content.get("field2") == "value2"
        assert len(result.supplements) == 1

    @pytest.mark.asyncio
    async def test_augment_no_data_returns_empty(self):
        """No data should return failed augmentation."""
        augmenter = RareDataAugmenter()

        result = await augmenter.augment(
            primary=None,
            supplementary=[],
        )

        assert result.confidence == 0.0
        assert result.augmentation_method == "failed"

    @pytest.mark.asyncio
    async def test_augment_from_supplements_only(self):
        """Should use best supplement as primary when no primary."""
        augmenter = RareDataAugmenter()

        supplements = [
            RawData(
                source="low_quality",
                content={"q": "low"},
                url="",
                fetched_at=datetime.now(UTC),
                quality_hint=0.3,
            ),
            RawData(
                source="high_quality",
                content={"q": "high"},
                url="",
                fetched_at=datetime.now(UTC),
                quality_hint=0.9,
            ),
        ]

        result = await augmenter.augment(
            primary=None,
            supplementary=supplements,
        )

        # Should use high quality as primary (may have +triangulated suffix)
        assert result.primary.source.startswith("high_quality")


# === PersistentBanditMixin Tests ===


class TestPersistentBanditMixin:
    """Tests for PersistentBanditMixin."""

    def test_save_and_load_state(self, temp_bandit_path):
        """Should save and load bandit state."""
        sources = ["sirene", "bodacc", "boamp"]

        # Create mixin class for testing
        class TestBandit(SourceBandit, PersistentBanditMixin):
            pass

        # Train and save
        bandit1 = TestBandit(sources=sources)
        bandit1.update("sirene", reward=0.9)
        bandit1.update("sirene", reward=0.8)
        bandit1.update("bodacc", reward=0.5)
        bandit1.save_state(temp_bandit_path)

        # Load in new instance
        bandit2 = TestBandit(sources=sources)
        loaded = bandit2.load_state(temp_bandit_path)

        assert loaded
        assert bandit2.total_pulls == 3
        assert bandit2.arm_counts[0] == 2  # sirene
        assert bandit2.arm_counts[1] == 1  # bodacc

    def test_load_missing_file(self, temp_bandit_path):
        """Should return False for missing file."""

        class TestBandit(SourceBandit, PersistentBanditMixin):
            pass

        bandit = TestBandit(sources=["a", "b"])
        loaded = bandit.load_state(temp_bandit_path)

        assert not loaded

    def test_load_mismatched_sources(self, temp_bandit_path):
        """Should reject state with different sources."""

        class TestBandit(SourceBandit, PersistentBanditMixin):
            pass

        # Save with one set of sources
        bandit1 = TestBandit(sources=["a", "b"])
        bandit1.save_state(temp_bandit_path)

        # Try to load with different sources
        bandit2 = TestBandit(sources=["x", "y", "z"])
        loaded = bandit2.load_state(temp_bandit_path)

        assert not loaded


# === FetchResult Tests ===


class TestFetchResult:
    """Tests for FetchResult dataclass."""

    def test_default_values(self):
        """Should have sensible defaults."""
        result = FetchResult(success=True)

        assert result.data is None
        assert result.source_used == ""
        assert result.attempts == 0
        assert result.fallbacks_tried == []
        assert not result.from_cache

    def test_failure_with_error(self):
        """Failed result should have error."""
        result = FetchResult(
            success=False,
            error="Connection timeout",
        )

        assert not result.success
        assert "timeout" in result.error.lower()


# === FALLBACK_CHAINS Tests ===


class TestFallbackChains:
    """Tests for fallback chain configuration."""

    def test_sirene_has_fallbacks(self):
        """Sirene should have fallback sources."""
        assert "sirene" in FALLBACK_CHAINS
        assert len(FALLBACK_CHAINS["sirene"]) >= 2

    def test_default_chain_exists(self):
        """Default chain should exist for unknown sources."""
        assert "default" in FALLBACK_CHAINS

    def test_no_circular_fallbacks(self):
        """Fallback chains should not be circular."""
        for source, fallbacks in FALLBACK_CHAINS.items():
            if source != "default":
                assert source not in fallbacks, f"Circular fallback: {source}"
