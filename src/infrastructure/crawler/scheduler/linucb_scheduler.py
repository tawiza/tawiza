"""Contextual Multi-Armed Bandit scheduler using LinUCB algorithm.

LinUCB uses context features to make better source selection decisions:
- Territory features: department code, region, urban/rural
- Query features: domain (entreprises, emploi, etc.), complexity
- Temporal features: time of day, day of week

This enables territory-aware source selection for TAJINE.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
from loguru import logger

from .source_arm import SourceArm


@dataclass
class ContextFeatures:
    """Context features for LinUCB decision making.

    Features are normalized to [0, 1] range for numerical stability.
    """

    # Territory features
    department_code: str | None = None  # "75", "69", etc.
    is_urban: bool = True
    is_overseas: bool = False  # DOM-TOM

    # Query features
    domain: str = "general"  # entreprises, emploi, immobilier, etc.
    complexity: float = 0.5  # 0=simple, 1=complex

    # Temporal features
    hour: int = 12  # 0-23
    day_of_week: int = 0  # 0=Monday

    # Source-specific
    source_type: str = "api"  # api, web, rss

    def to_vector(self) -> np.ndarray:
        """Convert features to numpy vector for LinUCB.

        Returns 10-dimensional feature vector:
        [dept_hash, is_urban, is_overseas, domain_hash, complexity,
         hour_sin, hour_cos, dow_sin, dow_cos, source_type_hash]
        """
        # Hash department to [0, 1]
        dept_val = 0.5
        if self.department_code:
            try:
                dept_num = int(self.department_code[:2])
                dept_val = dept_num / 100.0
            except ValueError:
                pass

        # Domain encoding (simple hash)
        domain_hash = hash(self.domain) % 100 / 100.0

        # Cyclical encoding for time features
        hour_sin = math.sin(2 * math.pi * self.hour / 24)
        hour_cos = math.cos(2 * math.pi * self.hour / 24)
        dow_sin = math.sin(2 * math.pi * self.day_of_week / 7)
        dow_cos = math.cos(2 * math.pi * self.day_of_week / 7)

        # Source type encoding
        source_map = {"api": 0.0, "web": 0.5, "rss": 1.0}
        source_val = source_map.get(self.source_type, 0.5)

        return np.array(
            [
                dept_val,
                float(self.is_urban),
                float(self.is_overseas),
                domain_hash,
                self.complexity,
                hour_sin,
                hour_cos,
                dow_sin,
                dow_cos,
                source_val,
            ]
        )

    @classmethod
    def from_query(
        cls,
        query: str,
        territory: str | None = None,
        domain: str = "general",
    ) -> ContextFeatures:
        """Create context features from a TAJINE query.

        Args:
            query: User query string
            territory: Department code or territory name
            domain: Query domain (entreprises, emploi, etc.)
        """
        now = datetime.now()

        # Estimate complexity from query length and keywords
        complexity = min(1.0, len(query.split()) / 20)
        complex_keywords = ["corrélation", "tendance", "évolution", "comparaison"]
        if any(kw in query.lower() for kw in complex_keywords):
            complexity = min(1.0, complexity + 0.3)

        # Detect if overseas territory
        is_overseas = territory in (
            "971",
            "972",
            "973",
            "974",
            "976",
        )  # Guadeloupe, Martinique, Guyane, Réunion, Mayotte

        # Detect urban (major cities)
        urban_depts = {"75", "69", "13", "31", "33", "59", "06", "34", "67", "44"}
        is_urban = territory in urban_depts if territory else True

        return cls(
            department_code=territory,
            is_urban=is_urban,
            is_overseas=is_overseas,
            domain=domain,
            complexity=complexity,
            hour=now.hour,
            day_of_week=now.weekday(),
        )


@dataclass
class LinUCBArm:
    """LinUCB arm with context-dependent reward model.

    Maintains a linear model: E[reward|context] = theta^T * context
    With confidence bounds from the covariance matrix.
    """

    source_id: str
    d: int = 10  # Feature dimension (matches ContextFeatures.to_vector())
    alpha: float = 0.5  # Exploration parameter

    # Linear model parameters (initialized on first use)
    A: np.ndarray = field(default_factory=lambda: None)  # type: ignore
    b: np.ndarray = field(default_factory=lambda: None)  # type: ignore

    # Statistics
    pulls: int = 0
    total_reward: float = 0.0

    def __post_init__(self):
        """Initialize matrices if not provided."""
        if self.A is None:
            self.A = np.eye(self.d)
        if self.b is None:
            self.b = np.zeros(self.d)

    def compute_ucb(self, context: np.ndarray) -> float:
        """Compute LinUCB score for given context.

        UCB = theta^T * context + alpha * sqrt(context^T * A^-1 * context)
        """
        A_inv = np.linalg.inv(self.A)
        theta = A_inv @ self.b

        # Expected reward
        exploitation = float(theta @ context)

        # Confidence bound
        exploration = self.alpha * math.sqrt(float(context @ A_inv @ context))

        return exploitation + exploration

    def update(self, context: np.ndarray, reward: float) -> None:
        """Update model after observing reward.

        Args:
            context: Feature vector used for selection
            reward: Observed reward (0-1)
        """
        self.A += np.outer(context, context)
        self.b += reward * context
        self.pulls += 1
        self.total_reward += reward

    @property
    def average_reward(self) -> float:
        """Average reward across all pulls."""
        return self.total_reward / self.pulls if self.pulls > 0 else 0.5


class LinUCBScheduler:
    """Contextual bandit scheduler using LinUCB algorithm.

    LinUCB extends UCB by learning a linear relationship between
    context features and expected rewards. This enables:

    - Better source selection for specific territories
    - Adaptation to query complexity
    - Time-aware scheduling (some APIs are slower at certain hours)
    """

    def __init__(
        self,
        alpha: float = 0.5,
        feature_dim: int = 10,
        fallback_to_ucb1: bool = True,
    ):
        """Initialize LinUCB scheduler.

        Args:
            alpha: Exploration parameter (higher = more exploration)
            feature_dim: Dimension of context features
            fallback_to_ucb1: Fall back to UCB1 if context is unavailable
        """
        self.alpha = alpha
        self.d = feature_dim
        self.fallback_to_ucb1 = fallback_to_ucb1
        self.arms: dict[str, LinUCBArm] = {}
        self.source_arms: dict[str, SourceArm] = {}  # Original SourceArm for compatibility

    def add_arm(self, arm: SourceArm) -> None:
        """Add a source arm to the scheduler."""
        self.source_arms[arm.source_id] = arm
        self.arms[arm.source_id] = LinUCBArm(
            source_id=arm.source_id,
            d=self.d,
            alpha=self.alpha,
        )
        logger.debug(f"Added LinUCB arm: {arm.source_id}")

    def remove_arm(self, source_id: str) -> None:
        """Remove a source arm from the scheduler."""
        self.arms.pop(source_id, None)
        self.source_arms.pop(source_id, None)
        logger.debug(f"Removed LinUCB arm: {source_id}")

    def get_arm(self, source_id: str) -> SourceArm | None:
        """Get original SourceArm by ID (for compatibility)."""
        return self.source_arms.get(source_id)

    def select_next(
        self,
        context: ContextFeatures | np.ndarray | None = None,
    ) -> SourceArm | None:
        """Select next source to crawl based on context.

        Args:
            context: Context features or vector (optional)

        Returns:
            Best source arm for this context
        """
        if not self.arms:
            return None

        # Convert context to vector
        if context is None and self.fallback_to_ucb1:
            return self._select_ucb1()
        elif isinstance(context, ContextFeatures):
            context_vec = context.to_vector()
        elif isinstance(context, np.ndarray):
            context_vec = context
        else:
            return self._select_ucb1()

        # Find best arm by LinUCB score
        best_source_id = None
        best_score = float("-inf")

        for source_id, arm in self.arms.items():
            score = arm.compute_ucb(context_vec)
            if score > best_score:
                best_score = score
                best_source_id = source_id

        return self.source_arms.get(best_source_id) if best_source_id else None

    def _select_ucb1(self) -> SourceArm | None:
        """Fallback to UCB1 when no context available."""
        total_pulls = sum(arm.pulls for arm in self.arms.values())

        best_arm = None
        best_score = float("-inf")

        for source_id, arm in self.arms.items():
            if arm.pulls == 0:
                return self.source_arms.get(source_id)

            exploitation = arm.average_reward
            exploration = math.sqrt(2 * math.log(max(1, total_pulls)) / arm.pulls)
            score = exploitation + exploration

            if score > best_score:
                best_score = score
                best_arm = source_id

        return self.source_arms.get(best_arm) if best_arm else None

    def select_batch(
        self,
        batch_size: int,
        context: ContextFeatures | None = None,
    ) -> list[SourceArm]:
        """Select multiple sources for parallel crawling.

        Uses Thompson Sampling-style selection to get diverse sources.
        """
        if not self.arms:
            return []

        context_vec = context.to_vector() if context else None
        selected: list[SourceArm] = []
        excluded: set[str] = set()

        for _ in range(min(batch_size, len(self.arms))):
            best_source_id = None
            best_score = float("-inf")

            for source_id, arm in self.arms.items():
                if source_id in excluded:
                    continue

                if context_vec is not None:
                    score = arm.compute_ucb(context_vec)
                    # Add noise for diversity
                    score += np.random.normal(0, 0.1)
                else:
                    score = arm.average_reward + np.random.random()

                if score > best_score:
                    best_score = score
                    best_source_id = source_id

            if best_source_id:
                excluded.add(best_source_id)
                if arm := self.source_arms.get(best_source_id):
                    selected.append(arm)

        return selected

    def record_result(
        self,
        source_id: str,
        context: ContextFeatures | np.ndarray | None,
        success: bool,
        quality: float | None = None,
    ) -> None:
        """Record result and update model.

        Args:
            source_id: Source that was used
            context: Context features used for selection
            success: Whether crawl succeeded
            quality: Quality score of extracted data (0-1)
        """
        if source_id not in self.arms:
            return

        # Compute reward (success + quality)
        reward = 0.5 if success else 0.0
        if quality is not None:
            reward = (reward + quality) / 2

        # Update LinUCB model
        if context is not None:
            context_vec = (
                context.to_vector()
                if isinstance(context, ContextFeatures)
                else context
            )
            self.arms[source_id].update(context_vec, reward)

        # Also update original SourceArm for compatibility
        if arm := self.source_arms.get(source_id):
            arm.record_pull(success, quality=quality)

        logger.debug(
            f"LinUCB update: {source_id} success={success} reward={reward:.2f}"
        )

    def get_stats(self) -> dict[str, Any]:
        """Get scheduler statistics for debugging."""
        stats = {
            "total_arms": len(self.arms),
            "total_pulls": sum(arm.pulls for arm in self.arms.values()),
            "arms": {},
        }

        for source_id, arm in self.arms.items():
            stats["arms"][source_id] = {
                "pulls": arm.pulls,
                "avg_reward": arm.average_reward,
            }

        return stats

    def save_state(self) -> dict[str, Any]:
        """Save scheduler state for persistence."""
        return {
            "alpha": self.alpha,
            "d": self.d,
            "arms": {
                source_id: {
                    "A": arm.A.tolist(),
                    "b": arm.b.tolist(),
                    "pulls": arm.pulls,
                    "total_reward": arm.total_reward,
                }
                for source_id, arm in self.arms.items()
            },
            "source_arms": {
                source_id: arm.to_dict()
                for source_id, arm in self.source_arms.items()
            },
        }

    def load_state(self, state: dict[str, Any]) -> None:
        """Load scheduler state from persistence."""
        self.alpha = state.get("alpha", 0.5)
        self.d = state.get("d", 10)

        # Restore source arms
        for source_id, arm_data in state.get("source_arms", {}).items():
            self.source_arms[source_id] = SourceArm.from_dict(arm_data)

        # Restore LinUCB arms
        for source_id, arm_data in state.get("arms", {}).items():
            self.arms[source_id] = LinUCBArm(
                source_id=source_id,
                d=self.d,
                alpha=self.alpha,
                A=np.array(arm_data["A"]),
                b=np.array(arm_data["b"]),
                pulls=arm_data["pulls"],
                total_reward=arm_data["total_reward"],
            )
