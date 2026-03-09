"""Feedback entity for collecting user feedback on model predictions."""

from enum import Enum, StrEnum
from typing import Any
from uuid import UUID

from .base import Entity


class FeedbackType(StrEnum):
    """Type of feedback."""

    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    RATING = "rating"  # 1-5 stars
    CORRECTION = "correction"  # User provides correct output
    BUG_REPORT = "bug_report"
    IMPLICIT = "implicit"  # Auto-logged prediction (no explicit user action)


class FeedbackStatus(StrEnum):
    """Status of feedback."""

    PENDING = "pending"  # Collected but not reviewed
    REVIEWED = "reviewed"  # Reviewed by team
    ACTIONED = "actioned"  # Used for retraining or fixes
    DISMISSED = "dismissed"  # Not relevant/spam


class Feedback(Entity):
    """Feedback entity for collecting and managing user feedback.

    This entity captures user feedback on model predictions to enable:
    - Continuous model improvement
    - Detection of model drift
    - Identification of edge cases
    - User satisfaction tracking
    """

    def __init__(
        self,
        model_id: UUID,
        feedback_type: FeedbackType,
        id: UUID | None = None,
        prediction_id: str | None = None,
        rating: int | None = None,
        comment: str | None = None,
        correction: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        input_data: dict[str, Any] | None = None,
        output_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Initialize feedback entity.

        Args:
            model_id: ID of the model that generated the prediction
            feedback_type: Type of feedback
            id: Optional entity ID
            prediction_id: Optional prediction identifier
            rating: Rating (1-5) for RATING type
            comment: Optional user comment
            correction: Corrected output provided by user
            user_id: Optional user identifier
            session_id: Optional session identifier
            input_data: Input data that was used for prediction
            output_data: Model's output/prediction
            metadata: Additional metadata (context, timestamp, etc.)
        """
        super().__init__(id)
        self._model_id = model_id
        self._feedback_type = feedback_type
        self._prediction_id = prediction_id
        self._rating = rating
        self._comment = comment
        self._correction = correction
        self._user_id = user_id
        self._session_id = session_id
        self._input_data = input_data or {}
        self._output_data = output_data or {}
        self._metadata = metadata or {}
        self._status = FeedbackStatus.PENDING

        # Validate rating if type is RATING
        if feedback_type == FeedbackType.RATING and rating is not None:
            if not 1 <= rating <= 5:
                raise ValueError("Rating must be between 1 and 5")

    @property
    def model_id(self) -> UUID:
        """Get the model ID."""
        return self._model_id

    @property
    def feedback_type(self) -> FeedbackType:
        """Get the feedback type."""
        return self._feedback_type

    @property
    def prediction_id(self) -> str | None:
        """Get the prediction ID."""
        return self._prediction_id

    @property
    def rating(self) -> int | None:
        """Get the rating."""
        return self._rating

    @property
    def comment(self) -> str | None:
        """Get the user comment."""
        return self._comment

    @property
    def correction(self) -> str | None:
        """Get the correction provided by user."""
        return self._correction

    @property
    def user_id(self) -> str | None:
        """Get the user ID."""
        return self._user_id

    @property
    def session_id(self) -> str | None:
        """Get the session ID."""
        return self._session_id

    @property
    def input_data(self) -> dict[str, Any]:
        """Get the input data."""
        return self._input_data.copy()

    @property
    def output_data(self) -> dict[str, Any]:
        """Get the output data."""
        return self._output_data.copy()

    @property
    def metadata(self) -> dict[str, Any]:
        """Get the metadata."""
        return self._metadata.copy()

    @property
    def status(self) -> FeedbackStatus:
        """Get the feedback status."""
        return self._status

    def mark_reviewed(self) -> None:
        """Mark feedback as reviewed."""
        self._status = FeedbackStatus.REVIEWED
        self._touch()

    def mark_actioned(self) -> None:
        """Mark feedback as actioned (used for improvement)."""
        self._status = FeedbackStatus.ACTIONED
        self._touch()

    def dismiss(self) -> None:
        """Dismiss feedback as not relevant."""
        self._status = FeedbackStatus.DISMISSED
        self._touch()

    def add_comment(self, comment: str) -> None:
        """Add or update comment.

        Args:
            comment: User comment
        """
        self._comment = comment
        self._touch()

    def update_metadata(self, metadata: dict[str, Any]) -> None:
        """Update metadata.

        Args:
            metadata: New metadata to merge
        """
        self._metadata.update(metadata)
        self._touch()

    def is_negative(self) -> bool:
        """Check if feedback is negative.

        Returns:
            True if feedback indicates a problem
        """
        if self._feedback_type == FeedbackType.THUMBS_DOWN:
            return True
        if self._feedback_type == FeedbackType.RATING and self._rating is not None:
            return self._rating <= 2
        return self._feedback_type in [FeedbackType.CORRECTION, FeedbackType.BUG_REPORT]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        base = super().to_dict()
        base.update(
            {
                "model_id": str(self._model_id),
                "feedback_type": self._feedback_type.value,
                "prediction_id": self._prediction_id,
                "rating": self._rating,
                "comment": self._comment,
                "correction": self._correction,
                "user_id": self._user_id,
                "session_id": self._session_id,
                "input_data": self._input_data,
                "output_data": self._output_data,
                "metadata": self._metadata,
                "status": self._status.value,
                "is_negative": self.is_negative(),
            }
        )
        return base
