"""Tests for Active Learning Manager."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.learning.active_learning import (
    ActiveLearningManager,
    AnnotationCandidate,
    PriorityQueue,
    SelectionStrategy,
)


class TestAnnotationCandidate:
    """Test AnnotationCandidate dataclass."""

    def test_create_candidate(self):
        """Should create a valid candidate."""
        candidate = AnnotationCandidate(
            id="test_1",
            instruction="What is AI?",
            output="AI is...",
            uncertainty_score=0.8,
        )
        assert candidate.id == "test_1"
        assert candidate.uncertainty_score == 0.8

    def test_candidate_priority(self):
        """Should calculate priority from scores."""
        candidate = AnnotationCandidate(
            id="test_1",
            instruction="Test",
            output="Output",
            uncertainty_score=0.7,
            diversity_score=0.5,
            impact_score=0.3,
        )
        # Default weights: uncertainty=0.5, diversity=0.3, impact=0.2
        expected = 0.7 * 0.5 + 0.5 * 0.3 + 0.3 * 0.2
        assert abs(candidate.priority - expected) < 0.001

    def test_candidate_status_default(self):
        """Should start as pending."""
        candidate = AnnotationCandidate(
            id="test",
            instruction="Test",
            output="Output",
        )
        assert candidate.status == "pending"


class TestPriorityQueue:
    """Test PriorityQueue for candidates."""

    def test_empty_queue(self):
        """Should start empty."""
        queue = PriorityQueue()
        assert len(queue) == 0
        assert queue.is_empty

    def test_push_candidate(self):
        """Should add candidate to queue."""
        queue = PriorityQueue()
        candidate = AnnotationCandidate(
            id="test",
            instruction="Test",
            output="Output",
            uncertainty_score=0.5,
        )
        queue.push(candidate)
        assert len(queue) == 1

    def test_pop_highest_priority(self):
        """Should pop candidate with highest priority."""
        queue = PriorityQueue()

        low = AnnotationCandidate(id="low", instruction="L", output="O", uncertainty_score=0.2)
        high = AnnotationCandidate(id="high", instruction="H", output="O", uncertainty_score=0.9)
        mid = AnnotationCandidate(id="mid", instruction="M", output="O", uncertainty_score=0.5)

        queue.push(low)
        queue.push(high)
        queue.push(mid)

        popped = queue.pop()
        assert popped.id == "high"

    def test_peek_without_removing(self):
        """Should peek without removing."""
        queue = PriorityQueue()
        candidate = AnnotationCandidate(
            id="test",
            instruction="Test",
            output="Output",
            uncertainty_score=0.5,
        )
        queue.push(candidate)

        peeked = queue.peek()
        assert peeked.id == "test"
        assert len(queue) == 1

    def test_pop_batch(self):
        """Should pop multiple candidates."""
        queue = PriorityQueue()

        for i in range(5):
            queue.push(
                AnnotationCandidate(
                    id=f"test_{i}",
                    instruction=f"Test {i}",
                    output="Output",
                    uncertainty_score=i * 0.2,
                )
            )

        batch = queue.pop_batch(3)
        assert len(batch) == 3
        assert len(queue) == 2

    def test_clear(self):
        """Should clear all candidates."""
        queue = PriorityQueue()
        queue.push(AnnotationCandidate(id="test", instruction="T", output="O"))
        queue.clear()
        assert queue.is_empty


class TestSelectionStrategy:
    """Test SelectionStrategy enum."""

    def test_strategies_exist(self):
        """Should have all expected strategies."""
        assert SelectionStrategy.UNCERTAINTY.value == "uncertainty"
        assert SelectionStrategy.DIVERSITY.value == "diversity"
        assert SelectionStrategy.HYBRID.value == "hybrid"


class TestActiveLearningManager:
    """Test ActiveLearningManager class."""

    def test_init(self):
        """Should initialize with empty queue."""
        manager = ActiveLearningManager()
        assert manager.queue.is_empty

    def test_add_candidate(self):
        """Should add candidate to queue."""
        manager = ActiveLearningManager()
        manager.add_candidate(
            id="test",
            instruction="What is AI?",
            output="AI is artificial intelligence.",
            uncertainty_score=0.7,
        )
        assert len(manager.queue) == 1

    def test_add_candidate_with_context(self):
        """Should calculate diversity from context."""
        manager = ActiveLearningManager()

        # Add first candidate
        manager.add_candidate(
            id="test_1",
            instruction="What is AI?",
            output="AI is...",
            uncertainty_score=0.5,
        )

        # Add similar candidate
        manager.add_candidate(
            id="test_2",
            instruction="What is AI?",  # Same instruction
            output="Artificial intelligence is...",
            uncertainty_score=0.5,
        )

        # Second should have lower diversity
        candidates = list(manager.queue)
        c1 = next(c for c in candidates if c.id == "test_1")
        c2 = next(c for c in candidates if c.id == "test_2")

        # First one is always max diversity (1.0)
        assert c1.diversity_score == 1.0
        # Second one should have lower diversity (similar instruction)
        assert c2.diversity_score < 1.0

    def test_get_next_for_annotation(self):
        """Should get next highest priority candidate."""
        manager = ActiveLearningManager()

        manager.add_candidate(id="low", instruction="Low", output="O", uncertainty_score=0.2)
        manager.add_candidate(id="high", instruction="High", output="O", uncertainty_score=0.9)

        candidate = manager.get_next()
        assert candidate.id == "high"

    def test_get_batch_for_annotation(self):
        """Should get batch of candidates."""
        manager = ActiveLearningManager()

        for i in range(10):
            manager.add_candidate(
                id=f"test_{i}",
                instruction=f"Test {i}",
                output="Output",
                uncertainty_score=i * 0.1,
            )

        batch = manager.get_batch(5)
        assert len(batch) == 5

    def test_mark_annotated(self):
        """Should mark candidate as annotated."""
        manager = ActiveLearningManager()
        manager.add_candidate(id="test", instruction="T", output="O")

        manager.mark_annotated("test", annotation="Corrected output")

        # Should be removed from queue
        assert manager.queue.is_empty
        # Should be in annotated history
        assert "test" in manager.annotated_ids

    def test_mark_skipped(self):
        """Should mark candidate as skipped."""
        manager = ActiveLearningManager()
        manager.add_candidate(id="test", instruction="T", output="O")

        manager.mark_skipped("test", reason="Low quality")

        assert manager.queue.is_empty
        assert "test" in manager.skipped_ids

    def test_stats(self):
        """Should return queue statistics."""
        manager = ActiveLearningManager()

        manager.add_candidate(id="1", instruction="A", output="B", uncertainty_score=0.8)
        manager.add_candidate(id="2", instruction="C", output="D", uncertainty_score=0.3)

        stats = manager.get_stats()

        assert stats["queue_size"] == 2
        assert stats["avg_uncertainty"] == 0.55
        assert "annotated_count" in stats

    @pytest.mark.asyncio
    async def test_push_to_label_studio(self):
        """Should push candidates to Label Studio."""
        manager = ActiveLearningManager()
        manager.add_candidate(id="test", instruction="T", output="O", uncertainty_score=0.9)

        # Mock Label Studio client
        mock_client = MagicMock()
        mock_client.create_task = AsyncMock(return_value={"id": 123})

        result = await manager.push_to_label_studio(
            project_id=1,
            client=mock_client,
            batch_size=1,
        )

        assert result["pushed_count"] == 1
        mock_client.create_task.assert_called_once()


class TestDiversityCalculation:
    """Test diversity score calculation."""

    def test_unique_instruction_high_diversity(self):
        """Unique instruction should have high diversity."""
        manager = ActiveLearningManager()

        manager.add_candidate(id="1", instruction="How to cook pasta?", output="O")
        manager.add_candidate(id="2", instruction="What is quantum physics?", output="O")
        manager.add_candidate(id="3", instruction="Explain photosynthesis", output="O")

        # All different, so all should have high diversity
        for candidate in manager.queue:
            assert candidate.diversity_score >= 0.8

    def test_similar_instructions_lower_diversity(self):
        """Similar instructions should have lower diversity."""
        manager = ActiveLearningManager()

        manager.add_candidate(id="1", instruction="What is AI?", output="O")
        manager.add_candidate(id="2", instruction="What is AI technology?", output="O")

        candidates = sorted(manager.queue, key=lambda c: c.id)
        # Second one should have lower diversity (similar to first)
        assert candidates[1].diversity_score < candidates[0].diversity_score
