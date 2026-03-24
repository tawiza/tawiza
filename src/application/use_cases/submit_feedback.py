"""Use case for submitting and managing user feedback."""

from typing import Any
from uuid import UUID

from src.domain.entities.feedback import Feedback, FeedbackType
from src.domain.repositories.ml_repositories import IFeedbackRepository, IMLModelRepository


class SubmitFeedbackUseCase:
    """Use case for submitting user feedback on model predictions."""

    def __init__(
        self,
        feedback_repository: IFeedbackRepository,
        model_repository: IMLModelRepository,
    ) -> None:
        """Initialize the use case.

        Args:
            feedback_repository: Feedback repository
            model_repository: Model repository
        """
        self._feedback_repository = feedback_repository
        self._model_repository = model_repository

    async def execute(
        self,
        model_id: UUID,
        feedback_type: FeedbackType,
        prediction_id: str | None = None,
        rating: int | None = None,
        comment: str | None = None,
        correction: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        input_data: dict[str, Any] | None = None,
        output_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Feedback:
        """Submit user feedback.

        Args:
            model_id: ID of the model
            feedback_type: Type of feedback
            prediction_id: Optional prediction ID
            rating: Rating (1-5) for RATING type
            comment: Optional user comment
            correction: Corrected output
            user_id: Optional user ID
            session_id: Optional session ID
            input_data: Input data for the prediction
            output_data: Model output
            metadata: Additional metadata

        Returns:
            Created feedback entity

        Raises:
            ValueError: If model not found or validation fails
        """
        # Verify model exists
        model = await self._model_repository.get_by_id(model_id)
        if not model:
            raise ValueError(f"Model with ID {model_id} not found")

        # Create feedback entity
        feedback = Feedback(
            model_id=model_id,
            feedback_type=feedback_type,
            prediction_id=prediction_id,
            rating=rating,
            comment=comment,
            correction=correction,
            user_id=user_id,
            session_id=session_id,
            input_data=input_data,
            output_data=output_data,
            metadata=metadata,
        )

        # Save feedback
        saved_feedback = await self._feedback_repository.save(feedback)

        return saved_feedback


class GetFeedbackStatisticsUseCase:
    """Use case for retrieving feedback statistics."""

    def __init__(
        self,
        feedback_repository: IFeedbackRepository,
        model_repository: IMLModelRepository,
    ) -> None:
        """Initialize the use case.

        Args:
            feedback_repository: Feedback repository
            model_repository: Model repository
        """
        self._feedback_repository = feedback_repository
        self._model_repository = model_repository

    async def execute(self, model_id: UUID) -> dict[str, Any]:
        """Get feedback statistics for a model.

        Args:
            model_id: Model ID

        Returns:
            Dictionary with feedback statistics

        Raises:
            ValueError: If model not found
        """
        # Verify model exists
        model = await self._model_repository.get_by_id(model_id)
        if not model:
            raise ValueError(f"Model with ID {model_id} not found")

        # Get statistics
        stats = await self._feedback_repository.get_feedback_statistics(model_id)

        return {
            "model_id": str(model_id),
            "model_name": model.name,
            "model_version": model.version,
            "statistics": stats,
        }


class GetNegativeFeedbackUseCase:
    """Use case for retrieving negative feedback to identify issues."""

    def __init__(
        self,
        feedback_repository: IFeedbackRepository,
    ) -> None:
        """Initialize the use case.

        Args:
            feedback_repository: Feedback repository
        """
        self._feedback_repository = feedback_repository

    async def execute(
        self,
        model_id: UUID | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Feedback]:
        """Get negative feedback.

        Args:
            model_id: Optional model ID to filter by
            skip: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            List of negative feedback
        """
        feedbacks = await self._feedback_repository.get_negative_feedback(
            model_id=model_id,
            skip=skip,
            limit=limit,
        )

        return feedbacks


class ReviewFeedbackUseCase:
    """Use case for reviewing and actioning feedback."""

    def __init__(
        self,
        feedback_repository: IFeedbackRepository,
    ) -> None:
        """Initialize the use case.

        Args:
            feedback_repository: Feedback repository
        """
        self._feedback_repository = feedback_repository

    async def mark_reviewed(self, feedback_id: UUID) -> Feedback:
        """Mark feedback as reviewed.

        Args:
            feedback_id: Feedback ID

        Returns:
            Updated feedback

        Raises:
            ValueError: If feedback not found
        """
        feedback = await self._feedback_repository.get_by_id(feedback_id)
        if not feedback:
            raise ValueError(f"Feedback with ID {feedback_id} not found")

        feedback.mark_reviewed()
        return await self._feedback_repository.save(feedback)

    async def mark_actioned(self, feedback_id: UUID) -> Feedback:
        """Mark feedback as actioned.

        Args:
            feedback_id: Feedback ID

        Returns:
            Updated feedback

        Raises:
            ValueError: If feedback not found
        """
        feedback = await self._feedback_repository.get_by_id(feedback_id)
        if not feedback:
            raise ValueError(f"Feedback with ID {feedback_id} not found")

        feedback.mark_actioned()
        return await self._feedback_repository.save(feedback)

    async def dismiss(self, feedback_id: UUID) -> Feedback:
        """Dismiss feedback.

        Args:
            feedback_id: Feedback ID

        Returns:
            Updated feedback

        Raises:
            ValueError: If feedback not found
        """
        feedback = await self._feedback_repository.get_by_id(feedback_id)
        if not feedback:
            raise ValueError(f"Feedback with ID {feedback_id} not found")

        feedback.dismiss()
        return await self._feedback_repository.save(feedback)
