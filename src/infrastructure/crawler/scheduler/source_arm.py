"""SourceArm model for Multi-Armed Bandit source selection."""

from dataclasses import dataclass
from enum import Enum, StrEnum


class SourceType(StrEnum):
    """Type of data source."""

    API = "api"
    WEB = "web"
    RSS = "rss"
    JS_HEAVY = "js_heavy"  # Sites requiring JavaScript rendering (SPAs, dynamic content)


@dataclass
class SourceArm:
    """
    A source 'arm' in the Multi-Armed Bandit algorithm.

    Each source has metrics for:
    - Freshness: How often content changes
    - Quality: Data extraction success rate
    - Relevance: Usefulness to TAJINE queries
    """

    source_id: str
    url: str
    source_type: SourceType
    requires_js: bool = False  # If True, use PlaywrightWorker instead of HTTPXWorker

    # MAB counters
    pulls: int = 0
    successes: int = 0
    total_reward: float = 0.0

    # Adaptation axes (0.0 - 1.0)
    freshness_score: float = 0.5
    quality_score: float = 0.5
    relevance_score: float = 0.5

    # Metadata
    last_crawl: str | None = None
    content_hash: str | None = None

    @property
    def average_reward(self) -> float:
        """Weighted average of the three scores."""
        # Weights: freshness=1, quality=2, relevance=3
        weights = [1, 2, 3]
        scores = [self.freshness_score, self.quality_score, self.relevance_score]
        return sum(s * w for s, w in zip(scores, weights, strict=False)) / sum(weights)

    def record_pull(
        self, success: bool, freshness: float | None = None, quality: float | None = None
    ) -> None:
        """
        Record a crawl attempt.

        Args:
            success: Whether crawl succeeded
            freshness: New freshness score (if content changed)
            quality: New quality score (based on extraction)
        """
        self.pulls += 1
        if success:
            self.successes += 1
        if freshness is not None:
            self.freshness_score = freshness
        if quality is not None:
            self.quality_score = quality

    def update_relevance(self, was_useful: bool) -> None:
        """
        Update relevance based on TAJINE feedback.

        Uses exponential moving average with alpha=0.1
        """
        alpha = 0.1
        reward = 1.0 if was_useful else 0.0
        self.relevance_score = (1 - alpha) * self.relevance_score + alpha * reward

    def to_dict(self) -> dict:
        """Convert to dictionary for Redis storage."""
        return {
            "source_id": self.source_id,
            "url": self.url,
            "source_type": self.source_type.value,
            "requires_js": self.requires_js,
            "pulls": self.pulls,
            "successes": self.successes,
            "total_reward": self.total_reward,
            "freshness_score": self.freshness_score,
            "quality_score": self.quality_score,
            "relevance_score": self.relevance_score,
            "last_crawl": self.last_crawl,
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SourceArm":
        """Create from dictionary."""
        return cls(
            source_id=data["source_id"],
            url=data["url"],
            source_type=SourceType(data["source_type"]),
            requires_js=data.get("requires_js", False),
            pulls=data.get("pulls", 0),
            successes=data.get("successes", 0),
            total_reward=data.get("total_reward", 0.0),
            freshness_score=data.get("freshness_score", 0.5),
            quality_score=data.get("quality_score", 0.5),
            relevance_score=data.get("relevance_score", 0.5),
            last_crawl=data.get("last_crawl"),
            content_hash=data.get("content_hash"),
        )
