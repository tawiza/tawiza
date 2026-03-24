"""Tests for token bucket rate limiting.

This module tests:
- TokenBucket
- RateLimiter
"""

import time

import pytest

from src.infrastructure.rate_limiting.token_bucket import RateLimiter, TokenBucket


class TestTokenBucket:
    """Test suite for TokenBucket."""

    def test_initial_capacity(self):
        """Bucket should start with full capacity."""
        bucket = TokenBucket(capacity=100, refill_rate=10)
        assert bucket.tokens == 100

    def test_consume_reduces_tokens(self):
        """Consuming should reduce token count."""
        bucket = TokenBucket(capacity=100, refill_rate=10)
        bucket.consume(10)
        assert bucket.tokens == 90

    def test_consume_returns_true_when_enough_tokens(self):
        """Consume should return True when enough tokens available."""
        bucket = TokenBucket(capacity=100, refill_rate=10)
        assert bucket.consume(50) is True

    def test_consume_returns_false_when_not_enough_tokens(self):
        """Consume should return False when not enough tokens."""
        bucket = TokenBucket(capacity=100, refill_rate=10)
        bucket.tokens = 10
        assert bucket.consume(50) is False

    def test_consume_default_is_one_token(self):
        """Consume should default to 1 token."""
        bucket = TokenBucket(capacity=100, refill_rate=10)
        bucket.consume()
        assert bucket.tokens == 99

    def test_peek_shows_current_tokens(self):
        """Peek should show current token count."""
        bucket = TokenBucket(capacity=100, refill_rate=10)
        bucket.tokens = 50
        bucket.last_refill = time.time()  # Reset refill time
        assert bucket.peek() == pytest.approx(50, rel=0.01)

    def test_peek_does_not_consume(self):
        """Peek should not consume tokens."""
        bucket = TokenBucket(capacity=100, refill_rate=10)
        bucket.peek()
        bucket.peek()
        assert bucket.tokens == 100

    def test_wait_time_zero_when_enough_tokens(self):
        """Wait time should be 0 when enough tokens available."""
        bucket = TokenBucket(capacity=100, refill_rate=10)
        assert bucket.wait_time(50) == 0.0

    def test_wait_time_calculated_correctly(self):
        """Wait time should calculate time to refill needed tokens."""
        bucket = TokenBucket(capacity=100, refill_rate=10)
        bucket.tokens = 0
        # Need 10 tokens at 10 tokens/sec = 1 second
        assert bucket.wait_time(10) == pytest.approx(1.0, rel=0.1)

    def test_refill_adds_tokens(self):
        """Refill should add tokens based on elapsed time."""
        bucket = TokenBucket(capacity=100, refill_rate=1000)
        bucket.tokens = 0
        bucket.last_refill = time.time() - 0.01  # 10ms ago

        # Should refill some tokens
        bucket._refill()
        assert bucket.tokens > 0

    def test_refill_does_not_exceed_capacity(self):
        """Refill should not exceed capacity."""
        bucket = TokenBucket(capacity=100, refill_rate=1000)
        bucket.tokens = 99
        bucket.last_refill = time.time() - 1  # 1 second ago

        bucket._refill()
        assert bucket.tokens == 100

    def test_get_stats_returns_bucket_info(self):
        """Get stats should return bucket information."""
        bucket = TokenBucket(capacity=100, refill_rate=10)
        bucket.tokens = 50
        bucket.last_refill = time.time()  # Reset refill time

        stats = bucket.get_stats()

        assert stats["capacity"] == 100
        assert stats["refill_rate"] == 10
        assert stats["current_tokens"] == pytest.approx(50, rel=0.01)
        assert stats["fill_percentage"] == pytest.approx(50.0, rel=0.01)
        assert "last_refill" in stats

    def test_repr_format(self):
        """Repr should show bucket state."""
        bucket = TokenBucket(capacity=100, refill_rate=10)
        repr_str = repr(bucket)

        assert "TokenBucket" in repr_str
        assert "capacity=100" in repr_str
        assert "rate=10/s" in repr_str

    def test_burst_consumption(self):
        """Should allow burst consumption up to capacity."""
        bucket = TokenBucket(capacity=100, refill_rate=10)

        # Burst consume all tokens
        assert bucket.consume(100) is True
        assert bucket.tokens == 0

        # Can't consume more
        assert bucket.consume(1) is False


class TestRateLimiter:
    """Test suite for RateLimiter."""

    def test_allow_creates_bucket_for_new_key(self):
        """Allow should create bucket for new key."""
        limiter = RateLimiter(capacity=100, refill_rate=10)
        limiter.allow("user123")

        assert "user123" in limiter.buckets

    def test_allow_returns_true_for_allowed_request(self):
        """Allow should return True for allowed request."""
        limiter = RateLimiter(capacity=100, refill_rate=10)
        assert limiter.allow("user123") is True

    def test_allow_returns_false_for_rate_limited(self):
        """Allow should return False when rate limited."""
        limiter = RateLimiter(capacity=10, refill_rate=1)

        # Exhaust tokens
        for _ in range(10):
            limiter.allow("user123")

        # Should be rate limited
        assert limiter.allow("user123") is False

    def test_separate_buckets_per_key(self):
        """Each key should have separate bucket."""
        limiter = RateLimiter(capacity=10, refill_rate=1)

        # Exhaust user1's tokens
        for _ in range(10):
            limiter.allow("user1")

        # user2 should still have tokens
        assert limiter.allow("user2") is True

    def test_tracks_allowed_requests(self):
        """Should track allowed requests count."""
        limiter = RateLimiter(capacity=100, refill_rate=10)
        limiter.allow("user1")
        limiter.allow("user1")
        limiter.allow("user2")

        assert limiter.allowed_requests == 3

    def test_tracks_rejected_requests(self):
        """Should track rejected requests count."""
        limiter = RateLimiter(capacity=1, refill_rate=0.01)

        limiter.allow("user1")  # Allowed
        limiter.allow("user1")  # Rejected (out of tokens)

        assert limiter.allowed_requests == 1
        assert limiter.rejected_requests == 1

    def test_wait_time_for_key(self):
        """Should return wait time for specific key."""
        limiter = RateLimiter(capacity=100, refill_rate=10)

        # Exhaust some tokens
        limiter.buckets["user1"] = TokenBucket(capacity=100, refill_rate=10)
        limiter.buckets["user1"].tokens = 0

        wait = limiter.wait_time("user1", 10)
        assert wait == pytest.approx(1.0, rel=0.1)

    def test_reset_removes_bucket(self):
        """Reset should remove bucket for key."""
        limiter = RateLimiter(capacity=100, refill_rate=10)
        limiter.allow("user1")
        assert "user1" in limiter.buckets

        limiter.reset("user1")
        assert "user1" not in limiter.buckets

    def test_reset_nonexistent_key_does_not_error(self):
        """Reset on nonexistent key should not error."""
        limiter = RateLimiter(capacity=100, refill_rate=10)
        limiter.reset("nonexistent")  # Should not raise

    def test_cleanup_removes_inactive_buckets(self):
        """Cleanup should remove buckets at full capacity."""
        limiter = RateLimiter(
            capacity=100,
            refill_rate=10,
            auto_cleanup=False,  # Disable auto-cleanup to control it manually
        )

        # Create active bucket (partially consumed)
        limiter.buckets["active"] = TokenBucket(capacity=100, refill_rate=10)
        limiter.buckets["active"].tokens = 50  # 50% consumed

        # Create inactive bucket (at full capacity)
        limiter.buckets["inactive"] = TokenBucket(capacity=100, refill_rate=10)
        # tokens = 100 (full capacity by default)

        # Trigger cleanup
        limiter._cleanup()

        # Active bucket should remain
        assert "active" in limiter.buckets

        # Inactive bucket (at full capacity) should be removed
        assert "inactive" not in limiter.buckets

    def test_get_stats_returns_limiter_info(self):
        """Get stats should return limiter information."""
        limiter = RateLimiter(capacity=100, refill_rate=10)
        limiter.allow("user1")
        limiter.allow("user2")

        stats = limiter.get_stats()

        assert stats["capacity"] == 100
        assert stats["refill_rate"] == 10
        assert stats["active_buckets"] == 2
        assert stats["allowed_requests"] == 2
        assert stats["rejected_requests"] == 0
        assert stats["rejection_rate"] == 0.0

    def test_get_stats_rejection_rate(self):
        """Get stats should calculate rejection rate."""
        limiter = RateLimiter(capacity=2, refill_rate=0.01)

        limiter.allow("user1")  # Allowed
        limiter.allow("user1")  # Allowed
        limiter.allow("user1")  # Rejected

        stats = limiter.get_stats()
        # 1 out of 3 rejected = 33.33%
        assert stats["rejection_rate"] == pytest.approx(33.33, rel=0.1)

    def test_repr_format(self):
        """Repr should show limiter state."""
        limiter = RateLimiter(capacity=100, refill_rate=10)
        limiter.allow("user1")

        repr_str = repr(limiter)

        assert "RateLimiter" in repr_str
        assert "buckets=1" in repr_str
        assert "capacity=100" in repr_str

    def test_custom_token_consumption(self):
        """Should allow custom token consumption per request."""
        limiter = RateLimiter(capacity=100, refill_rate=10)

        # Heavy request consuming 50 tokens
        assert limiter.allow("user1", tokens=50) is True

        # Light request consuming 1 token
        assert limiter.allow("user1", tokens=1) is True

        # Another heavy request should fail
        assert limiter.allow("user1", tokens=50) is False
