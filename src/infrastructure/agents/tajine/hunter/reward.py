"""Multi-dimensional reward computation for Source Bandit.

Computes a weighted reward signal from multiple fetch quality dimensions,
with error classification to distinguish external failures (skip update)
from internal failures (light penalty).
"""

from __future__ import annotations

from dataclasses import dataclass

from src.infrastructure.agents.tajine.trust import (
    EXTERNAL_FAILURES,
    classify_failure,
)


@dataclass
class FetchSignals:
    """Raw signals collected after a source fetch."""

    item_count: int = 0
    field_count: int = 0
    total_fields_possible: int = 1  # avoid division by zero
    has_dates: bool = False
    response_time_s: float = 0.0
    success: bool = True
    error: str | Exception | None = None


@dataclass
class RewardResult:
    """Output of reward computation."""

    reward: float | None  # None means "skip bandit update"
    components: dict[str, float]
    is_external_failure: bool = False


# Dimension weights (must sum to 1.0)
_WEIGHTS = {
    "item_count": 0.30,
    "data_richness": 0.25,
    "freshness": 0.20,
    "response_time": 0.15,
    "success": 0.10,
}


def compute_reward(signals: FetchSignals) -> RewardResult:
    """Compute a multi-dimensional reward from fetch signals.

    Dimensions and weights:
        item_count   (30%) - normalised on 20 items
        data_richness(25%) - ratio of filled fields
        freshness    (20%) - 1.0 if dates present, 0.5 otherwise
        response_time(15%) - linear decay over 30 s
        success      (10%) - binary 1.0 / 0.0

    Error handling:
        External error (timeout, 503 ...) -> reward=None (skip update)
        Internal error (parsing ...)      -> reward=0.05 (light penalty)
    """
    # --- Error classification -------------------------------------------------
    if not signals.success and signals.error is not None:
        failure_type = classify_failure(signals.error)
        if failure_type in EXTERNAL_FAILURES:
            return RewardResult(
                reward=None,
                components={},
                is_external_failure=True,
            )
        # Internal failure -> light penalty
        return RewardResult(
            reward=0.05,
            components={"penalty": 0.05},
            is_external_failure=False,
        )

    # --- Compute individual dimensions ----------------------------------------
    components: dict[str, float] = {}

    # item_count: normalised on 20 items, capped at 1.0
    components["item_count"] = min(signals.item_count / 20.0, 1.0)

    # data_richness: ratio of filled fields
    if signals.total_fields_possible > 0:
        components["data_richness"] = signals.field_count / signals.total_fields_possible
    else:
        components["data_richness"] = 0.0

    # freshness: bonus if dates are present
    components["freshness"] = 1.0 if signals.has_dates else 0.5

    # response_time: linear decay (30s -> 0, 0s -> 1)
    components["response_time"] = max(0.0, 1.0 - signals.response_time_s / 30.0)

    # success: binary
    components["success"] = 1.0 if signals.success else 0.0

    # --- Weighted sum ---------------------------------------------------------
    reward = sum(_WEIGHTS[dim] * components[dim] for dim in _WEIGHTS)

    return RewardResult(
        reward=round(reward, 4),
        components=components,
        is_external_failure=False,
    )
