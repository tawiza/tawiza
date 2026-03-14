"""SQLAlchemy implementation of feedback repository."""

from collections.abc import Callable
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.feedback import Feedback, FeedbackStatus, FeedbackType
from src.domain.repositories.ml_repositories import IFeedbackRepository
from src.infrastructure.persistence.models.feedback_model import FeedbackDB


class SQLAlchemyFeedbackRepository(IFeedbackRepository):
    """SQLAlchemy implementation of the feedback repository."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        """Initialize the repository.

        Args:
            session_factory: Factory function to create database sessions
        """
        self._session_factory = session_factory

    def _to_domain(self, db_model: FeedbackDB) -> Feedback:
        """Convert database model to domain entity.

        Args:
            db_model: Database model

        Returns:
            Domain entity
        """
        feedback = Feedback(
            id=db_model.id,
            model_id=db_model.model_id,
            feedback_type=FeedbackType(db_model.feedback_type),
            prediction_id=db_model.prediction_id,
            rating=db_model.rating,
            comment=db_model.comment,
            correction=db_model.correction,
            user_id=db_model.user_id,
            session_id=db_model.session_id,
            input_data=db_model.input_data or {},
            output_data=db_model.output_data or {},
            metadata=db_model.feedback_metadata or {},
        )

        # Set status
        if db_model.status == FeedbackStatus.REVIEWED.value:
            feedback.mark_reviewed()
        elif db_model.status == FeedbackStatus.ACTIONED.value:
            feedback.mark_actioned()
        elif db_model.status == FeedbackStatus.DISMISSED.value:
            feedback.dismiss()

        return feedback

    def _to_db_model(self, feedback: Feedback) -> FeedbackDB:
        """Convert domain entity to database model.

        Args:
            feedback: Domain entity

        Returns:
            Database model
        """
        return FeedbackDB(
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

    async def save(self, feedback: Feedback) -> Feedback:
        """Save a feedback entity.

        Args:
            feedback: Feedback to save

        Returns:
            Saved feedback
        """
        async with self._session_factory() as session:
            db_model = self._to_db_model(feedback)
            session.add(db_model)
            await session.commit()
            await session.refresh(db_model)
            return self._to_domain(db_model)

    async def get_by_id(self, feedback_id: UUID) -> Feedback | None:
        """Get feedback by ID.

        Args:
            feedback_id: Feedback ID

        Returns:
            Feedback if found, None otherwise
        """
        async with self._session_factory() as session:
            query = select(FeedbackDB).where(FeedbackDB.id == feedback_id)
            result = await session.execute(query)
            db_model = result.scalar_one_or_none()
            return self._to_domain(db_model) if db_model else None

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Feedback]:
        """Get all feedback with pagination.

        Args:
            skip: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            List of feedback
        """
        async with self._session_factory() as session:
            query = (
                select(FeedbackDB).order_by(FeedbackDB.created_at.desc()).offset(skip).limit(limit)
            )
            result = await session.execute(query)
            db_models = result.scalars().all()
            return [self._to_domain(db_model) for db_model in db_models]

    # Alias for backwards compatibility
    async def list_all(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Feedback]:
        """List all feedback with pagination (alias for get_all)."""
        return await self.get_all(skip=skip, limit=limit)

    async def delete(self, feedback_id: UUID) -> bool:
        """Delete feedback by ID.

        Args:
            feedback_id: Feedback ID

        Returns:
            True if deleted, False if not found
        """
        async with self._session_factory() as session:
            query = select(FeedbackDB).where(FeedbackDB.id == feedback_id)
            result = await session.execute(query)
            db_model = result.scalar_one_or_none()

            if db_model:
                await session.delete(db_model)
                await session.commit()
                return True
            return False

    async def get_by_model_id(
        self,
        model_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Feedback]:
        """Get feedback by model ID.

        Args:
            model_id: Model ID
            skip: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            List of feedback for the model
        """
        async with self._session_factory() as session:
            query = (
                select(FeedbackDB)
                .where(FeedbackDB.model_id == model_id)
                .order_by(FeedbackDB.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            result = await session.execute(query)
            db_models = result.scalars().all()
            return [self._to_domain(db_model) for db_model in db_models]

    async def get_by_status(
        self,
        status: FeedbackStatus,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Feedback]:
        """Get feedback by status.

        Args:
            status: Feedback status
            skip: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            List of feedback with the status
        """
        async with self._session_factory() as session:
            query = (
                select(FeedbackDB)
                .where(FeedbackDB.status == status.value)
                .order_by(FeedbackDB.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            result = await session.execute(query)
            db_models = result.scalars().all()
            return [self._to_domain(db_model) for db_model in db_models]

    async def get_by_type(
        self,
        feedback_type: FeedbackType,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Feedback]:
        """Get feedback by type.

        Args:
            feedback_type: Feedback type
            skip: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            List of feedback with the type
        """
        async with self._session_factory() as session:
            query = (
                select(FeedbackDB)
                .where(FeedbackDB.feedback_type == feedback_type.value)
                .order_by(FeedbackDB.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            result = await session.execute(query)
            db_models = result.scalars().all()
            return [self._to_domain(db_model) for db_model in db_models]

    async def get_negative_feedback(
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
        async with self._session_factory() as session:
            # Build query for negative feedback
            query = select(FeedbackDB).where(
                (FeedbackDB.feedback_type == FeedbackType.THUMBS_DOWN.value)
                | (FeedbackDB.feedback_type == FeedbackType.BUG_REPORT.value)
                | (FeedbackDB.feedback_type == FeedbackType.CORRECTION.value)
                | (
                    (FeedbackDB.feedback_type == FeedbackType.RATING.value)
                    & (FeedbackDB.rating <= 2)
                )
            )

            if model_id:
                query = query.where(FeedbackDB.model_id == model_id)

            query = query.order_by(FeedbackDB.created_at.desc()).offset(skip).limit(limit)

            result = await session.execute(query)
            db_models = result.scalars().all()
            return [self._to_domain(db_model) for db_model in db_models]

    async def get_by_prediction_id(
        self,
        prediction_id: str,
    ) -> list[Feedback]:
        """Get feedback by prediction ID.

        Args:
            prediction_id: Prediction ID

        Returns:
            List of feedback for the prediction
        """
        async with self._session_factory() as session:
            query = (
                select(FeedbackDB)
                .where(FeedbackDB.prediction_id == prediction_id)
                .order_by(FeedbackDB.created_at.desc())
            )
            result = await session.execute(query)
            db_models = result.scalars().all()
            return [self._to_domain(db_model) for db_model in db_models]

    async def get_feedback_statistics(
        self,
        model_id: UUID,
    ) -> dict:
        """Get feedback statistics for a model.

        Args:
            model_id: Model ID

        Returns:
            Dictionary with statistics
        """
        async with self._session_factory() as session:
            # Total count
            total_query = select(func.count(FeedbackDB.id)).where(FeedbackDB.model_id == model_id)
            total_result = await session.execute(total_query)
            total_count = total_result.scalar() or 0

            # Count by type
            type_query = (
                select(FeedbackDB.feedback_type, func.count(FeedbackDB.id))
                .where(FeedbackDB.model_id == model_id)
                .group_by(FeedbackDB.feedback_type)
            )
            type_result = await session.execute(type_query)
            counts_by_type = {row[0]: row[1] for row in type_result}

            # Average rating
            rating_query = select(func.avg(FeedbackDB.rating)).where(
                (FeedbackDB.model_id == model_id)
                & (FeedbackDB.feedback_type == FeedbackType.RATING.value)
            )
            rating_result = await session.execute(rating_query)
            avg_rating = rating_result.scalar()

            # Negative feedback count
            negative_query = select(func.count(FeedbackDB.id)).where(
                (FeedbackDB.model_id == model_id)
                & (
                    (FeedbackDB.feedback_type == FeedbackType.THUMBS_DOWN.value)
                    | (FeedbackDB.feedback_type == FeedbackType.BUG_REPORT.value)
                    | (FeedbackDB.feedback_type == FeedbackType.CORRECTION.value)
                    | (
                        (FeedbackDB.feedback_type == FeedbackType.RATING.value)
                        & (FeedbackDB.rating <= 2)
                    )
                )
            )
            negative_result = await session.execute(negative_query)
            negative_count = negative_result.scalar() or 0

            return {
                "total_count": total_count,
                "counts_by_type": counts_by_type,
                "average_rating": float(avg_rating) if avg_rating else None,
                "negative_count": negative_count,
                "negative_percentage": (
                    (negative_count / total_count * 100) if total_count > 0 else 0
                ),
            }

    async def exists(self, entity_id: UUID) -> bool:
        """Check if feedback exists.

        Args:
            entity_id: Feedback ID

        Returns:
            True if exists, False otherwise
        """
        async with self._session_factory() as session:
            query = select(func.count(FeedbackDB.id)).where(FeedbackDB.id == entity_id)
            result = await session.execute(query)
            count = result.scalar() or 0
            return count > 0

    async def count(self) -> int:
        """Count total number of feedback entries.

        Returns:
            Total count
        """
        async with self._session_factory() as session:
            query = select(func.count(FeedbackDB.id))
            result = await session.execute(query)
            return result.scalar() or 0
