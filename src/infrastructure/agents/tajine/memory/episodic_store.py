"""Episodic memory store for TAJINE agent.

Stores episodes (past analyses) with their:
- Query and context
- Analysis results
- User feedback
- Embeddings for semantic retrieval
"""

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class Episode:
    """A single episode in TAJINE's memory.

    Represents one analysis interaction with all relevant context.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Query information
    query: str = ""
    query_type: str = ""  # 'territorial', 'sector', 'general'

    # Territorial context
    territory: str = ""  # Department code or region
    sector: str = ""  # NAF code or sector name
    keywords: list[str] = field(default_factory=list)

    # Analysis results
    analysis_result: dict[str, Any] = field(default_factory=dict)
    cognitive_levels: dict[str, float] = field(default_factory=dict)  # Scores per level
    confidence_score: float = 0.0
    mode: str = "fast"  # 'fast' or 'complete'

    # PPDSL cycle data
    ppdsl_phases: dict[str, Any] = field(default_factory=dict)

    # User interaction
    user_feedback: str | None = None
    feedback_score: float | None = None  # -1 to 1
    corrections: list[str] = field(default_factory=list)

    # For RAG retrieval
    embedding: list[float] = field(default_factory=list)

    # Metadata
    duration_ms: float = 0.0
    sources_used: list[str] = field(default_factory=list)
    tools_called: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Episode":
        """Create from dictionary."""
        if isinstance(data.get("timestamp"), str):
            ts = datetime.fromisoformat(data["timestamp"])
            # Ensure timezone-aware (assume UTC for naive timestamps)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            data["timestamp"] = ts
        return cls(**data)

    def get_search_text(self) -> str:
        """Get text representation for search/embedding."""
        parts = [
            self.query,
            f"territoire: {self.territory}" if self.territory else "",
            f"secteur: {self.sector}" if self.sector else "",
            " ".join(self.keywords),
        ]
        return " ".join(p for p in parts if p)

    def matches_context(
        self,
        territory: str | None = None,
        sector: str | None = None,
    ) -> bool:
        """Check if episode matches given context."""
        if territory and self.territory != territory:
            return False
        return not (sector and self.sector != sector)


class EpisodicStore:
    """Persistent store for TAJINE episodes.

    Stores episodes in JSON files with optional vector embeddings.
    Supports multiple storage backends.
    """

    def __init__(
        self,
        storage_path: str | Path = ".tajine_memory",
        max_episodes: int = 10000,
    ) -> None:
        """Initialize the episodic store.

        Args:
            storage_path: Directory for storing episodes
            max_episodes: Maximum episodes to keep (oldest pruned)
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.max_episodes = max_episodes

        self._episodes: dict[str, Episode] = {}
        self._index_file = self.storage_path / "index.json"
        self._load_index()

    def _load_index(self) -> None:
        """Load episode index from disk."""
        if self._index_file.exists():
            try:
                with open(self._index_file) as f:
                    index = json.load(f)
                    for ep_id in index.get("episodes", []):
                        self._load_episode(ep_id)
                logger.info(f"Loaded {len(self._episodes)} episodes from memory")
            except Exception as e:
                logger.error(f"Failed to load episode index: {e}")

    def _load_episode(self, episode_id: str) -> Episode | None:
        """Load a single episode from disk."""
        ep_file = self.storage_path / f"{episode_id}.json"
        if ep_file.exists():
            try:
                with open(ep_file) as f:
                    data = json.load(f)
                    episode = Episode.from_dict(data)
                    self._episodes[episode_id] = episode
                    return episode
            except Exception as e:
                logger.warning(f"Failed to load episode {episode_id}: {e}")
        return None

    def _save_index(self) -> None:
        """Save episode index to disk."""
        index = {
            "episodes": list(self._episodes.keys()),
            "count": len(self._episodes),
            "last_updated": datetime.utcnow().isoformat(),
        }
        with open(self._index_file, "w") as f:
            json.dump(index, f)

    def _save_episode(self, episode: Episode) -> None:
        """Save a single episode to disk."""
        ep_file = self.storage_path / f"{episode.id}.json"
        with open(ep_file, "w") as f:
            json.dump(episode.to_dict(), f, indent=2, ensure_ascii=False)

    def add(self, episode: Episode) -> str:
        """Add a new episode to memory.

        Args:
            episode: Episode to add

        Returns:
            Episode ID
        """
        self._episodes[episode.id] = episode
        self._save_episode(episode)
        self._save_index()

        # Prune if over limit
        if len(self._episodes) > self.max_episodes:
            self._prune_oldest()

        logger.debug(f"Added episode {episode.id} to memory")
        return episode.id

    def get(self, episode_id: str) -> Episode | None:
        """Get episode by ID."""
        return self._episodes.get(episode_id)

    def update(self, episode_id: str, updates: dict[str, Any]) -> bool:
        """Update an existing episode.

        Args:
            episode_id: Episode to update
            updates: Fields to update

        Returns:
            True if updated, False if not found
        """
        episode = self._episodes.get(episode_id)
        if not episode:
            return False

        for key, value in updates.items():
            if hasattr(episode, key):
                setattr(episode, key, value)

        self._save_episode(episode)
        return True

    def add_feedback(
        self,
        episode_id: str,
        feedback: str,
        score: float | None = None,
    ) -> bool:
        """Add user feedback to an episode.

        Args:
            episode_id: Episode ID
            feedback: Feedback text
            score: Optional feedback score (-1 to 1)

        Returns:
            True if added, False if episode not found
        """
        return self.update(
            episode_id,
            {
                "user_feedback": feedback,
                "feedback_score": score,
            },
        )

    def add_correction(self, episode_id: str, correction: str) -> bool:
        """Add a user correction to an episode.

        Args:
            episode_id: Episode ID
            correction: Correction text

        Returns:
            True if added
        """
        episode = self._episodes.get(episode_id)
        if not episode:
            return False

        episode.corrections.append(correction)
        self._save_episode(episode)
        return True

    def get_by_territory(
        self,
        territory: str,
        limit: int = 10,
    ) -> list[Episode]:
        """Get episodes for a specific territory.

        Args:
            territory: Territory code
            limit: Maximum results

        Returns:
            List of matching episodes, newest first
        """
        matching = [ep for ep in self._episodes.values() if ep.territory == territory]
        matching.sort(key=lambda x: x.timestamp, reverse=True)
        return matching[:limit]

    def get_by_sector(
        self,
        sector: str,
        limit: int = 10,
    ) -> list[Episode]:
        """Get episodes for a specific sector.

        Args:
            sector: Sector code or name
            limit: Maximum results

        Returns:
            List of matching episodes
        """
        matching = [ep for ep in self._episodes.values() if sector.lower() in ep.sector.lower()]
        matching.sort(key=lambda x: x.timestamp, reverse=True)
        return matching[:limit]

    def get_recent(self, limit: int = 10) -> list[Episode]:
        """Get most recent episodes.

        Args:
            limit: Maximum results

        Returns:
            List of episodes, newest first
        """
        episodes = sorted(
            self._episodes.values(),
            key=lambda x: x.timestamp,
            reverse=True,
        )
        return episodes[:limit]

    def get_with_feedback(
        self,
        positive_only: bool = False,
        limit: int = 50,
    ) -> list[Episode]:
        """Get episodes that have user feedback.

        Args:
            positive_only: Only return episodes with positive feedback
            limit: Maximum results

        Returns:
            List of episodes with feedback
        """
        episodes = [
            ep
            for ep in self._episodes.values()
            if ep.user_feedback or ep.feedback_score is not None
        ]

        if positive_only:
            episodes = [ep for ep in episodes if ep.feedback_score and ep.feedback_score > 0]

        episodes.sort(key=lambda x: x.timestamp, reverse=True)
        return episodes[:limit]

    def search_text(
        self,
        query: str,
        limit: int = 10,
    ) -> list[Episode]:
        """Simple text search across episodes.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            Matching episodes
        """
        query_lower = query.lower()
        scored = []

        for episode in self._episodes.values():
            search_text = episode.get_search_text().lower()
            if query_lower in search_text:
                # Simple relevance score based on position and frequency
                score = search_text.count(query_lower)
                scored.append((score, episode))

        scored.sort(key=lambda x: (-x[0], -x[1].timestamp.timestamp()))
        return [ep for _, ep in scored[:limit]]

    def _prune_oldest(self, keep_count: int | None = None) -> int:
        """Remove oldest episodes to stay under limit.

        Args:
            keep_count: Number to keep (default: max_episodes)

        Returns:
            Number of episodes removed
        """
        keep_count = keep_count or self.max_episodes
        if len(self._episodes) <= keep_count:
            return 0

        # Sort by timestamp, remove oldest
        sorted_eps = sorted(
            self._episodes.items(),
            key=lambda x: x[1].timestamp,
        )

        to_remove = sorted_eps[: len(sorted_eps) - keep_count]
        removed = 0

        for ep_id, _ in to_remove:
            # Delete file
            ep_file = self.storage_path / f"{ep_id}.json"
            if ep_file.exists():
                ep_file.unlink()

            del self._episodes[ep_id]
            removed += 1

        self._save_index()
        logger.info(f"Pruned {removed} old episodes from memory")
        return removed

    def get_stats(self) -> dict[str, Any]:
        """Get memory statistics.

        Returns:
            Statistics about stored episodes
        """
        episodes = list(self._episodes.values())

        # Count by territory
        territories: dict[str, int] = {}
        for ep in episodes:
            if ep.territory:
                territories[ep.territory] = territories.get(ep.territory, 0) + 1

        # Count by sector
        sectors: dict[str, int] = {}
        for ep in episodes:
            if ep.sector:
                sectors[ep.sector] = sectors.get(ep.sector, 0) + 1

        # Feedback stats
        with_feedback = [ep for ep in episodes if ep.feedback_score is not None]
        avg_feedback = (
            sum(ep.feedback_score for ep in with_feedback) / len(with_feedback)
            if with_feedback
            else None
        )

        return {
            "total_episodes": len(episodes),
            "unique_territories": len(territories),
            "unique_sectors": len(sectors),
            "top_territories": sorted(territories.items(), key=lambda x: x[1], reverse=True)[:5],
            "top_sectors": sorted(sectors.items(), key=lambda x: x[1], reverse=True)[:5],
            "episodes_with_feedback": len(with_feedback),
            "avg_feedback_score": avg_feedback,
            "oldest_episode": (
                min(ep.timestamp for ep in episodes).isoformat() if episodes else None
            ),
            "newest_episode": (
                max(ep.timestamp for ep in episodes).isoformat() if episodes else None
            ),
        }

    def clear(self) -> int:
        """Clear all episodes from memory.

        Returns:
            Number of episodes removed
        """
        count = len(self._episodes)

        # Delete files
        for ep_id in list(self._episodes.keys()):
            ep_file = self.storage_path / f"{ep_id}.json"
            if ep_file.exists():
                ep_file.unlink()

        self._episodes.clear()
        self._save_index()

        logger.info(f"Cleared {count} episodes from memory")
        return count
