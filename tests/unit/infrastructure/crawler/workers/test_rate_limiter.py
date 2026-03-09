"""Tests for rate limiter."""

import asyncio

import pytest

from src.infrastructure.crawler.workers.rate_limiter import RateLimit, RateLimiter


class TestRateLimitConfig:
    """Test RateLimit configuration."""

    def test_create_rate_limit(self):
        """Create a rate limit config."""
        limit = RateLimit(requests=10, period=60)
        assert limit.requests == 10
        assert limit.period == 60

    def test_default_rate_limit(self):
        """Default rate limit values."""
        limit = RateLimit()
        assert limit.requests == 10
        assert limit.period == 60


class TestRateLimiter:
    """Test RateLimiter functionality."""

    def test_create_limiter(self):
        """Create rate limiter with domain limits."""
        limiter = RateLimiter()
        assert limiter is not None

    def test_add_domain_limit(self):
        """Add custom limit for domain."""
        limiter = RateLimiter()
        limiter.set_limit("api.insee.fr", RateLimit(requests=100, period=60))
        limit = limiter.get_limit("api.insee.fr")
        assert limit.requests == 100

    def test_get_default_limit(self):
        """Unknown domains get default limit."""
        limiter = RateLimiter()
        limit = limiter.get_limit("unknown.com")
        assert limit.requests == 10

    @pytest.mark.asyncio
    async def test_acquire_immediate(self):
        """First request is immediate."""
        limiter = RateLimiter()
        start = asyncio.get_event_loop().time()
        await limiter.acquire("example.com")
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_is_blocked(self):
        """Check if domain is blocked."""
        limiter = RateLimiter()
        assert not limiter.is_blocked("example.com")
        limiter.block_domain("example.com", duration=300)
        assert limiter.is_blocked("example.com")
