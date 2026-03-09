"""Rate limiter for respectful crawling."""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from loguru import logger


@dataclass
class RateLimit:
    """Rate limit configuration for a domain."""
    requests: int = 10
    period: int = 60


@dataclass
class DomainState:
    """Track state for a specific domain."""
    tokens: float = 10.0
    last_update: datetime = field(default_factory=datetime.now)
    blocked_until: datetime | None = None


class RateLimiter:
    """
    Token bucket rate limiter with domain-specific limits.

    Features:
    - Per-domain rate limits
    - Temporary blocking for 429/503 responses
    - Exponential backoff support
    """

    def __init__(self, default_limit: RateLimit | None = None):
        """Initialize rate limiter."""
        self.default_limit = default_limit or RateLimit()
        self.limits: dict[str, RateLimit] = {}
        self.states: dict[str, DomainState] = {}
        self._lock = asyncio.Lock()

    def set_limit(self, domain: str, limit: RateLimit) -> None:
        """Set rate limit for a specific domain."""
        self.limits[domain] = limit
        logger.debug(f"Set limit for {domain}: {limit.requests}/{limit.period}s")

    def get_limit(self, domain: str) -> RateLimit:
        """Get rate limit for domain (or default)."""
        return self.limits.get(domain, self.default_limit)

    def _get_state(self, domain: str) -> DomainState:
        """Get or create state for domain."""
        if domain not in self.states:
            limit = self.get_limit(domain)
            self.states[domain] = DomainState(tokens=float(limit.requests))
        return self.states[domain]

    def _refill_tokens(self, domain: str) -> None:
        """Refill tokens based on elapsed time."""
        state = self._get_state(domain)
        limit = self.get_limit(domain)

        now = datetime.now()
        elapsed = (now - state.last_update).total_seconds()

        tokens_to_add = elapsed * (limit.requests / limit.period)
        state.tokens = min(limit.requests, state.tokens + tokens_to_add)
        state.last_update = now

    async def acquire(self, domain: str) -> None:
        """
        Acquire permission to make a request.

        Blocks until rate limit allows the request.
        """
        async with self._lock:
            state = self._get_state(domain)
            if state.blocked_until and datetime.now() < state.blocked_until:
                wait_time = (state.blocked_until - datetime.now()).total_seconds()
                logger.warning(f"Domain {domain} blocked for {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                state.blocked_until = None

            self._refill_tokens(domain)

            if state.tokens < 1:
                limit = self.get_limit(domain)
                wait_time = (1 - state.tokens) * (limit.period / limit.requests)
                logger.debug(f"Rate limited {domain}, waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
                self._refill_tokens(domain)

            state.tokens -= 1

    def block_domain(self, domain: str, duration: int = 300) -> None:
        """
        Temporarily block a domain.

        Args:
            domain: Domain to block
            duration: Block duration in seconds (default 5 min)
        """
        state = self._get_state(domain)
        state.blocked_until = datetime.now() + timedelta(seconds=duration)
        logger.warning(f"Blocked {domain} for {duration}s")

    def is_blocked(self, domain: str) -> bool:
        """Check if domain is currently blocked."""
        state = self._get_state(domain)
        if state.blocked_until:
            return datetime.now() < state.blocked_until
        return False
