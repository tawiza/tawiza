"""
Cache Statistics - Monitoring and metrics

Provides cache metrics collection and reporting.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CacheStats:
    """Cache statistics collector"""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    sets: int = 0
    deletes: int = 0
    clears: int = 0
    start_time: datetime = field(default_factory=datetime.now)

    def record_hit(self) -> None:
        """Record a cache hit"""
        self.hits += 1

    def record_miss(self) -> None:
        """Record a cache miss"""
        self.misses += 1

    def record_eviction(self) -> None:
        """Record an eviction"""
        self.evictions += 1

    def record_set(self) -> None:
        """Record a set operation"""
        self.sets += 1

    def record_delete(self) -> None:
        """Record a delete operation"""
        self.deletes += 1

    def record_clear(self) -> None:
        """Record a clear operation"""
        self.clears += 1

    def get_hit_rate(self) -> float:
        """
        Calculate hit rate

        Returns:
            Hit rate as percentage (0-100)
        """
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return (self.hits / total) * 100

    def get_uptime_seconds(self) -> float:
        """Get cache uptime in seconds"""
        return (datetime.now() - self.start_time).total_seconds()

    def get_requests_per_second(self) -> float:
        """Calculate requests per second"""
        uptime = self.get_uptime_seconds()
        if uptime == 0:
            return 0.0
        total_requests = self.hits + self.misses
        return total_requests / uptime

    def to_dict(self) -> dict:
        """Convert stats to dictionary"""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "sets": self.sets,
            "deletes": self.deletes,
            "clears": self.clears,
            "hit_rate": self.get_hit_rate(),
            "uptime_seconds": self.get_uptime_seconds(),
            "requests_per_second": self.get_requests_per_second(),
            "start_time": self.start_time.isoformat(),
        }

    def reset(self) -> None:
        """Reset all counters"""
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.sets = 0
        self.deletes = 0
        self.clears = 0
        self.start_time = datetime.now()
