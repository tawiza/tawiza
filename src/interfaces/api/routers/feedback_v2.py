"""Feedback API router v2 - Complete implementation with database integration.

This router provides a simplified feedback API that integrates with the
existing Feedback domain entity and SQLAlchemy repository.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.feedback import Feedback, FeedbackStatus, FeedbackType
from src.infrastructure.persistence.database import get_db_session
from src.infrastructure.persistence.models.feedback_model import FeedbackDB

router = APIRouter()


# Pydantic models
class SubmitFeedbackRequest(BaseModel):
    """Request model for submitting feedback."""

    prediction_id: UUID = Field(..., description="ID of the prediction being rated")
    model_id: UUID | None = Field(None, description="ID of the model (optional)")
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 (bad) to 5 (excellent)")
    comment: str | None = Field(None, max_length=1000, description="Optional feedback comment")
    is_correct: bool | None = Field(None, description="Was the prediction correct?")
    expected_output: str | None = Field(None, description="What was the expected output?")
    user_id: str | None = Field(None, description="Optional user identifier")


class FeedbackResponse(BaseModel):
    """Response model for feedback submission."""

    feedback_id: UUID
    prediction_id: UUID
    rating: int
    status: str = "received"
    message: str = "Feedback recorded successfully"


class FeedbackItem(BaseModel):
    """Model for a feedback item."""

    id: UUID
    prediction_id: str | None
    model_id: UUID | None
    rating: int | None
    comment: str | None
    is_correct: bool | None
    expected_output: str | None
    feedback_type: str
    status: str
    created_at: datetime
    user_id: str | None


class FeedbackStats(BaseModel):
    """Feedback statistics."""

    total_feedback: int
    average_rating: float | None
    rating_distribution: dict
    correct_predictions: int
    incorrect_predictions: int
    needs_review: int


def _feedback_db_to_item(db_model: FeedbackDB) -> FeedbackItem:
    """Convert database model to API response model."""
    # Extract is_correct and expected_output from metadata if stored
    metadata = db_model.feedback_metadata or {}

    return FeedbackItem(
        id=db_model.id,
        prediction_id=db_model.prediction_id,
        model_id=db_model.model_id,
        rating=db_model.rating,
        comment=db_model.comment,
        is_correct=metadata.get("is_correct"),
        expected_output=db_model.correction,
        feedback_type=db_model.feedback_type,
        status=db_model.status,
        created_at=db_model.created_at,
        user_id=db_model.user_id,
    )


@router.post(
    "",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit feedback",
    description="Submit feedback for a prediction to improve the model",
)
async def submit_feedback(
    request: SubmitFeedbackRequest,
    session: AsyncSession = Depends(get_db_session),
) -> FeedbackResponse:
    """
    Submit feedback for a prediction.

    This feedback is used for:
    - Active learning: Identifying cases for re-annotation
    - Model evaluation: Tracking prediction accuracy
    - Continuous improvement: Triggering retraining when needed

    Args:
        request: Feedback submission request
        session: Database session

    Returns:
        Feedback confirmation with ID
    """
    try:
        # Determine feedback type based on rating and is_correct
        if request.is_correct is False or request.expected_output:
            feedback_type = FeedbackType.CORRECTION
        elif request.rating <= 2:
            feedback_type = FeedbackType.THUMBS_DOWN
        elif request.rating >= 4:
            feedback_type = FeedbackType.THUMBS_UP
        else:
            feedback_type = FeedbackType.RATING

        # Create domain entity
        # Use a placeholder model_id if not provided (will be resolved later)
        model_id = request.model_id or UUID("00000000-0000-0000-0000-000000000000")

        feedback = Feedback(
            model_id=model_id,
            feedback_type=feedback_type,
            prediction_id=str(request.prediction_id),
            rating=request.rating,
            comment=request.comment,
            correction=request.expected_output,
            user_id=request.user_id,
            metadata={
                "is_correct": request.is_correct,
                "source": "api_v2",
            },
        )

        # Save to database
        db_model = FeedbackDB(
            id=feedback.id,
            model_id=feedback.model_id,
            prediction_id=feedback.prediction_id,
            feedback_type=feedback.feedback_type.value,
            status=feedback.status.value,
            rating=feedback.rating,
            comment=feedback.comment,
            correction=feedback.correction,
            user_id=feedback.user_id,
            session_id=feedback.session_id,
            input_data=feedback.input_data,
            output_data=feedback.output_data,
            feedback_metadata=feedback.metadata,
            created_at=feedback.created_at,
            updated_at=feedback.updated_at,
        )

        session.add(db_model)
        await session.commit()
        await session.refresh(db_model)

        logger.info(
            f"Feedback {feedback.id} submitted for prediction {request.prediction_id}: "
            f"rating={request.rating}, type={feedback_type.value}"
        )

        # Check if this should trigger re-annotation
        if feedback.is_negative():
            logger.warning(
                f"Prediction {request.prediction_id} needs review "
                f"(rating={request.rating}, correct={request.is_correct})"
            )
            # Future: Create annotation task in Label Studio
            # Future: Check if we should trigger retraining

        return FeedbackResponse(
            feedback_id=feedback.id,
            prediction_id=request.prediction_id,
            rating=request.rating,
            status="received",
            message="Feedback recorded successfully. Thank you for helping improve the model!",
        )

    except Exception as e:
        logger.error(f"Failed to submit feedback: {e}", exc_info=True)
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit feedback: {str(e)}",
        )


@router.get(
    "",
    response_model=list[FeedbackItem],
    summary="List feedback",
    description="List all feedback with pagination",
)
async def list_feedback(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    rating_filter: int | None = Query(None, ge=1, le=5, description="Filter by rating"),
    session: AsyncSession = Depends(get_db_session),
) -> list[FeedbackItem]:
    """
    List feedback with optional filtering.

    Args:
        page: Page number
        page_size: Items per page
        rating_filter: Optional rating filter
        session: Database session

    Returns:
        List of feedback items
    """
    try:
        skip = (page - 1) * page_size

        query = select(FeedbackDB).order_by(FeedbackDB.created_at.desc())

        if rating_filter is not None:
            query = query.where(FeedbackDB.rating == rating_filter)

        query = query.offset(skip).limit(page_size)

        result = await session.execute(query)
        db_models = result.scalars().all()

        logger.info(f"Fetched {len(db_models)} feedback items (page {page})")

        return [_feedback_db_to_item(db_model) for db_model in db_models]

    except Exception as e:
        logger.error(f"Failed to list feedback: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list feedback: {str(e)}",
        )


@router.get(
    "/stats",
    response_model=FeedbackStats,
    summary="Get feedback statistics",
    description="Get aggregated feedback statistics for monitoring",
)
async def get_feedback_stats(
    session: AsyncSession = Depends(get_db_session),
) -> FeedbackStats:
    """
    Get feedback statistics.

    Useful for:
    - Monitoring model performance
    - Identifying when retraining is needed
    - Understanding user satisfaction

    Args:
        session: Database session

    Returns:
        Feedback statistics
    """
    try:
        # Total count
        total_query = select(func.count(FeedbackDB.id))
        total_result = await session.execute(total_query)
        total_count = total_result.scalar() or 0

        # Average rating
        avg_query = select(func.avg(FeedbackDB.rating)).where(FeedbackDB.rating.isnot(None))
        avg_result = await session.execute(avg_query)
        avg_rating = avg_result.scalar()

        # Rating distribution
        rating_distribution = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
        for r in [1, 2, 3, 4, 5]:
            count_query = select(func.count(FeedbackDB.id)).where(FeedbackDB.rating == r)
            count_result = await session.execute(count_query)
            rating_distribution[str(r)] = count_result.scalar() or 0

        # Negative feedback (needs review)
        negative_query = select(func.count(FeedbackDB.id)).where(
            (FeedbackDB.feedback_type == FeedbackType.THUMBS_DOWN.value)
            | (FeedbackDB.feedback_type == FeedbackType.CORRECTION.value)
            | (FeedbackDB.feedback_type == FeedbackType.BUG_REPORT.value)
            | ((FeedbackDB.rating.isnot(None)) & (FeedbackDB.rating <= 2))
        )
        negative_result = await session.execute(negative_query)
        needs_review = negative_result.scalar() or 0

        # Correct/incorrect based on feedback_type
        correct_query = select(func.count(FeedbackDB.id)).where(
            FeedbackDB.feedback_type == FeedbackType.THUMBS_UP.value
        )
        correct_result = await session.execute(correct_query)
        correct_predictions = correct_result.scalar() or 0

        incorrect_query = select(func.count(FeedbackDB.id)).where(
            (FeedbackDB.feedback_type == FeedbackType.THUMBS_DOWN.value)
            | (FeedbackDB.feedback_type == FeedbackType.CORRECTION.value)
        )
        incorrect_result = await session.execute(incorrect_query)
        incorrect_predictions = incorrect_result.scalar() or 0

        logger.info("Retrieved feedback statistics")

        return FeedbackStats(
            total_feedback=total_count,
            average_rating=float(avg_rating) if avg_rating else None,
            rating_distribution=rating_distribution,
            correct_predictions=correct_predictions,
            incorrect_predictions=incorrect_predictions,
            needs_review=needs_review,
        )

    except Exception as e:
        logger.error(f"Failed to get feedback statistics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get feedback statistics: {str(e)}",
        )


@router.get(
    "/{feedback_id}",
    response_model=FeedbackItem,
    summary="Get feedback by ID",
    description="Retrieve a specific feedback item",
)
async def get_feedback(
    feedback_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> FeedbackItem:
    """
    Get a specific feedback item.

    Args:
        feedback_id: Feedback UUID
        session: Database session

    Returns:
        Feedback item

    Raises:
        HTTPException: If feedback not found
    """
    try:
        query = select(FeedbackDB).where(FeedbackDB.id == feedback_id)
        result = await session.execute(query)
        db_model = result.scalar_one_or_none()

        if not db_model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feedback {feedback_id} not found",
            )

        logger.info(f"Retrieved feedback {feedback_id}")
        return _feedback_db_to_item(db_model)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get feedback: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get feedback: {str(e)}",
        )


@router.delete(
    "/{feedback_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete feedback",
    description="Delete a feedback item",
)
async def delete_feedback(
    feedback_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Delete a feedback item.

    Args:
        feedback_id: Feedback UUID
        session: Database session

    Raises:
        HTTPException: If feedback not found
    """
    try:
        query = select(FeedbackDB).where(FeedbackDB.id == feedback_id)
        result = await session.execute(query)
        db_model = result.scalar_one_or_none()

        if not db_model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feedback {feedback_id} not found",
            )

        await session.delete(db_model)
        await session.commit()

        logger.info(f"Deleted feedback {feedback_id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete feedback: {e}", exc_info=True)
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete feedback: {str(e)}",
        )


@router.patch(
    "/{feedback_id}/status",
    response_model=FeedbackItem,
    summary="Update feedback status",
    description="Update the status of a feedback item (reviewed, actioned, dismissed)",
)
async def update_feedback_status(
    feedback_id: UUID,
    new_status: str = Query(..., description="New status: pending, reviewed, actioned, dismissed"),
    session: AsyncSession = Depends(get_db_session),
) -> FeedbackItem:
    """
    Update feedback status.

    Args:
        feedback_id: Feedback UUID
        new_status: New status value
        session: Database session

    Returns:
        Updated feedback item

    Raises:
        HTTPException: If feedback not found or invalid status
    """
    try:
        # Validate status
        try:
            status_enum = FeedbackStatus(new_status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {new_status}. Valid values: {[s.value for s in FeedbackStatus]}",
            )

        query = select(FeedbackDB).where(FeedbackDB.id == feedback_id)
        result = await session.execute(query)
        db_model = result.scalar_one_or_none()

        if not db_model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feedback {feedback_id} not found",
            )

        db_model.status = status_enum.value
        await session.commit()
        await session.refresh(db_model)

        logger.info(f"Updated feedback {feedback_id} status to {new_status}")
        return _feedback_db_to_item(db_model)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update feedback status: {e}", exc_info=True)
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update feedback status: {str(e)}",
        )
