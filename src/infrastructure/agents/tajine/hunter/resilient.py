"""Resilient Data Hunting - Retry, fallback, and cache strategies for rare data.

This module provides robust data fetching with:
- ResilientFetcher: Retry with exponential backoff + circuit breaker
- FallbackSourceChain: Alternative sources when primary fails
- DataCache: TTL-based caching to avoid refetching
- RareDataAugmenter: Cross-source triangulation for scarce data
"""
from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.infrastructure.agents.resilience.retry import (
    CircuitBreakerConfig,
    ResilientExecutor,
    RetryConfig,
    RetryStrategy,
)
from src.infrastructure.agents.tajine.core.types import RawData

logger = logging.getLogger(__name__)


# === Fallback Source Chains ===

FALLBACK_CHAINS: dict[str, list[str]] = {
    # Primary -> Fallbacks for French business data
    "sirene": ["insee_api", "data_gouv_sirene", "pappers"],
    "bodacc": ["infogreffe", "pappers", "societe_com"],
    "boamp": ["data_gouv_boamp", "marches_publics"],
    "infogreffe": ["pappers", "societe_com", "bodacc"],
    "ban": ["data_gouv_adresse", "nominatim"],

    # Fallback for unknown sources
    "default": ["sirene", "data_gouv"],
}


@dataclass
class FetchResult:
    """Result of a resilient fetch operation."""
    success: bool
    data: RawData | None = None
    source_used: str = ""
    attempts: int = 0
    fallbacks_tried: list[str] = field(default_factory=list)
    error: str | None = None
    from_cache: bool = False
    duration_ms: int = 0


class ResilientFetcher:
    """
    Wraps data fetching with retry and circuit breaker.

    Features:
    - Exponential backoff with jitter
    - Circuit breaker to avoid hammering failing sources
    - Per-source circuit isolation
    """

    def __init__(
        self,
        retry_attempts: int = 3,
        retry_backoff: float = 1.0,
        circuit_failure_threshold: int = 5,
        circuit_timeout: float = 60.0,
    ):
        self.retry_config = RetryConfig(
            max_attempts=retry_attempts,
            backoff_base=retry_backoff,
            strategy=RetryStrategy.EXPONENTIAL_JITTER,
        )
        self.circuit_config = CircuitBreakerConfig(
            failure_threshold=circuit_failure_threshold,
            timeout=circuit_timeout,
        )

        # Per-source executors for circuit isolation
        self._executors: dict[str, ResilientExecutor] = {}

    def _get_executor(self, source: str) -> ResilientExecutor:
        """Get or create executor for source."""
        if source not in self._executors:
            self._executors[source] = ResilientExecutor(
                name=f"source_{source}",
                retry_config=self.retry_config,
                circuit_config=self.circuit_config,
            )
        return self._executors[source]

    async def fetch(
        self,
        fetch_func: Callable,
        source: str,
        fallback_func: Callable | None = None,
        **kwargs,
    ) -> FetchResult:
        """
        Fetch with resilience.

        Args:
            fetch_func: Async function to fetch data
            source: Source identifier
            fallback_func: Optional fallback if all retries fail
            **kwargs: Arguments to pass to fetch_func
        """
        start = datetime.now(UTC)
        executor = self._get_executor(source)

        try:
            result = await executor.execute(
                fetch_func,
                **kwargs,
                fallback=fallback_func,
            )

            duration = int((datetime.now(UTC) - start).total_seconds() * 1000)

            return FetchResult(
                success=True,
                data=result,
                source_used=source,
                attempts=executor.retry_handler._stats.get("total_retries", 0) + 1,
                duration_ms=duration,
            )

        except Exception as e:
            duration = int((datetime.now(UTC) - start).total_seconds() * 1000)
            logger.warning(f"Resilient fetch failed for {source}: {e}")

            return FetchResult(
                success=False,
                error=str(e),
                source_used=source,
                attempts=self.retry_config.max_attempts,
                duration_ms=duration,
            )

    def get_source_health(self, source: str) -> dict:
        """Get health status for a source."""
        if source not in self._executors:
            return {"status": "unknown", "healthy": True}

        executor = self._executors[source]
        return {
            "status": executor.circuit_breaker.state.value,
            "healthy": executor.is_healthy,
            **executor.stats,
        }


class FallbackSourceChain:
    """
    Manages fallback source chains for resilient data fetching.

    When primary source fails, automatically tries alternatives.
    """

    def __init__(
        self,
        chains: dict[str, list[str]] | None = None,
        fetcher: ResilientFetcher | None = None,
    ):
        self.chains = chains or FALLBACK_CHAINS
        self.fetcher = fetcher or ResilientFetcher()

    def get_fallbacks(self, source: str) -> list[str]:
        """Get fallback sources for a primary source."""
        return self.chains.get(source, self.chains.get("default", []))

    async def fetch_with_fallback(
        self,
        fetch_func: Callable,
        source: str,
        max_fallbacks: int = 2,
        **kwargs,
    ) -> FetchResult:
        """
        Fetch from source with automatic fallback.

        Args:
            fetch_func: Async function(source, **kwargs) -> RawData
            source: Primary source to try
            max_fallbacks: Maximum number of fallbacks to try
            **kwargs: Arguments to pass to fetch_func
        """
        start = datetime.now(UTC)
        fallbacks_tried = []

        # Try primary source
        async def source_fetch():
            return await fetch_func(source=source, **kwargs)

        result = await self.fetcher.fetch(
            source_fetch,
            source=source,
        )

        if result.success:
            return result

        # Try fallbacks
        for fallback in self.get_fallbacks(source)[:max_fallbacks]:
            fallbacks_tried.append(fallback)

            logger.info(f"Trying fallback source: {fallback} (primary: {source})")

            async def fallback_fetch(fb=fallback):
                return await fetch_func(source=fb, **kwargs)

            result = await self.fetcher.fetch(
                fallback_fetch,
                source=fallback,
            )

            if result.success:
                result.fallbacks_tried = fallbacks_tried
                return result

        # All failed
        duration = int((datetime.now(UTC) - start).total_seconds() * 1000)

        return FetchResult(
            success=False,
            source_used=source,
            fallbacks_tried=fallbacks_tried,
            error=f"All sources failed: {source} + {fallbacks_tried}",
            duration_ms=duration,
        )


# === Data Cache ===

@dataclass
class CacheEntry:
    """A cached data entry."""
    data: RawData
    cached_at: datetime
    ttl_seconds: int

    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        now = datetime.now(UTC)
        cached = self.cached_at
        if cached.tzinfo is None:
            cached = cached.replace(tzinfo=UTC)
        return (now - cached).total_seconds() > self.ttl_seconds


class DataCache:
    """
    TTL-based cache for fetched data.

    Avoids refetching recent data, especially important for
    rate-limited APIs.
    """

    # Default TTLs by source type (seconds)
    DEFAULT_TTLS = {
        "sirene": 86400,      # 24 hours (official data, rarely changes)
        "bodacc": 3600,       # 1 hour (announcements)
        "boamp": 3600,        # 1 hour (public markets)
        "infogreffe": 86400,  # 24 hours
        "web": 1800,          # 30 minutes (web scraping)
        "default": 3600,      # 1 hour
    }

    def __init__(
        self,
        max_entries: int = 1000,
        persist_path: Path | None = None,
        ttls: dict[str, int] | None = None,
    ):
        self.max_entries = max_entries
        self.persist_path = persist_path
        self.ttls = {**self.DEFAULT_TTLS, **(ttls or {})}

        self._cache: dict[str, CacheEntry] = {}

        if persist_path and persist_path.exists():
            self._load()

    def _make_key(self, source: str, query: str, territory: str = "") -> str:
        """Create cache key from parameters."""
        raw = f"{source}:{query}:{territory}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get(
        self,
        source: str,
        query: str,
        territory: str = "",
    ) -> RawData | None:
        """Get cached data if available and not expired."""
        key = self._make_key(source, query, territory)

        entry = self._cache.get(key)
        if entry is None:
            return None

        if entry.is_expired:
            del self._cache[key]
            return None

        logger.debug(f"Cache hit for {source}:{query[:30]}...")
        return entry.data

    def put(
        self,
        data: RawData,
        query: str,
        territory: str = "",
        ttl: int | None = None,
    ):
        """Store data in cache."""
        key = self._make_key(data.source, query, territory)

        # Evict oldest if at capacity
        if len(self._cache) >= self.max_entries:
            self._evict_oldest()

        effective_ttl = ttl or self.ttls.get(data.source, self.ttls["default"])

        self._cache[key] = CacheEntry(
            data=data,
            cached_at=datetime.now(UTC),
            ttl_seconds=effective_ttl,
        )

        if self.persist_path:
            self._save()

    def _evict_oldest(self):
        """Remove oldest cache entry."""
        if not self._cache:
            return

        oldest_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].cached_at,
        )
        del self._cache[oldest_key]

    def clear(self):
        """Clear all cached data."""
        self._cache.clear()
        if self.persist_path and self.persist_path.exists():
            self.persist_path.unlink()

    def _save(self):
        """Persist cache to disk."""
        if not self.persist_path:
            return

        try:
            serializable = {}
            for key, entry in self._cache.items():
                serializable[key] = {
                    "data": {
                        "source": entry.data.source,
                        "content": entry.data.content,
                        "url": entry.data.url,
                        "fetched_at": entry.data.fetched_at.isoformat(),
                        "quality_hint": entry.data.quality_hint,
                    },
                    "cached_at": entry.cached_at.isoformat(),
                    "ttl_seconds": entry.ttl_seconds,
                }

            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            self.persist_path.write_text(json.dumps(serializable, indent=2))

        except Exception as e:
            logger.warning(f"Failed to persist cache: {e}")

    def _load(self):
        """Load cache from disk."""
        if not self.persist_path or not self.persist_path.exists():
            return

        try:
            data = json.loads(self.persist_path.read_text())

            for key, entry_data in data.items():
                raw = entry_data["data"]
                self._cache[key] = CacheEntry(
                    data=RawData(
                        source=raw["source"],
                        content=raw["content"],
                        url=raw["url"],
                        fetched_at=datetime.fromisoformat(raw["fetched_at"]),
                        quality_hint=raw["quality_hint"],
                    ),
                    cached_at=datetime.fromisoformat(entry_data["cached_at"]),
                    ttl_seconds=entry_data["ttl_seconds"],
                )

            logger.info(f"Loaded {len(self._cache)} cache entries")

        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")

    @property
    def stats(self) -> dict:
        """Get cache statistics."""
        expired = sum(1 for e in self._cache.values() if e.is_expired)
        return {
            "total_entries": len(self._cache),
            "expired_entries": expired,
            "valid_entries": len(self._cache) - expired,
        }


# === Rare Data Augmentation ===

@dataclass
class AugmentedData:
    """Data augmented from multiple sources."""
    primary: RawData
    supplements: list[RawData] = field(default_factory=list)
    inferred_fields: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    augmentation_method: str = "none"


class RareDataAugmenter:
    """
    Strategies for handling scarce data situations.

    When primary sources yield little data:
    1. Cross-source triangulation: Merge from multiple sources
    2. Historical projection: Use past data with decay
    3. Field inference: Use LLM to infer missing fields
    """

    def __init__(
        self,
        llm_client=None,
        min_confidence: float = 0.5,
    ):
        self.llm = llm_client
        self.min_confidence = min_confidence

    async def augment(
        self,
        primary: RawData | None,
        supplementary: list[RawData],
        target_fields: list[str] | None = None,
    ) -> AugmentedData:
        """
        Augment primary data with supplementary sources.

        Args:
            primary: Primary data (may be None or sparse)
            supplementary: Additional data from other sources
            target_fields: Fields we're trying to fill
        """
        if primary is None and not supplementary:
            return AugmentedData(
                primary=self._create_empty_data(),
                confidence=0.0,
                augmentation_method="failed",
            )

        # If we have a good primary and no supplements, minimal augmentation
        if primary and not supplementary and self._is_complete(primary, target_fields):
            return AugmentedData(
                primary=primary,
                confidence=1.0,
                augmentation_method="none",
            )

        # Cross-source triangulation
        merged, supplements_used = await self._triangulate(primary, supplementary)

        # Field inference for remaining gaps
        inferred = {}
        if self.llm and target_fields:
            inferred = await self._infer_missing_fields(merged, target_fields)

        # Calculate confidence based on source agreement
        confidence = self._calculate_confidence(merged, supplements_used, inferred)

        return AugmentedData(
            primary=merged,
            supplements=supplements_used,
            inferred_fields=inferred,
            confidence=confidence,
            augmentation_method="triangulation" if supplements_used else "inference",
        )

    def _is_complete(
        self,
        data: RawData,
        target_fields: list[str] | None,
    ) -> bool:
        """Check if data has all target fields."""
        if not target_fields:
            return True

        content = data.content
        if not isinstance(content, dict):
            return False

        return all(
            content.get(f) is not None
            for f in target_fields
        )

    async def _triangulate(
        self,
        primary: RawData | None,
        supplementary: list[RawData],
    ) -> tuple[RawData, list[RawData]]:
        """
        Merge data from multiple sources.

        Priority: Primary > High-quality supplementary > Others
        """
        if not primary and not supplementary:
            return self._create_empty_data(), []

        if not primary:
            # Use best supplementary as base
            supplementary.sort(key=lambda d: d.quality_hint, reverse=True)
            primary = supplementary.pop(0)

        if not supplementary:
            return primary, []

        # Merge supplementary into primary
        merged_content = dict(primary.content) if isinstance(primary.content, dict) else {}
        used_supplements = []

        for supp in supplementary:
            if not isinstance(supp.content, dict):
                continue

            added_fields = False
            for key, value in supp.content.items():
                if key not in merged_content or merged_content[key] is None:
                    merged_content[key] = value
                    added_fields = True

            if added_fields:
                used_supplements.append(supp)

        merged = RawData(
            source=f"{primary.source}+triangulated",
            content=merged_content,
            url=primary.url,
            fetched_at=primary.fetched_at,
            quality_hint=min(0.95, primary.quality_hint + 0.05 * len(used_supplements)),
        )

        return merged, used_supplements

    async def _infer_missing_fields(
        self,
        data: RawData,
        target_fields: list[str],
    ) -> dict[str, Any]:
        """Use LLM to infer missing fields."""
        if not self.llm:
            return {}

        content = data.content if isinstance(data.content, dict) else {}
        missing = [f for f in target_fields if content.get(f) is None]

        if not missing:
            return {}

        # Prepare context for inference
        {
            "source": data.source,
            "known_fields": {k: v for k, v in content.items() if v is not None},
            "missing_fields": missing,
        }

        try:
            # This would call the LLM to infer
            # For now, return empty (requires LLM integration)
            logger.debug(f"Would infer fields: {missing} from context")
            return {}

        except Exception as e:
            logger.warning(f"Field inference failed: {e}")
            return {}

    def _calculate_confidence(
        self,
        merged: RawData,
        supplements: list[RawData],
        inferred: dict,
    ) -> float:
        """Calculate confidence score for augmented data."""
        base = merged.quality_hint

        # Boost for corroboration
        if supplements:
            base = min(0.95, base + 0.03 * len(supplements))

        # Penalty for inferred fields
        if inferred:
            base *= (1.0 - 0.1 * len(inferred))

        return round(max(0.0, min(1.0, base)), 3)

    def _create_empty_data(self) -> RawData:
        """Create empty RawData for failed augmentation."""
        return RawData(
            source="none",
            content={},
            url="",
            fetched_at=datetime.now(UTC),
            quality_hint=0.0,
        )


# === Persistent Bandit ===

class PersistentBanditMixin:
    """
    Mixin to add persistence to SourceBandit.

    Saves/loads bandit state to preserve learning across sessions.
    """

    def save_state(self, path: Path):
        """Save bandit state to file."""
        state = {
            "sources": self.sources,
            "exploration_factor": self.exploration_factor,
            "arm_counts": self.arm_counts,
            "arm_rewards": self.arm_rewards,
            "total_pulls": self.total_pulls,
            "saved_at": datetime.now(UTC).isoformat(),
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2))
        logger.info(f"Saved bandit state to {path}")

    def load_state(self, path: Path) -> bool:
        """Load bandit state from file."""
        if not path.exists():
            return False

        try:
            state = json.loads(path.read_text())

            # Validate sources match
            if state["sources"] != self.sources:
                logger.warning("Bandit sources changed, resetting state")
                return False

            self.arm_counts = state["arm_counts"]
            self.arm_rewards = state["arm_rewards"]
            self.total_pulls = state["total_pulls"]

            logger.info(f"Loaded bandit state ({self.total_pulls} total pulls)")
            return True

        except Exception as e:
            logger.warning(f"Failed to load bandit state: {e}")
            return False
