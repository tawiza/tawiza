"""Multi-Armed Bandit scheduler using UCB algorithm."""
import math

from loguru import logger

from .source_arm import SourceArm


class MABScheduler:
    """
    Multi-Armed Bandit scheduler for source selection.

    Uses Upper Confidence Bound (UCB) algorithm to balance
    exploration (trying new sources) vs exploitation (using proven sources).

    UCB Score = average_reward + C * sqrt(log(N) / n_i)

    Where:
    - average_reward = weighted combination of freshness/quality/relevance
    - C = exploration parameter (default 2.0)
    - N = total pulls across all arms
    - n_i = pulls for this specific arm
    """

    def __init__(self, exploration_param: float = 2.0):
        """
        Initialize MAB scheduler.

        Args:
            exploration_param: UCB exploration constant (higher = more exploration)
        """
        self.exploration_param = exploration_param
        self.arms: dict[str, SourceArm] = {}
        self.total_pulls: int = 0

    def add_arm(self, arm: SourceArm) -> None:
        """Add a source arm to the scheduler."""
        self.arms[arm.source_id] = arm
        logger.debug(f"Added arm: {arm.source_id}")

    def remove_arm(self, source_id: str) -> None:
        """Remove a source arm from the scheduler."""
        if source_id in self.arms:
            del self.arms[source_id]
            logger.debug(f"Removed arm: {source_id}")

    def get_arm(self, source_id: str) -> SourceArm | None:
        """Get arm by source ID."""
        return self.arms.get(source_id)

    def compute_ucb(self, arm: SourceArm) -> float:
        """
        Compute UCB score for an arm.

        Args:
            arm: Source arm to score

        Returns:
            UCB score (higher = should select)
        """
        if arm.pulls == 0:
            return float('inf')

        exploitation = arm.average_reward

        if self.total_pulls > 0:
            exploration = self.exploration_param * math.sqrt(
                math.log(self.total_pulls) / arm.pulls
            )
        else:
            exploration = 0

        return exploitation + exploration

    def select_next(self) -> SourceArm | None:
        """
        Select the next source to crawl based on UCB scores.

        Returns:
            Best arm to pull, or None if no arms
        """
        if not self.arms:
            return None

        best_arm = None
        best_score = float('-inf')

        for arm in self.arms.values():
            score = self.compute_ucb(arm)
            if score > best_score:
                best_score = score
                best_arm = arm

        return best_arm

    def select_batch(self, batch_size: int) -> list[SourceArm]:
        """
        Select multiple sources for parallel crawling.

        Args:
            batch_size: Number of sources to select

        Returns:
            List of arms to crawl
        """
        if not self.arms:
            return []

        scored = [(arm, self.compute_ucb(arm)) for arm in self.arms.values()]
        scored.sort(key=lambda x: x[1], reverse=True)

        return [arm for arm, _ in scored[:batch_size]]

    def record_result(
        self,
        source_id: str,
        success: bool,
        freshness: float | None = None,
        quality: float | None = None
    ) -> None:
        """
        Record crawl result for an arm.

        Args:
            source_id: ID of the crawled source
            success: Whether crawl succeeded
            freshness: New freshness score
            quality: New quality score
        """
        arm = self.arms.get(source_id)
        if arm:
            arm.record_pull(success, freshness, quality)
            self.total_pulls += 1

    def update_relevance(self, source_id: str, was_useful: bool) -> None:
        """
        Update relevance score based on TAJINE feedback.

        Args:
            source_id: Source that provided data
            was_useful: Whether data was used in response
        """
        arm = self.arms.get(source_id)
        if arm:
            arm.update_relevance(was_useful)
