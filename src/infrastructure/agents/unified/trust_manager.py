"""Trust Manager - Controls agent autonomy based on multi-criteria scoring."""

from datetime import UTC, datetime, timedelta

from loguru import logger

from .config import AutonomyLevel, TrustConfig


def utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(UTC)


class TrustManager:
    """Manages trust score and autonomy levels.

    Trust score is calculated from:
    - Metrics (40%): accuracy, success rate, error rate
    - Feedback (35%): positive/negative human feedback
    - History (25%): days without incident, completed tasks

    The agent progresses through autonomy levels as trust increases:
    - SUPERVISED (0): Human validates everything
    - ASSISTED (1): Human validates important decisions
    - SEMI_AUTONOMOUS (2): Human validates only fine-tuning
    - AUTONOMOUS (3): Agent autonomous with alerts
    - FULL_AUTONOMOUS (4): Fully autonomous
    """

    # Tasks that require specific autonomy levels
    TASK_REQUIREMENTS = {
        "web_scraping": AutonomyLevel.ASSISTED,
        "code_execution": AutonomyLevel.ASSISTED,
        "annotation": AutonomyLevel.SEMI_AUTONOMOUS,
        "dataset_creation": AutonomyLevel.SEMI_AUTONOMOUS,
        "fine_tuning": AutonomyLevel.FULL_AUTONOMOUS,
        "model_deployment": AutonomyLevel.FULL_AUTONOMOUS,
    }

    def __init__(self, config: TrustConfig | None = None):
        """Initialize trust manager.

        Args:
            config: Trust configuration, uses defaults if None
        """
        self.config = config or TrustConfig()
        self._level = AutonomyLevel.SUPERVISED
        self._score = 0.0

        # Metrics storage
        self._metrics = {"accuracy": 0.0, "success_rate": 0.0, "error_rate": 1.0}
        self._feedback = {"positive": 0, "negative": 0}
        self._history = {"days_without_incident": 0, "tasks_completed": 0}

        # Cooldown state
        self._cooldown_until: datetime | None = None
        self._last_update = utc_now()

        logger.info(f"TrustManager initialized at level {self._level.name}")

    @property
    def level(self) -> AutonomyLevel:
        """Current autonomy level."""
        return self._level

    @property
    def score(self) -> float:
        """Current trust score (0.0 to 1.0)."""
        return self._score

    @property
    def is_in_cooldown(self) -> bool:
        """Check if manager is in cooldown period."""
        if self._cooldown_until is None:
            return False
        return utc_now() < self._cooldown_until

    def record_metrics(
        self,
        accuracy: float,
        success_rate: float,
        error_rate: float
    ) -> None:
        """Record performance metrics.

        Args:
            accuracy: Model/task accuracy (0-1)
            success_rate: Task success rate (0-1)
            error_rate: Error rate (0-1)
        """
        self._metrics = {
            "accuracy": max(0, min(1, accuracy)),
            "success_rate": max(0, min(1, success_rate)),
            "error_rate": max(0, min(1, error_rate)),
        }
        logger.debug(f"Recorded metrics: {self._metrics}")

    def record_feedback(self, positive: int, negative: int) -> None:
        """Record human feedback counts.

        Args:
            positive: Number of positive validations
            negative: Number of negative corrections
        """
        self._feedback = {"positive": positive, "negative": negative}
        logger.debug(f"Recorded feedback: {self._feedback}")

    def record_history(self, days_without_incident: int, tasks_completed: int) -> None:
        """Record historical performance.

        Args:
            days_without_incident: Consecutive days without major error
            tasks_completed: Total tasks completed successfully
        """
        self._history = {
            "days_without_incident": days_without_incident,
            "tasks_completed": tasks_completed,
        }
        logger.debug(f"Recorded history: {self._history}")

    def calculate_score(self) -> float:
        """Calculate trust score from all criteria.

        Returns:
            Trust score between 0.0 and 1.0
        """
        # Metrics score (accuracy, success, low errors)
        metrics_score = (
            self._metrics["accuracy"] * 0.4 +
            self._metrics["success_rate"] * 0.4 +
            (1 - self._metrics["error_rate"]) * 0.2
        )

        # Feedback score
        total_feedback = self._feedback["positive"] + self._feedback["negative"]
        if total_feedback > 0:
            feedback_score = self._feedback["positive"] / total_feedback
        else:
            feedback_score = 0.5  # Neutral if no feedback

        # History score (normalized)
        days_score = min(1.0, self._history["days_without_incident"] / 30)
        tasks_score = min(1.0, self._history["tasks_completed"] / 100)
        history_score = (days_score + tasks_score) / 2

        # Weighted combination
        self._score = (
            metrics_score * self.config.metrics_weight +
            feedback_score * self.config.feedback_weight +
            history_score * self.config.history_weight
        )

        logger.debug(
            f"Trust score calculated: {self._score:.3f} "
            f"(metrics={metrics_score:.2f}, feedback={feedback_score:.2f}, history={history_score:.2f})"
        )

        return self._score

    def update_level(self) -> AutonomyLevel:
        """Update autonomy level based on current score.

        Returns:
            New autonomy level
        """
        if self.is_in_cooldown:
            logger.info("In cooldown, level unchanged")
            return self._level

        # Determine appropriate level from score
        new_level = AutonomyLevel.SUPERVISED
        for i, threshold in enumerate(self.config.level_thresholds):
            if self._score >= threshold:
                new_level = AutonomyLevel(i + 1)

        # Handle regression
        if new_level < self._level:
            if self.config.rollback_on_regression:
                logger.warning(
                    f"Trust regression: {self._level.name} -> {new_level.name}"
                )
                self._level = new_level
            # If rollback disabled, keep current level
        elif new_level > self._level:
            logger.info(f"Trust promotion: {self._level.name} -> {new_level.name}")
            self._level = new_level

        self._last_update = utc_now()
        return self._level

    def trigger_cooldown(self, hours: int | None = None) -> None:
        """Trigger cooldown period after major error.

        Args:
            hours: Cooldown duration, uses config default if None
        """
        duration = hours or self.config.cooldown_hours
        self._cooldown_until = utc_now() + timedelta(hours=duration)
        logger.warning(f"Cooldown triggered for {duration} hours")

    def requires_approval(self, task_type: str) -> bool:
        """Check if task requires human approval at current level.

        Args:
            task_type: Type of task to check

        Returns:
            True if approval required
        """
        required_level = self.TASK_REQUIREMENTS.get(
            task_type,
            AutonomyLevel.SUPERVISED
        )
        return self._level < required_level

    def to_dict(self) -> dict:
        """Export state to dictionary."""
        return {
            "level": self._level.name,
            "level_value": self._level.value,
            "score": self._score,
            "metrics": self._metrics,
            "feedback": self._feedback,
            "history": self._history,
            "in_cooldown": self.is_in_cooldown,
            "last_update": self._last_update.isoformat(),
        }
