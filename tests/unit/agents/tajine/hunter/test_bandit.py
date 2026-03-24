"""Tests for Source Bandit (UCB-based source selection)."""

import pytest

from src.infrastructure.agents.tajine.hunter.bandit import SourceBandit


class TestSourceBandit:
    """Test UCB-based source selection."""

    def test_init_with_sources(self):
        """Should initialize with list of sources."""
        bandit = SourceBandit(sources=["sirene", "bodacc", "boamp"])
        assert len(bandit.sources) == 3

    def test_select_returns_sources(self):
        """Should return n selected sources."""
        bandit = SourceBandit(sources=["sirene", "bodacc", "boamp"])
        selected = bandit.select(n=2)
        assert len(selected) == 2
        assert all(s in bandit.sources for s in selected)

    def test_update_increases_count(self):
        """Should update arm statistics after observation."""
        bandit = SourceBandit(sources=["sirene", "bodacc"])
        bandit.update("sirene", reward=1.0)
        assert bandit.arm_counts[0] == 1
        assert bandit.arm_rewards[0] == 1.0

    def test_ucb_exploration(self):
        """UCB should prefer unexplored sources early on."""
        bandit = SourceBandit(sources=["sirene", "bodacc", "boamp"])
        # Update sirene many times
        for _ in range(100):
            bandit.update("sirene", reward=0.8)
        # Unexplored sources should have high UCB
        assert bandit.get_ucb_score(1) > bandit.get_ucb_score(0)

    def test_exploitation_after_exploration(self):
        """After enough exploration, best arm should be selected."""
        bandit = SourceBandit(sources=["sirene", "bodacc"])
        # sirene has high reward
        for _ in range(50):
            bandit.update("sirene", reward=0.9)
        # bodacc has low reward
        for _ in range(50):
            bandit.update("bodacc", reward=0.3)
        # After exploration, sirene should dominate
        selections = [bandit.select(n=1)[0] for _ in range(100)]
        sirene_count = selections.count("sirene")
        assert sirene_count > 70  # Should select sirene most often


