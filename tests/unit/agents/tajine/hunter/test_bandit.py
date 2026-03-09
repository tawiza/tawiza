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


class TestSourceBanditEMA:
    """Test EMA decay and persistence (state_to_dict / state_from_dict)."""

    def test_ema_convergence(self):
        """After 50 updates at 0.8, EMA reward should converge near 0.8."""
        bandit = SourceBandit(sources=["sirene", "bodacc"], decay_alpha=0.05)
        for _ in range(50):
            bandit.update("sirene", reward=0.8)

        ema = bandit.arm_rewards[0]
        # With alpha=0.05 and 50 obs, EMA should be very close to 0.8
        # After first obs: 0.8.  Each subsequent: (0.95 * prev + 0.05 * 0.8)
        # converges to 0.8.  Tolerance of 0.05 is generous.
        assert abs(ema - 0.8) < 0.05, f"EMA {ema} not close to 0.8"
        # raw_counts should track total pulls
        assert bandit.arm_raw_counts[0] == 50
        assert bandit.total_pulls == 50

    def test_state_to_dict_contains_all_fields(self):
        """state_to_dict() must include all EMA-era fields."""
        bandit = SourceBandit(
            sources=["sirene", "bodacc"],
            exploration_factor=1.5,
            decay_alpha=0.10,
        )
        bandit.update("sirene", reward=0.7)

        state = bandit.state_to_dict()

        expected_keys = {
            "sources",
            "exploration_factor",
            "decay_alpha",
            "arm_counts",
            "arm_rewards",
            "arm_raw_counts",
            "total_pulls",
        }
        assert set(state.keys()) == expected_keys
        assert state["decay_alpha"] == 0.10
        assert state["arm_raw_counts"] == [1, 0]

    def test_state_from_dict_backward_compat(self):
        """state_from_dict() should handle old format (no arm_raw_counts, no decay_alpha)."""
        bandit = SourceBandit(sources=["a", "b"], decay_alpha=0.05)

        old_state = {
            "sources": ["a", "b"],
            "exploration_factor": 2.0,
            "arm_counts": [10, 5],
            "arm_rewards": [0.6, 0.4],
            "total_pulls": 15,
            # No arm_raw_counts, no decay_alpha
        }

        ok = bandit.state_from_dict(old_state)
        assert ok is True
        # arm_raw_counts should fall back to arm_counts copy
        assert bandit.arm_raw_counts == [10, 5]
        # decay_alpha should keep the instance default (0.05)
        assert bandit.decay_alpha == 0.05
        assert bandit.arm_rewards == [0.6, 0.4]
        assert bandit.total_pulls == 15

    def test_state_from_dict_mismatched_sources(self):
        """state_from_dict() should return False when sources differ."""
        bandit = SourceBandit(sources=["sirene", "bodacc"])

        state = {
            "sources": ["alpha", "beta"],
            "exploration_factor": 2.0,
            "arm_counts": [1, 1],
            "arm_rewards": [0.5, 0.5],
            "arm_raw_counts": [1, 1],
            "total_pulls": 2,
            "decay_alpha": 0.05,
        }

        ok = bandit.state_from_dict(state)
        assert ok is False
        # Internal state should be unchanged (still zeros from __post_init__)
        assert bandit.arm_counts == [0, 0]
        assert bandit.total_pulls == 0
