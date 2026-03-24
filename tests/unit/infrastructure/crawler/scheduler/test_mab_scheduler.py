"""Tests for MAB Scheduler with UCB algorithm."""

import pytest

from src.infrastructure.crawler.scheduler.mab_scheduler import MABScheduler
from src.infrastructure.crawler.scheduler.source_arm import SourceArm, SourceType


class TestMABSchedulerCreation:
    """Test MABScheduler initialization."""

    def test_create_empty_scheduler(self):
        """Create scheduler with no sources."""
        scheduler = MABScheduler()
        assert len(scheduler.arms) == 0

    def test_create_with_exploration_param(self):
        """Create scheduler with custom exploration parameter."""
        scheduler = MABScheduler(exploration_param=3.0)
        assert scheduler.exploration_param == 3.0

    def test_add_source(self):
        """Add a source to the scheduler."""
        scheduler = MABScheduler()
        arm = SourceArm(source_id="test", url="https://example.com", source_type=SourceType.API)
        scheduler.add_arm(arm)
        assert len(scheduler.arms) == 1


class TestUCBAlgorithm:
    """Test UCB score calculation."""

    def test_ucb_score_unexplored(self):
        """Unexplored arms get infinite score."""
        scheduler = MABScheduler()
        arm = SourceArm(source_id="test", url="https://example.com", source_type=SourceType.API)
        scheduler.add_arm(arm)
        score = scheduler.compute_ucb(arm)
        assert score == float("inf")

    def test_ucb_score_explored(self):
        """Explored arms get finite UCB score."""
        scheduler = MABScheduler()
        arm = SourceArm(
            source_id="test",
            url="https://example.com",
            source_type=SourceType.API,
            pulls=10,
            freshness_score=0.8,
            quality_score=0.7,
            relevance_score=0.9,
        )
        scheduler.add_arm(arm)
        scheduler.total_pulls = 100
        score = scheduler.compute_ucb(arm)
        assert 0 < score < 10


class TestSourceSelection:
    """Test source selection logic."""

    def test_select_single_source(self):
        """Select the only available source."""
        scheduler = MABScheduler()
        arm = SourceArm(source_id="only", url="https://example.com", source_type=SourceType.API)
        scheduler.add_arm(arm)
        selected = scheduler.select_next()
        assert selected.source_id == "only"

    def test_select_prioritizes_unexplored(self):
        """Unexplored sources are selected first."""
        scheduler = MABScheduler()
        explored = SourceArm(
            source_id="explored", url="https://a.com", source_type=SourceType.API, pulls=10
        )
        unexplored = SourceArm(
            source_id="unexplored", url="https://b.com", source_type=SourceType.API, pulls=0
        )
        scheduler.add_arm(explored)
        scheduler.add_arm(unexplored)
        scheduler.total_pulls = 10

        selected = scheduler.select_next()
        assert selected.source_id == "unexplored"

    def test_select_batch(self):
        """Select multiple sources for parallel crawling."""
        scheduler = MABScheduler()
        for i in range(10):
            arm = SourceArm(
                source_id=f"source-{i}", url=f"https://example{i}.com", source_type=SourceType.API
            )
            scheduler.add_arm(arm)

        batch = scheduler.select_batch(5)
        assert len(batch) == 5
        ids = [arm.source_id for arm in batch]
        assert len(set(ids)) == 5

    def test_select_empty_scheduler(self):
        """Select from empty scheduler returns None."""
        scheduler = MABScheduler()
        selected = scheduler.select_next()
        assert selected is None


class TestResultRecording:
    """Test result recording."""

    def test_record_result(self):
        """Record crawl result updates arm."""
        scheduler = MABScheduler()
        arm = SourceArm(source_id="test", url="https://example.com", source_type=SourceType.API)
        scheduler.add_arm(arm)

        scheduler.record_result("test", success=True, freshness=0.9, quality=0.8)

        assert scheduler.total_pulls == 1
        assert arm.pulls == 1
        assert arm.successes == 1
        assert arm.freshness_score == 0.9

    def test_update_relevance(self):
        """Update relevance from TAJINE feedback."""
        scheduler = MABScheduler()
        arm = SourceArm(source_id="test", url="https://example.com", source_type=SourceType.API)
        scheduler.add_arm(arm)
        initial = arm.relevance_score

        scheduler.update_relevance("test", was_useful=True)

        assert arm.relevance_score > initial
