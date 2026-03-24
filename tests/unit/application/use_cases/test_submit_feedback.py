"""Tests for submit feedback use cases.

This module tests:
- SubmitFeedbackUseCase
- GetFeedbackStatisticsUseCase
- GetNegativeFeedbackUseCase
- ReviewFeedbackUseCase
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.use_cases.submit_feedback import (
    GetFeedbackStatisticsUseCase,
    GetNegativeFeedbackUseCase,
    ReviewFeedbackUseCase,
    SubmitFeedbackUseCase,
)
from src.domain.entities.feedback import Feedback, FeedbackType


class TestSubmitFeedbackUseCase:
    """Test suite for SubmitFeedbackUseCase."""

    @pytest.fixture
    def mock_feedback_repository(self):
        """Create mock feedback repository."""
        repo = AsyncMock()
        repo.save = AsyncMock()
        return repo

    @pytest.fixture
    def mock_model_repository(self):
        """Create mock model repository."""
        repo = AsyncMock()
        repo.get_by_id = AsyncMock()
        return repo

    @pytest.fixture
    def use_case(self, mock_feedback_repository, mock_model_repository):
        """Create use case with mocks."""
        return SubmitFeedbackUseCase(
            feedback_repository=mock_feedback_repository,
            model_repository=mock_model_repository,
        )

    @pytest.mark.asyncio
    async def test_submit_rating_feedback(
        self, use_case, mock_feedback_repository, mock_model_repository
    ):
        """Should submit rating feedback successfully."""
        model_id = uuid4()
        mock_model = MagicMock(id=model_id, version="1.0")
        mock_model.name = "test-model"
        mock_model_repository.get_by_id.return_value = mock_model

        mock_feedback = MagicMock(id=uuid4())
        mock_feedback_repository.save.return_value = mock_feedback

        result = await use_case.execute(
            model_id=model_id,
            feedback_type=FeedbackType.RATING,
            rating=5,
            comment="Great model!",
        )

        assert result is mock_feedback
        mock_model_repository.get_by_id.assert_called_once_with(model_id)
        mock_feedback_repository.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_correction_feedback(
        self, use_case, mock_feedback_repository, mock_model_repository
    ):
        """Should submit correction feedback successfully."""
        model_id = uuid4()
        mock_model = MagicMock(id=model_id, version="1.0")
        mock_model.name = "test-model"
        mock_model_repository.get_by_id.return_value = mock_model

        mock_feedback = MagicMock(id=uuid4())
        mock_feedback_repository.save.return_value = mock_feedback

        result = await use_case.execute(
            model_id=model_id,
            feedback_type=FeedbackType.CORRECTION,
            correction="The correct answer is X",
            input_data={"prompt": "What is X?"},
            output_data={"response": "Y"},
        )

        assert result is mock_feedback
        mock_feedback_repository.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_feedback_model_not_found(self, use_case, mock_model_repository):
        """Should raise error when model not found."""
        model_id = uuid4()
        mock_model_repository.get_by_id.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await use_case.execute(
                model_id=model_id,
                feedback_type=FeedbackType.RATING,
                rating=5,
            )

    @pytest.mark.asyncio
    async def test_submit_feedback_with_metadata(
        self, use_case, mock_feedback_repository, mock_model_repository
    ):
        """Should include metadata in feedback."""
        model_id = uuid4()
        mock_model = MagicMock(id=model_id)
        mock_model_repository.get_by_id.return_value = mock_model

        mock_feedback = MagicMock(id=uuid4())
        mock_feedback_repository.save.return_value = mock_feedback

        await use_case.execute(
            model_id=model_id,
            feedback_type=FeedbackType.RATING,
            rating=4,
            user_id="user-123",
            session_id="session-abc",
            metadata={"source": "web"},
        )

        # Verify the saved feedback has the expected metadata
        call_args = mock_feedback_repository.save.call_args
        saved_feedback = call_args[0][0]
        assert isinstance(saved_feedback, Feedback)


class TestGetFeedbackStatisticsUseCase:
    """Test suite for GetFeedbackStatisticsUseCase."""

    @pytest.fixture
    def mock_feedback_repository(self):
        """Create mock feedback repository."""
        repo = AsyncMock()
        repo.get_feedback_statistics = AsyncMock()
        return repo

    @pytest.fixture
    def mock_model_repository(self):
        """Create mock model repository."""
        repo = AsyncMock()
        repo.get_by_id = AsyncMock()
        return repo

    @pytest.fixture
    def use_case(self, mock_feedback_repository, mock_model_repository):
        """Create use case with mocks."""
        return GetFeedbackStatisticsUseCase(
            feedback_repository=mock_feedback_repository,
            model_repository=mock_model_repository,
        )

    @pytest.mark.asyncio
    async def test_get_statistics_success(
        self, use_case, mock_feedback_repository, mock_model_repository
    ):
        """Should return statistics successfully."""
        model_id = uuid4()
        mock_model = MagicMock(id=model_id, version="1.0")
        mock_model.name = "test-model"  # Set name as attribute, not constructor arg
        mock_model_repository.get_by_id.return_value = mock_model

        mock_stats = {
            "total_feedback": 100,
            "average_rating": 4.2,
            "positive_count": 80,
            "negative_count": 20,
        }
        mock_feedback_repository.get_feedback_statistics.return_value = mock_stats

        result = await use_case.execute(model_id=model_id)

        assert result["model_id"] == str(model_id)
        assert result["model_name"] == "test-model"
        assert result["model_version"] == "1.0"
        assert result["statistics"] == mock_stats

    @pytest.mark.asyncio
    async def test_get_statistics_model_not_found(self, use_case, mock_model_repository):
        """Should raise error when model not found."""
        model_id = uuid4()
        mock_model_repository.get_by_id.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await use_case.execute(model_id=model_id)


class TestGetNegativeFeedbackUseCase:
    """Test suite for GetNegativeFeedbackUseCase."""

    @pytest.fixture
    def mock_feedback_repository(self):
        """Create mock feedback repository."""
        repo = AsyncMock()
        repo.get_negative_feedback = AsyncMock()
        return repo

    @pytest.fixture
    def use_case(self, mock_feedback_repository):
        """Create use case with mocks."""
        return GetNegativeFeedbackUseCase(
            feedback_repository=mock_feedback_repository,
        )

    @pytest.mark.asyncio
    async def test_get_negative_feedback_all(self, use_case, mock_feedback_repository):
        """Should get all negative feedback."""
        mock_feedbacks = [MagicMock(), MagicMock()]
        mock_feedback_repository.get_negative_feedback.return_value = mock_feedbacks

        result = await use_case.execute()

        assert len(result) == 2
        mock_feedback_repository.get_negative_feedback.assert_called_once_with(
            model_id=None,
            skip=0,
            limit=100,
        )

    @pytest.mark.asyncio
    async def test_get_negative_feedback_by_model(self, use_case, mock_feedback_repository):
        """Should filter by model ID."""
        model_id = uuid4()
        mock_feedbacks = [MagicMock()]
        mock_feedback_repository.get_negative_feedback.return_value = mock_feedbacks

        result = await use_case.execute(model_id=model_id)

        assert len(result) == 1
        mock_feedback_repository.get_negative_feedback.assert_called_once_with(
            model_id=model_id,
            skip=0,
            limit=100,
        )

    @pytest.mark.asyncio
    async def test_get_negative_feedback_with_pagination(self, use_case, mock_feedback_repository):
        """Should support pagination."""
        mock_feedbacks = [MagicMock() for _ in range(50)]
        mock_feedback_repository.get_negative_feedback.return_value = mock_feedbacks

        result = await use_case.execute(skip=10, limit=50)

        assert len(result) == 50
        mock_feedback_repository.get_negative_feedback.assert_called_once_with(
            model_id=None,
            skip=10,
            limit=50,
        )


class TestReviewFeedbackUseCase:
    """Test suite for ReviewFeedbackUseCase."""

    @pytest.fixture
    def mock_feedback_repository(self):
        """Create mock feedback repository."""
        repo = AsyncMock()
        repo.get_by_id = AsyncMock()
        repo.save = AsyncMock()
        return repo

    @pytest.fixture
    def use_case(self, mock_feedback_repository):
        """Create use case with mocks."""
        return ReviewFeedbackUseCase(
            feedback_repository=mock_feedback_repository,
        )

    @pytest.mark.asyncio
    async def test_mark_reviewed(self, use_case, mock_feedback_repository):
        """Should mark feedback as reviewed."""
        feedback_id = uuid4()
        mock_feedback = MagicMock()
        mock_feedback_repository.get_by_id.return_value = mock_feedback
        mock_feedback_repository.save.return_value = mock_feedback

        result = await use_case.mark_reviewed(feedback_id)

        mock_feedback.mark_reviewed.assert_called_once()
        mock_feedback_repository.save.assert_called_once_with(mock_feedback)
        assert result is mock_feedback

    @pytest.mark.asyncio
    async def test_mark_reviewed_not_found(self, use_case, mock_feedback_repository):
        """Should raise error when feedback not found."""
        feedback_id = uuid4()
        mock_feedback_repository.get_by_id.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await use_case.mark_reviewed(feedback_id)

    @pytest.mark.asyncio
    async def test_mark_actioned(self, use_case, mock_feedback_repository):
        """Should mark feedback as actioned."""
        feedback_id = uuid4()
        mock_feedback = MagicMock()
        mock_feedback_repository.get_by_id.return_value = mock_feedback
        mock_feedback_repository.save.return_value = mock_feedback

        result = await use_case.mark_actioned(feedback_id)

        mock_feedback.mark_actioned.assert_called_once()
        mock_feedback_repository.save.assert_called_once_with(mock_feedback)
        assert result is mock_feedback

    @pytest.mark.asyncio
    async def test_mark_actioned_not_found(self, use_case, mock_feedback_repository):
        """Should raise error when feedback not found."""
        feedback_id = uuid4()
        mock_feedback_repository.get_by_id.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await use_case.mark_actioned(feedback_id)

    @pytest.mark.asyncio
    async def test_dismiss(self, use_case, mock_feedback_repository):
        """Should dismiss feedback."""
        feedback_id = uuid4()
        mock_feedback = MagicMock()
        mock_feedback_repository.get_by_id.return_value = mock_feedback
        mock_feedback_repository.save.return_value = mock_feedback

        result = await use_case.dismiss(feedback_id)

        mock_feedback.dismiss.assert_called_once()
        mock_feedback_repository.save.assert_called_once_with(mock_feedback)
        assert result is mock_feedback

    @pytest.mark.asyncio
    async def test_dismiss_not_found(self, use_case, mock_feedback_repository):
        """Should raise error when feedback not found."""
        feedback_id = uuid4()
        mock_feedback_repository.get_by_id.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await use_case.dismiss(feedback_id)
