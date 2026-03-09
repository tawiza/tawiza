"""Source Bandit - UCB-based source selection."""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class SourceBandit:
    """
    Multi-Armed Bandit for intelligent source selection.

    Uses UCB1 (Upper Confidence Bound) algorithm to balance
    exploration of new sources vs exploitation of known good ones.
    """
    sources: list[str]
    exploration_factor: float = 2.0

    # Per-arm statistics
    arm_counts: list[int] = field(init=False)
    arm_rewards: list[float] = field(init=False)
    total_pulls: int = field(default=0, init=False)

    def __post_init__(self):
        """Initialize arm statistics."""
        n_arms = len(self.sources)
        self.arm_counts = [0] * n_arms
        self.arm_rewards = [0.0] * n_arms

    def select(self, n: int = 1) -> list[str]:
        """
        Select n sources using UCB1.

        UCB(a) = mean_reward(a) + c * sqrt(ln(t) / n_a)

        Where:
        - mean_reward(a) = exploitation term
        - sqrt(ln(t) / n_a) = exploration bonus
        - c = exploration factor
        """
        if n >= len(self.sources):
            return list(self.sources)

        # Compute UCB scores for all arms
        ucb_scores = [self.get_ucb_score(i) for i in range(len(self.sources))]

        # Select top n arms by UCB score
        indexed_scores = list(enumerate(ucb_scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)

        selected_indices = [idx for idx, _ in indexed_scores[:n]]
        return [self.sources[i] for i in selected_indices]

    def get_ucb_score(self, arm_index: int) -> float:
        """Compute UCB score for an arm."""
        if self.arm_counts[arm_index] == 0:
            return float('inf')  # Always explore unvisited arms

        mean_reward = self.arm_rewards[arm_index] / self.arm_counts[arm_index]

        if self.total_pulls == 0:
            exploration_bonus = float('inf')
        else:
            exploration_bonus = self.exploration_factor * math.sqrt(
                math.log(self.total_pulls) / self.arm_counts[arm_index]
            )

        return mean_reward + exploration_bonus

    def update(self, source: str, reward: float):
        """Update statistics after observing a reward."""
        arm_index = self.sources.index(source)
        self.arm_counts[arm_index] += 1
        self.arm_rewards[arm_index] += reward
        self.total_pulls += 1

    def get_arm_mean(self, source: str) -> float:
        """Get mean reward for a source."""
        arm_index = self.sources.index(source)
        if self.arm_counts[arm_index] == 0:
            return 0.0
        return self.arm_rewards[arm_index] / self.arm_counts[arm_index]

    def reset(self):
        """Reset all statistics."""
        n_arms = len(self.sources)
        self.arm_counts = [0] * n_arms
        self.arm_rewards = [0.0] * n_arms
        self.total_pulls = 0
