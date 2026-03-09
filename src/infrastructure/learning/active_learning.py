"""Active Learning Manager - Prioritizes examples for human annotation."""

import heapq
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, StrEnum
from typing import Any

from loguru import logger


def utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(UTC)


class SelectionStrategy(StrEnum):
    """Strategies for selecting candidates."""

    UNCERTAINTY = "uncertainty"  # Prioritize uncertain predictions
    DIVERSITY = "diversity"  # Prioritize diverse examples
    HYBRID = "hybrid"  # Combine uncertainty, diversity, impact


@dataclass
class AnnotationCandidate:
    """Candidate for human annotation.

    Scores are used to prioritize which examples
    are most valuable to annotate.
    """

    id: str
    instruction: str
    output: str
    uncertainty_score: float = 0.5
    diversity_score: float = 1.0
    impact_score: float = 0.5
    status: str = "pending"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)

    # Weights for priority calculation
    _uncertainty_weight: float = 0.5
    _diversity_weight: float = 0.3
    _impact_weight: float = 0.2

    @property
    def priority(self) -> float:
        """Calculate priority score (higher = more important to annotate)."""
        return (
            self.uncertainty_score * self._uncertainty_weight +
            self.diversity_score * self._diversity_weight +
            self.impact_score * self._impact_weight
        )

    def __lt__(self, other: "AnnotationCandidate") -> bool:
        """Compare by priority (for heapq, lower = better, so we negate)."""
        return self.priority > other.priority


class PriorityQueue:
    """Priority queue for annotation candidates.

    Uses a heap to efficiently get the highest-priority candidates.
    """

    def __init__(self):
        """Initialize empty queue."""
        self._heap: list[AnnotationCandidate] = []
        self._id_set: set[str] = set()

    def __len__(self) -> int:
        """Get number of candidates in queue."""
        return len(self._heap)

    def __iter__(self) -> Iterator[AnnotationCandidate]:
        """Iterate over candidates."""
        return iter(sorted(self._heap, reverse=True))

    @property
    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return len(self._heap) == 0

    def push(self, candidate: AnnotationCandidate) -> None:
        """Add candidate to queue.

        Args:
            candidate: Candidate to add
        """
        if candidate.id in self._id_set:
            logger.warning(f"Candidate {candidate.id} already in queue, skipping")
            return

        heapq.heappush(self._heap, candidate)
        self._id_set.add(candidate.id)

    def pop(self) -> AnnotationCandidate | None:
        """Remove and return highest priority candidate.

        Returns:
            Highest priority candidate, or None if empty
        """
        if self.is_empty:
            return None

        candidate = heapq.heappop(self._heap)
        self._id_set.discard(candidate.id)
        return candidate

    def peek(self) -> AnnotationCandidate | None:
        """Return highest priority candidate without removing.

        Returns:
            Highest priority candidate, or None if empty
        """
        if self.is_empty:
            return None
        return self._heap[0]

    def pop_batch(self, n: int) -> list[AnnotationCandidate]:
        """Remove and return n highest priority candidates.

        Args:
            n: Number of candidates to pop

        Returns:
            List of candidates
        """
        result = []
        for _ in range(min(n, len(self._heap))):
            candidate = self.pop()
            if candidate:
                result.append(candidate)
        return result

    def clear(self) -> None:
        """Clear all candidates."""
        self._heap.clear()
        self._id_set.clear()

    def remove_by_id(self, candidate_id: str) -> bool:
        """Remove candidate by ID.

        Args:
            candidate_id: ID to remove

        Returns:
            True if found and removed
        """
        if candidate_id not in self._id_set:
            return False

        self._heap = [c for c in self._heap if c.id != candidate_id]
        heapq.heapify(self._heap)
        self._id_set.discard(candidate_id)
        return True


class ActiveLearningManager:
    """Manages active learning for annotation prioritization.

    Tracks candidates, calculates priorities, and integrates
    with Label Studio for annotation.

    Example:
        manager = ActiveLearningManager()
        manager.add_candidate(
            id="ex_1",
            instruction="What is AI?",
            output="AI is...",
            uncertainty_score=0.8
        )
        next_to_annotate = manager.get_next()
    """

    def __init__(
        self,
        strategy: SelectionStrategy = SelectionStrategy.HYBRID,
        min_uncertainty: float = 0.3,
    ):
        """Initialize manager.

        Args:
            strategy: Selection strategy to use
            min_uncertainty: Minimum uncertainty to consider for queue
        """
        self.strategy = strategy
        self.min_uncertainty = min_uncertainty

        self.queue = PriorityQueue()
        self.annotated_ids: set[str] = set()
        self.skipped_ids: set[str] = set()

        # Track seen instructions for diversity calculation
        self._seen_instructions: list[str] = []

        logger.info(f"ActiveLearningManager initialized with strategy={strategy.value}")

    def _calculate_diversity(self, instruction: str) -> float:
        """Calculate diversity score based on seen instructions.

        Uses simple Jaccard similarity to measure how different
        this instruction is from what we've seen.

        Args:
            instruction: New instruction

        Returns:
            Diversity score (0.0 to 1.0, higher = more diverse)
        """
        if not self._seen_instructions:
            return 1.0  # First one is always diverse

        # Simple word overlap similarity
        new_words = set(instruction.lower().split())

        max_similarity = 0.0
        for seen in self._seen_instructions:
            seen_words = set(seen.lower().split())

            # Jaccard similarity
            if new_words or seen_words:
                intersection = len(new_words & seen_words)
                union = len(new_words | seen_words)
                similarity = intersection / union if union > 0 else 0.0
                max_similarity = max(max_similarity, similarity)

        # Diversity is inverse of max similarity
        return 1.0 - max_similarity

    def add_candidate(
        self,
        id: str,
        instruction: str,
        output: str,
        uncertainty_score: float = 0.5,
        impact_score: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> AnnotationCandidate | None:
        """Add a candidate for annotation.

        Args:
            id: Unique identifier
            instruction: The instruction text
            output: The generated output
            uncertainty_score: Model uncertainty (0-1)
            impact_score: Business impact (0-1)
            metadata: Additional metadata

        Returns:
            Created candidate, or None if filtered out
        """
        # Skip if already processed
        if id in self.annotated_ids or id in self.skipped_ids:
            return None

        # Skip low uncertainty if using uncertainty strategy
        if self.strategy != SelectionStrategy.DIVERSITY:
            if uncertainty_score < self.min_uncertainty:
                return None

        # Calculate diversity
        diversity_score = self._calculate_diversity(instruction)

        # Create candidate
        candidate = AnnotationCandidate(
            id=id,
            instruction=instruction,
            output=output,
            uncertainty_score=uncertainty_score,
            diversity_score=diversity_score,
            impact_score=impact_score,
            metadata=metadata or {},
        )

        # Add to queue and track instruction
        self.queue.push(candidate)
        self._seen_instructions.append(instruction)

        logger.debug(
            f"Added candidate {id}: uncertainty={uncertainty_score:.2f}, "
            f"diversity={diversity_score:.2f}, priority={candidate.priority:.2f}"
        )

        return candidate

    def get_next(self) -> AnnotationCandidate | None:
        """Get next highest priority candidate for annotation.

        Returns:
            Highest priority candidate, or None if queue empty
        """
        return self.queue.pop()

    def get_batch(self, n: int) -> list[AnnotationCandidate]:
        """Get batch of highest priority candidates.

        Args:
            n: Number of candidates to get

        Returns:
            List of candidates
        """
        return self.queue.pop_batch(n)

    def mark_annotated(
        self,
        candidate_id: str,
        annotation: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Mark a candidate as annotated.

        Args:
            candidate_id: ID of candidate
            annotation: The human annotation
            metadata: Additional metadata
        """
        self.queue.remove_by_id(candidate_id)
        self.annotated_ids.add(candidate_id)
        logger.info(f"Marked {candidate_id} as annotated")

    def mark_skipped(
        self,
        candidate_id: str,
        reason: str = "",
    ) -> None:
        """Mark a candidate as skipped.

        Args:
            candidate_id: ID of candidate
            reason: Reason for skipping
        """
        self.queue.remove_by_id(candidate_id)
        self.skipped_ids.add(candidate_id)
        logger.info(f"Marked {candidate_id} as skipped: {reason}")

    def get_stats(self) -> dict[str, Any]:
        """Get queue statistics.

        Returns:
            Statistics dictionary
        """
        candidates = list(self.queue)

        if not candidates:
            return {
                "queue_size": 0,
                "avg_uncertainty": 0.0,
                "avg_diversity": 0.0,
                "avg_priority": 0.0,
                "annotated_count": len(self.annotated_ids),
                "skipped_count": len(self.skipped_ids),
            }

        return {
            "queue_size": len(candidates),
            "avg_uncertainty": sum(c.uncertainty_score for c in candidates) / len(candidates),
            "avg_diversity": sum(c.diversity_score for c in candidates) / len(candidates),
            "avg_priority": sum(c.priority for c in candidates) / len(candidates),
            "annotated_count": len(self.annotated_ids),
            "skipped_count": len(self.skipped_ids),
        }

    async def push_to_label_studio(
        self,
        project_id: int,
        client: Any,
        batch_size: int = 10,
    ) -> dict[str, Any]:
        """Push candidates to Label Studio for annotation.

        Args:
            project_id: Label Studio project ID
            client: Label Studio client
            batch_size: Number to push

        Returns:
            Result with pushed count and task IDs
        """
        batch = self.get_batch(batch_size)
        task_ids = []

        for candidate in batch:
            try:
                # Create task in Label Studio
                task_data = {
                    "data": {
                        "id": candidate.id,
                        "instruction": candidate.instruction,
                        "output": candidate.output,
                        "uncertainty": candidate.uncertainty_score,
                        "priority": candidate.priority,
                    }
                }

                result = await client.create_task(project_id, task_data)
                task_ids.append(result.get("id"))

                # Mark as in progress
                candidate.status = "in_label_studio"

            except Exception as e:
                logger.error(f"Failed to push {candidate.id} to Label Studio: {e}")
                # Put back in queue
                self.queue.push(candidate)

        logger.info(f"Pushed {len(task_ids)} candidates to Label Studio project {project_id}")

        return {
            "pushed_count": len(task_ids),
            "task_ids": task_ids,
        }
