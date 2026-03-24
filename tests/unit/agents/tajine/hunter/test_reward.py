"""Tests for multi-dimensional reward computation (reward.py)."""
import pytest

from src.infrastructure.agents.tajine.hunter.reward import (
    FetchSignals,
    RewardResult,
    _WEIGHTS,
    compute_reward,
)


class TestComputeReward:
    """Test compute_reward() under various signal profiles."""

    # ------------------------------------------------------------------
    # Success scenarios
    # ------------------------------------------------------------------

    def test_normal_success(self):
        """Typical successful fetch should yield reward > 0.5."""
        signals = FetchSignals(
            item_count=10,
            field_count=8,
            total_fields_possible=10,
            has_dates=True,
            response_time_s=2.0,
            success=True,
        )
        result = compute_reward(signals)

        assert isinstance(result, RewardResult)
        assert result.reward is not None
        assert result.reward > 0.5
        assert result.is_external_failure is False
        # All five dimensions should be present
        assert set(result.components.keys()) == {
            "item_count", "data_richness", "freshness",
            "response_time", "success",
        }

    def test_rich_data(self):
        """High-quality fetch (many items, all fields, fast) should yield reward > 0.8."""
        signals = FetchSignals(
            item_count=20,
            field_count=10,
            total_fields_possible=10,
            has_dates=True,
            response_time_s=0.5,
            success=True,
        )
        result = compute_reward(signals)

        assert result.reward is not None
        assert result.reward > 0.8
        assert result.is_external_failure is False

    def test_poor_data(self):
        """Low-quality fetch (few items, sparse, slow, no dates) should yield reward < 0.4."""
        signals = FetchSignals(
            item_count=1,
            field_count=2,
            total_fields_possible=10,
            has_dates=False,
            response_time_s=25.0,
            success=True,
        )
        result = compute_reward(signals)

        assert result.reward is not None
        assert result.reward < 0.4
        assert result.is_external_failure is False

    # ------------------------------------------------------------------
    # Error classification scenarios
    # ------------------------------------------------------------------

    def test_external_failure_timeout(self):
        """Timeout error should return reward=None and is_external_failure=True."""
        signals = FetchSignals(
            success=False,
            error="Connection timed out after 30s",
        )
        result = compute_reward(signals)

        assert result.reward is None
        assert result.is_external_failure is True
        assert result.components == {}

    def test_external_failure_503(self):
        """HTTP 503 error should return reward=None and is_external_failure=True."""
        signals = FetchSignals(
            success=False,
            error="503 Service Unavailable",
        )
        result = compute_reward(signals)

        assert result.reward is None
        assert result.is_external_failure is True
        assert result.components == {}

    def test_internal_failure_parsing(self):
        """Parsing error should return reward=0.05 (light penalty) and is_external=False."""
        signals = FetchSignals(
            success=False,
            error="JSON decode error: unexpected token at position 42",
        )
        result = compute_reward(signals)

        assert result.reward == 0.05
        assert result.is_external_failure is False
        assert result.components == {"penalty": 0.05}

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_success_false_no_error_uses_dimensions(self):
        """success=False with error=None bypasses error classification
        and falls through to dimension computation.

        The success component will be 0.0 (since success=False), so the
        total reward is lower than a fully successful fetch with the same
        signals, but it is NOT None.
        """
        signals = FetchSignals(
            item_count=10,
            field_count=8,
            total_fields_possible=10,
            has_dates=True,
            response_time_s=2.0,
            success=False,
            error=None,
        )
        result = compute_reward(signals)

        # Not classified as error, so reward is computed
        assert result.reward is not None
        assert result.is_external_failure is False
        # success component is 0 -> reward slightly lower than with success=True
        success_true = compute_reward(
            FetchSignals(
                item_count=10,
                field_count=8,
                total_fields_possible=10,
                has_dates=True,
                response_time_s=2.0,
                success=True,
            )
        )
        assert result.reward < success_true.reward
        # The difference should be exactly _WEIGHTS["success"] * 1.0 = 0.10
        diff = round(success_true.reward - result.reward, 4)
        assert diff == _WEIGHTS["success"]

    # ------------------------------------------------------------------
    # Weight validation
    # ------------------------------------------------------------------

    def test_weights_sum_to_one(self):
        """Dimension weights must sum to exactly 1.0."""
        total = sum(_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9, f"Weights sum to {total}, expected 1.0"
