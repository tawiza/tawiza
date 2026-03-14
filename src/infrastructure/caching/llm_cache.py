"""
LLM Response Cache - Intelligent caching for language model responses

This module provides semantic caching for LLM responses, allowing:
- Cache based on prompt + model + parameters hash
- Multi-level cache support (L1/L2/L3)
- Configurable TTL per model type
- Streaming response caching
- Cache invalidation by pattern

Usage:
    cache = LLMCache(enable_redis=True)
    await cache.connect()

    # Check cache before calling LLM
    cached = await cache.get(prompt, model, temperature)
    if cached:
        return cached

    # Call LLM and cache response
    response = await ollama.generate(prompt, model, temperature)
    await cache.set(prompt, model, temperature, response)
"""

import hashlib
import json
from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import Any

from loguru import logger

from .multi_level_cache import MultiLevelCache


class CacheStrategy(StrEnum):
    """Cache strategy for different use cases."""

    # Cache aggressively - deterministic responses
    AGGRESSIVE = "aggressive"

    # Cache with shorter TTL - semi-deterministic
    MODERATE = "moderate"

    # No caching - highly dynamic
    NONE = "none"


@dataclass
class CacheConfig:
    """Configuration for LLM caching per model type."""

    strategy: CacheStrategy
    l1_ttl: int  # seconds
    l2_ttl: int  # seconds
    l3_ttl: int  # seconds (Redis)

    # Temperature threshold: only cache if temperature <= this
    max_cacheable_temperature: float = 0.3


# Default cache configs per model type
DEFAULT_CACHE_CONFIGS = {
    # Embedding models - highly deterministic
    "embedding": CacheConfig(
        strategy=CacheStrategy.AGGRESSIVE,
        l1_ttl=3600,  # 1 hour
        l2_ttl=86400,  # 24 hours
        l3_ttl=604800,  # 1 week
        max_cacheable_temperature=1.0,  # Always cache
    ),
    # Code models - semi-deterministic at low temperature
    "code": CacheConfig(
        strategy=CacheStrategy.MODERATE,
        l1_ttl=600,  # 10 minutes
        l2_ttl=3600,  # 1 hour
        l3_ttl=86400,  # 24 hours
        max_cacheable_temperature=0.3,
    ),
    # Chat models - cache only at very low temperature
    "chat": CacheConfig(
        strategy=CacheStrategy.MODERATE,
        l1_ttl=300,  # 5 minutes
        l2_ttl=1800,  # 30 minutes
        l3_ttl=7200,  # 2 hours
        max_cacheable_temperature=0.1,
    ),
    # Vision models - semi-deterministic
    "vision": CacheConfig(
        strategy=CacheStrategy.MODERATE,
        l1_ttl=600,  # 10 minutes
        l2_ttl=3600,  # 1 hour
        l3_ttl=14400,  # 4 hours
        max_cacheable_temperature=0.3,
    ),
    # Default for unknown model types
    "default": CacheConfig(
        strategy=CacheStrategy.MODERATE,
        l1_ttl=300,
        l2_ttl=1800,
        l3_ttl=7200,
        max_cacheable_temperature=0.2,
    ),
}


class LLMCache:
    """
    Intelligent cache for LLM responses.

    Features:
    - Semantic caching based on prompt + model + parameters
    - Multi-level cache (L1 LRU → L2 LFU → L3 Redis)
    - Per-model-type cache strategies
    - Temperature-aware caching
    - Conversation context hashing
    - Cache metrics and monitoring

    Examples:
        >>> cache = LLMCache(enable_redis=True)
        >>> await cache.connect()
        >>>
        >>> # Single prompt caching
        >>> key = cache.make_key("What is Python?", "qwen3.5:27b", 0.1)
        >>> cached = await cache.get(key)
        >>> if not cached:
        ...     response = await llm.generate(prompt)
        ...     await cache.set(key, response)
        >>>
        >>> # Chat history caching
        >>> messages = [{"role": "user", "content": "Hello"}]
        >>> key = cache.make_chat_key(messages, "qwen3.5:27b", 0.1)
    """

    def __init__(
        self,
        l1_capacity: int = 200,
        l2_capacity: int = 1000,
        enable_redis: bool = False,
        redis_url: str = "redis://localhost:6379/0",
        configs: dict[str, CacheConfig] | None = None,
    ):
        """
        Initialize LLM cache.

        Args:
            l1_capacity: L1 cache capacity (hot responses)
            l2_capacity: L2 cache capacity (warm responses)
            enable_redis: Enable Redis L3 cache
            redis_url: Redis connection URL
            configs: Custom cache configs per model type
        """
        self.configs = configs or DEFAULT_CACHE_CONFIGS

        # Initialize multi-level cache with short default TTLs
        # (actual TTLs are applied per-request based on model type)
        self._cache = MultiLevelCache(
            l1_capacity=l1_capacity,
            l2_capacity=l2_capacity,
            l1_ttl=300,  # 5 min default
            l2_ttl=1800,  # 30 min default
            l3_ttl=7200,  # 2 hours default
            write_through=True,
            enable_l3=enable_redis,
            redis_url=redis_url,
            redis_key_prefix="tawiza:llm_cache:",
        )

        # Statistics
        self._stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "cache_skipped": 0,  # Skipped due to high temperature
            "tokens_saved": 0,  # Estimated tokens saved by caching
        }

        logger.info(
            f"LLMCache initialized: L1={l1_capacity}, L2={l2_capacity}, "
            f"Redis={'enabled' if enable_redis else 'disabled'}"
        )

    async def connect(self) -> bool:
        """
        Connect to Redis L3 cache if enabled.

        Returns:
            True if connected (or Redis not enabled)
        """
        return await self._cache.connect_l3()

    async def close(self) -> None:
        """Close Redis connection."""
        await self._cache.close_l3()

    def _get_model_type(self, model_name: str) -> str:
        """
        Determine model type from model name.

        Args:
            model_name: Model name (e.g., "qwen3-coder:14b")

        Returns:
            Model type for cache config lookup
        """
        model_lower = model_name.lower()

        if "embed" in model_lower or "bge" in model_lower or "e5" in model_lower:
            return "embedding"
        elif "code" in model_lower or "coder" in model_lower or "codellama" in model_lower:
            return "code"
        elif "llava" in model_lower or "vision" in model_lower or "bakllava" in model_lower:
            return "vision"
        elif "chat" in model_lower or "instruct" in model_lower:
            return "chat"
        else:
            return "default"

    def _get_config(self, model_name: str) -> CacheConfig:
        """Get cache config for model."""
        model_type = self._get_model_type(model_name)
        return self.configs.get(model_type, self.configs["default"])

    def _should_cache(
        self,
        model_name: str,
        temperature: float,
    ) -> bool:
        """
        Determine if response should be cached.

        High-temperature responses are non-deterministic and shouldn't be cached.

        Args:
            model_name: Model name
            temperature: Sampling temperature

        Returns:
            True if response should be cached
        """
        config = self._get_config(model_name)

        if config.strategy == CacheStrategy.NONE:
            return False

        return not temperature > config.max_cacheable_temperature

    def make_key(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.0,
        system: str | None = None,
        max_tokens: int | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> str:
        """
        Generate cache key for a prompt.

        The key is a hash of all parameters that affect the response.

        Args:
            prompt: User prompt
            model: Model name
            temperature: Sampling temperature
            system: System prompt
            max_tokens: Max tokens to generate
            extra_params: Additional parameters

        Returns:
            Cache key (SHA256 hash)
        """
        key_data = {
            "prompt": prompt,
            "model": model,
            "temperature": round(temperature, 2),
        }

        if system:
            key_data["system"] = system
        if max_tokens:
            key_data["max_tokens"] = max_tokens
        if extra_params:
            key_data["extra"] = extra_params

        key_json = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_json.encode()).hexdigest()[:32]

    def make_chat_key(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.0,
        extra_params: dict[str, Any] | None = None,
    ) -> str:
        """
        Generate cache key for a chat conversation.

        Args:
            messages: Chat messages [{"role": "user", "content": "..."}]
            model: Model name
            temperature: Sampling temperature
            extra_params: Additional parameters

        Returns:
            Cache key (SHA256 hash)
        """
        key_data = {
            "messages": messages,
            "model": model,
            "temperature": round(temperature, 2),
        }

        if extra_params:
            key_data["extra"] = extra_params

        key_json = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_json.encode()).hexdigest()[:32]

    def make_embedding_key(
        self,
        text: str,
        model: str,
    ) -> str:
        """
        Generate cache key for embeddings.

        Embeddings are deterministic so only text + model matter.

        Args:
            text: Input text
            model: Embedding model name

        Returns:
            Cache key (SHA256 hash)
        """
        key_data = {
            "text": text,
            "model": model,
            "type": "embedding",
        }

        key_json = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_json.encode()).hexdigest()[:32]

    async def get(
        self,
        key: str,
        model: str = "",
        temperature: float = 0.0,
    ) -> dict[str, Any] | None:
        """
        Get cached response.

        Args:
            key: Cache key from make_key()
            model: Model name (for checking if caching is allowed)
            temperature: Temperature (for checking if caching is allowed)

        Returns:
            Cached response or None
        """
        # Check if this request type should use cache
        if model and not self._should_cache(model, temperature):
            self._stats["cache_skipped"] += 1
            return None

        # Try to get from cache
        value = await self._cache.get_async(key)

        if value is not None:
            self._stats["cache_hits"] += 1

            # Estimate tokens saved (rough: 4 chars per token)
            if isinstance(value, dict) and "response" in value:
                self._stats["tokens_saved"] += len(value["response"]) // 4
            elif isinstance(value, str):
                self._stats["tokens_saved"] += len(value) // 4

            logger.debug(f"LLM cache hit for key {key[:8]}...")
            return value

        self._stats["cache_misses"] += 1
        return None

    async def set(
        self,
        key: str,
        value: str | dict[str, Any] | list[float],
        model: str = "",
        temperature: float = 0.0,
    ) -> bool:
        """
        Cache a response.

        Args:
            key: Cache key from make_key()
            value: Response to cache
            model: Model name (for determining TTL)
            temperature: Temperature (for checking if caching is allowed)

        Returns:
            True if cached successfully
        """
        # Check if this request type should use cache
        if model and not self._should_cache(model, temperature):
            return False

        # Get TTL based on model type
        config = self._get_config(model) if model else self.configs["default"]

        await self._cache.put_async(key, value, l3_ttl=config.l3_ttl)
        logger.debug(f"LLM response cached for key {key[:8]}... (TTL: {config.l3_ttl}s)")
        return True

    async def invalidate(self, key: str) -> bool:
        """
        Invalidate a cached response.

        Args:
            key: Cache key to invalidate

        Returns:
            True if key was found and deleted
        """
        return await self._cache.delete_async(key)

    async def clear(self) -> None:
        """Clear all cached responses."""
        await self._cache.clear_async()
        logger.info("LLM cache cleared")

    def get_stats(self) -> dict[str, Any]:
        """
        Get comprehensive cache statistics.

        Returns:
            Dictionary with cache metrics
        """
        total = self._stats["cache_hits"] + self._stats["cache_misses"]
        hit_rate = (self._stats["cache_hits"] / total * 100) if total > 0 else 0.0

        return {
            **self._stats,
            "hit_rate": f"{hit_rate:.1f}%",
            "total_requests": total,
            "multi_level_stats": self._cache.get_stats(),
        }

    async def health_check(self) -> dict[str, Any]:
        """
        Perform health check on cache.

        Returns:
            Health status for all cache levels
        """
        return await self._cache.health_check()

    async def __aenter__(self) -> "LLMCache":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    def __repr__(self) -> str:
        """String representation."""
        stats = self.get_stats()
        return (
            f"LLMCache("
            f"hits={stats['cache_hits']}, "
            f"misses={stats['cache_misses']}, "
            f"hit_rate={stats['hit_rate']}, "
            f"tokens_saved={stats['tokens_saved']})"
        )


# Global LLM cache instance
_llm_cache: LLMCache | None = None


async def get_llm_cache(
    enable_redis: bool = False,
    redis_url: str = "redis://localhost:6379/0",
    **kwargs,
) -> LLMCache:
    """
    Get or create global LLM cache instance.

    Args:
        enable_redis: Enable Redis L3 cache
        redis_url: Redis connection URL
        **kwargs: Additional LLMCache arguments

    Returns:
        LLMCache instance
    """
    global _llm_cache

    if _llm_cache is None:
        _llm_cache = LLMCache(
            enable_redis=enable_redis,
            redis_url=redis_url,
            **kwargs,
        )
        await _llm_cache.connect()

    return _llm_cache


async def close_llm_cache() -> None:
    """Close global LLM cache instance."""
    global _llm_cache

    if _llm_cache is not None:
        await _llm_cache.close()
        _llm_cache = None
