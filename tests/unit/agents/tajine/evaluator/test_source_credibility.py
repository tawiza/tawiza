"""Tests for Bayesian source credibility scoring."""

import pytest

from src.infrastructure.agents.tajine.evaluator.source_credibility import (
    SourceCredibilityScorer,
)


class TestSourceCredibilityScorer:
    """Test Bayesian source credibility."""

    def test_prior_scores_exist(self):
        """Should have prior scores for known sources."""
        scorer = SourceCredibilityScorer()

        assert scorer.score("sirene") > 0.9
        assert scorer.score("bodacc") > 0.85
        assert scorer.score("blog") < 0.5
        assert scorer.score("unknown") < 0.2

    def test_update_increases_score(self):
        """Correct observations should increase score."""
        scorer = SourceCredibilityScorer()

        initial = scorer.score("sirene")

        for _ in range(10):
            scorer.update("sirene", was_correct=True)

        updated = scorer.score("sirene")
        assert updated >= initial

    def test_update_decreases_score(self):
        """Incorrect observations should decrease score."""
        scorer = SourceCredibilityScorer()

        # First establish some history
        for _ in range(5):
            scorer.update("blog", was_correct=True)

        initial = scorer.score("blog")

        for _ in range(10):
            scorer.update("blog", was_correct=False)

        updated = scorer.score("blog")
        assert updated < initial

    def test_unknown_source_gets_default(self):
        """Unknown sources should get low default score."""
        scorer = SourceCredibilityScorer()
        assert scorer.score("totally_unknown_source") == scorer.PRIORS["unknown"]

    def test_score_bounds(self):
        """Score should always be between 0 and 1."""
        scorer = SourceCredibilityScorer()

        # Many positive updates
        for _ in range(1000):
            scorer.update("test_source", was_correct=True)

        assert 0 <= scorer.score("test_source") <= 1
