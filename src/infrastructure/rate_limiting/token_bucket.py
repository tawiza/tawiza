"""
Token Bucket Algorithm - Smooth rate limiting with burst support

Algorithm:
    Bucket has capacity C and refills at rate R tokens/second.

    Operations:
    1. Refill: tokens = min(C, current_tokens + (elapsed_time * R))
    2. Consume: if tokens >= requested: consume and allow; else: reject

    Properties:
    - Allows controlled bursts (up to capacity)
    - Smooth rate limiting (refill is continuous)
    - O(1) time complexity
    - Simple and efficient

    Example:
        Capacity: 100 tokens
        Refill rate: 10 tokens/second

        - Can burst up to 100 requests immediately
        - Sustains 10 requests/second indefinitely
        - After burst, refills at 10/sec back to 100

Time complexity: O(1) for consume operation
Space complexity: O(1) per bucket
"""

import time
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TokenBucket:
    """
    Token Bucket for rate limiting

    Examples:
        >>> bucket = TokenBucket(capacity=100, refill_rate=10)
        >>> bucket.consume(1)  # True (allowed)
        >>> bucket.consume(200)  # False (not enough tokens)
        >>> time.sleep(10)  # Wait for refill
        >>> bucket.consume(100)  # True (refilled)
    """

    capacity: float  # Maximum tokens
    refill_rate: float  # Tokens per second
    tokens: float = None  # Current tokens
    last_refill: float = None  # Last refill timestamp

    def __post_init__(self):
        """Initialize bucket with full capacity"""
        if self.tokens is None:
            self.tokens = self.capacity
        if self.last_refill is None:
            self.last_refill = time.time()

    def _refill(self) -> None:
        """
        Refill tokens based on elapsed time

        Time complexity: O(1)

        Algorithm:
        1. Calculate elapsed time since last refill
        2. Calculate new tokens: elapsed_time * refill_rate
        3. Add to current tokens (max = capacity)
        4. Update last_refill timestamp
        """
        now = time.time()
        elapsed = now - self.last_refill

        # Calculate tokens to add
        new_tokens = elapsed * self.refill_rate

        # Add tokens (capped at capacity)
        self.tokens = min(self.capacity, self.tokens + new_tokens)

        # Update refill timestamp
        self.last_refill = now

    def consume(self, tokens: float = 1) -> bool:
        """
        Attempt to consume tokens

        Time complexity: O(1)

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens consumed (request allowed)
            False if not enough tokens (request rejected)
        """
        # Refill first
        self._refill()

        # Check if enough tokens available
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True

        return False

    def peek(self) -> float:
        """
        Get current token count without consuming

        Returns:
            Current number of tokens available
        """
        self._refill()
        return self.tokens

    def wait_time(self, tokens: float = 1) -> float:
        """
        Calculate time to wait until tokens available

        Args:
            tokens: Number of tokens needed

        Returns:
            Time to wait in seconds (0 if tokens already available)
        """
        self._refill()

        if self.tokens >= tokens:
            return 0.0

        # Calculate tokens needed
        needed = tokens - self.tokens

        # Calculate time to accumulate needed tokens
        return needed / self.refill_rate

    def get_stats(self) -> dict:
        """Get bucket statistics"""
        self._refill()
        return {
            "capacity": self.capacity,
            "refill_rate": self.refill_rate,
            "current_tokens": self.tokens,
            "fill_percentage": (self.tokens / self.capacity) * 100,
            "last_refill": datetime.fromtimestamp(self.last_refill).isoformat(),
        }

    def __repr__(self) -> str:
        """String representation"""
        self._refill()
        return (
            f"TokenBucket(capacity={self.capacity}, "
            f"rate={self.refill_rate}/s, "
            f"tokens={self.tokens:.1f})"
        )


class RateLimiter:
    """
    Multi-bucket rate limiter

    Manages multiple token buckets for different keys (users, endpoints, etc.)

    Examples:
        >>> limiter = RateLimiter(capacity=100, refill_rate=10)
        >>> limiter.allow("user123")  # True
        >>> limiter.allow("user456")  # True (separate bucket)
    """

    def __init__(
        self,
        capacity: float = 100,
        refill_rate: float = 10,
        auto_cleanup: bool = True,
        cleanup_threshold: int = 1000,
    ):
        """
        Initialize rate limiter

        Args:
            capacity: Token bucket capacity per key
            refill_rate: Refill rate (tokens/second) per key
            auto_cleanup: Automatically clean up full buckets
            cleanup_threshold: Trigger cleanup after N buckets
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.auto_cleanup = auto_cleanup
        self.cleanup_threshold = cleanup_threshold

        # Buckets per key
        self.buckets: dict[str, TokenBucket] = {}

        # Statistics
        self.allowed_requests = 0
        self.rejected_requests = 0

    def _get_bucket(self, key: str) -> TokenBucket:
        """
        Get or create bucket for key

        Args:
            key: Rate limit key (user ID, IP, etc.)

        Returns:
            Token bucket for the key
        """
        if key not in self.buckets:
            self.buckets[key] = TokenBucket(
                capacity=self.capacity,
                refill_rate=self.refill_rate,
            )

            # Auto-cleanup if too many buckets
            if self.auto_cleanup and len(self.buckets) > self.cleanup_threshold:
                self._cleanup()

        return self.buckets[key]

    def allow(self, key: str, tokens: float = 1) -> bool:
        """
        Check if request is allowed

        Args:
            key: Rate limit key
            tokens: Tokens to consume

        Returns:
            True if allowed, False if rate limited
        """
        bucket = self._get_bucket(key)
        allowed = bucket.consume(tokens)

        if allowed:
            self.allowed_requests += 1
        else:
            self.rejected_requests += 1

        return allowed

    def wait_time(self, key: str, tokens: float = 1) -> float:
        """
        Get wait time until request allowed

        Args:
            key: Rate limit key
            tokens: Tokens needed

        Returns:
            Seconds to wait
        """
        bucket = self._get_bucket(key)
        return bucket.wait_time(tokens)

    def reset(self, key: str) -> None:
        """Reset bucket for key"""
        if key in self.buckets:
            del self.buckets[key]

    def _cleanup(self) -> None:
        """Remove buckets that are full (inactive)"""
        to_remove = []

        for key, bucket in self.buckets.items():
            bucket._refill()
            # Remove if bucket is at or near full capacity (inactive)
            if bucket.tokens >= bucket.capacity * 0.95:
                to_remove.append(key)

        for key in to_remove:
            del self.buckets[key]

    def get_stats(self) -> dict:
        """Get rate limiter statistics"""
        total_requests = self.allowed_requests + self.rejected_requests

        return {
            "capacity": self.capacity,
            "refill_rate": self.refill_rate,
            "active_buckets": len(self.buckets),
            "allowed_requests": self.allowed_requests,
            "rejected_requests": self.rejected_requests,
            "rejection_rate": (
                (self.rejected_requests / total_requests * 100) if total_requests > 0 else 0.0
            ),
        }

    def __repr__(self) -> str:
        """String representation"""
        return (
            f"RateLimiter(buckets={len(self.buckets)}, "
            f"capacity={self.capacity}, "
            f"rate={self.refill_rate}/s)"
        )
