"""Tests for predict use case.

This module tests:
- PredictUseCase
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.application.dtos.ml_dtos import PredictionRequest, PredictionResponse
from src.application.use_cases.predict import PredictUseCase


class TestPredictUseCase:
    """Test suite for PredictUseCase."""

    @pytest.fixture
    def mock_model_repository(self):
        """Create mock model repository."""
        repo = AsyncMock()
        repo.get_by_id = AsyncMock()
        repo.get_latest_deployed = AsyncMock()
        return repo

    @pytest.fixture
    def mock_model_inference(self):
        """Create mock model inference service."""
        inference = AsyncMock()
        inference.predict = AsyncMock()
        return inference

    @pytest.fixture
    def mock_feedback_repository(self):
        """Create mock feedback repository."""
        repo = AsyncMock()
        repo.create = AsyncMock()
        return repo

    @pytest.fixture
    def use_case(self, mock_model_repository, mock_model_inference, mock_feedback_repository):
        """Create use case with mocks."""
        return PredictUseCase(
            model_repository=mock_model_repository,
            model_inference=mock_model_inference,
            feedback_repository=mock_feedback_repository,
        )

    @pytest.fixture
    def use_case_no_feedback(self, mock_model_repository, mock_model_inference):
        """Create use case without feedback repository."""
        return PredictUseCase(
            model_repository=mock_model_repository,
            model_inference=mock_model_inference,
            feedback_repository=None,
        )

    @pytest.fixture
    def deployed_model(self):
        """Create a deployed mock model."""
        model = MagicMock()
        model.id = uuid4()
        model.name = "test-model"
        model.version = "1.0"
        model.is_deployed = True
        model.status = MagicMock()
        model.status.value = "deployed"
        return model

    @pytest.fixture
    def undeployed_model(self):
        """Create an undeployed mock model."""
        model = MagicMock()
        model.id = uuid4()
        model.name = "test-model"
        model.version = "1.0"
        model.is_deployed = False
        model.status = MagicMock()
        model.status.value = "training"
        return model

    @pytest.mark.asyncio
    async def test_predict_with_specific_model(
        self, use_case, mock_model_repository, mock_model_inference, deployed_model
    ):
        """Should make prediction with specified model."""
        mock_model_repository.get_by_id.return_value = deployed_model
        mock_model_inference.predict.return_value = {"response": "Hello!", "confidence": 0.95}

        request = PredictionRequest(
            input_data={"prompt": "Hello"},
            model_id=deployed_model.id,
        )

        result = await use_case.execute(request)

        assert isinstance(result, PredictionResponse)
        assert result.model_id == deployed_model.id
        assert result.model_version == "1.0"
        assert result.output == {"response": "Hello!", "confidence": 0.95}
        assert result.confidence == 0.95
        mock_model_repository.get_by_id.assert_called_once_with(deployed_model.id)

    @pytest.mark.asyncio
    async def test_predict_with_latest_deployed_model(
        self, use_case, mock_model_repository, mock_model_inference, deployed_model
    ):
        """Should use latest deployed model when model_id not specified."""
        mock_model_repository.get_latest_deployed.return_value = deployed_model
        mock_model_inference.predict.return_value = {"response": "Hi!"}

        request = PredictionRequest(
            input_data={"prompt": "Hello"},
            model_id=None,
        )

        result = await use_case.execute(request)

        assert result.model_id == deployed_model.id
        mock_model_repository.get_latest_deployed.assert_called_once()
        mock_model_repository.get_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_predict_model_not_found(self, use_case, mock_model_repository):
        """Should raise error when model not found."""
        model_id = uuid4()
        mock_model_repository.get_by_id.return_value = None

        request = PredictionRequest(
            input_data={"prompt": "Hello"},
            model_id=model_id,
        )

        with pytest.raises(ValueError, match="not found"):
            await use_case.execute(request)

    @pytest.mark.asyncio
    async def test_predict_model_not_deployed(
        self, use_case, mock_model_repository, undeployed_model
    ):
        """Should raise error when model is not deployed."""
        mock_model_repository.get_by_id.return_value = undeployed_model

        request = PredictionRequest(
            input_data={"prompt": "Hello"},
            model_id=undeployed_model.id,
        )

        with pytest.raises(ValueError, match="not deployed"):
            await use_case.execute(request)

    @pytest.mark.asyncio
    async def test_predict_no_deployed_model_available(self, use_case, mock_model_repository):
        """Should raise error when no deployed model available."""
        mock_model_repository.get_latest_deployed.return_value = None

        request = PredictionRequest(
            input_data={"prompt": "Hello"},
            model_id=None,
        )

        with pytest.raises(ValueError, match="No deployed model available"):
            await use_case.execute(request)

    @pytest.mark.asyncio
    async def test_predict_with_custom_parameters(
        self, use_case, mock_model_repository, mock_model_inference, deployed_model
    ):
        """Should pass custom inference parameters."""
        mock_model_repository.get_by_id.return_value = deployed_model
        mock_model_inference.predict.return_value = {"response": "Custom response"}

        request = PredictionRequest(
            input_data={"prompt": "Hello"},
            model_id=deployed_model.id,
            temperature=0.5,
            max_tokens=256,
            top_p=0.8,
        )

        await use_case.execute(request)

        # Verify inference was called with correct parameters
        mock_model_inference.predict.assert_called_once()
        call_args = mock_model_inference.predict.call_args
        assert call_args.kwargs["parameters"]["temperature"] == 0.5
        assert call_args.kwargs["parameters"]["max_tokens"] == 256
        assert call_args.kwargs["parameters"]["top_p"] == 0.8

    @pytest.mark.asyncio
    async def test_predict_logs_to_feedback_repository(
        self,
        use_case,
        mock_model_repository,
        mock_model_inference,
        mock_feedback_repository,
        deployed_model,
    ):
        """Should log prediction to feedback repository with IMPLICIT type."""
        mock_model_repository.get_by_id.return_value = deployed_model
        mock_model_inference.predict.return_value = {"response": "Hello!"}

        request = PredictionRequest(
            input_data={"prompt": "Hello"},
            model_id=deployed_model.id,
        )

        result = await use_case.execute(request)

        assert result.output == {"response": "Hello!"}
        # Verify feedback was logged with IMPLICIT type
        mock_feedback_repository.create.assert_called_once()
        feedback_arg = mock_feedback_repository.create.call_args[0][0]
        from src.domain.entities.feedback import FeedbackType

        assert feedback_arg.feedback_type == FeedbackType.IMPLICIT

    @pytest.mark.asyncio
    async def test_predict_without_feedback_repository(
        self, use_case_no_feedback, mock_model_repository, mock_model_inference, deployed_model
    ):
        """Should work without feedback repository."""
        mock_model_repository.get_by_id.return_value = deployed_model
        mock_model_inference.predict.return_value = {"response": "Hello!"}

        request = PredictionRequest(
            input_data={"prompt": "Hello"},
            model_id=deployed_model.id,
        )

        result = await use_case_no_feedback.execute(request)

        assert result.output == {"response": "Hello!"}

    @pytest.mark.asyncio
    async def test_predict_feedback_logging_failure_does_not_break_prediction(
        self,
        use_case,
        mock_model_repository,
        mock_model_inference,
        mock_feedback_repository,
        deployed_model,
    ):
        """Should continue if feedback logging fails."""
        mock_model_repository.get_by_id.return_value = deployed_model
        mock_model_inference.predict.return_value = {"response": "Hello!"}
        mock_feedback_repository.create.side_effect = Exception("DB error")

        request = PredictionRequest(
            input_data={"prompt": "Hello"},
            model_id=deployed_model.id,
        )

        # Should not raise even though feedback logging fails
        result = await use_case.execute(request)
        assert result.output == {"response": "Hello!"}

    @pytest.mark.asyncio
    async def test_predict_inference_failure_is_propagated(
        self, use_case, mock_model_repository, mock_model_inference, deployed_model
    ):
        """Should propagate inference failures."""
        mock_model_repository.get_by_id.return_value = deployed_model
        mock_model_inference.predict.side_effect = Exception("Inference error")

        request = PredictionRequest(
            input_data={"prompt": "Hello"},
            model_id=deployed_model.id,
        )

        with pytest.raises(Exception, match="Inference error"):
            await use_case.execute(request)

    @pytest.mark.asyncio
    async def test_predict_response_includes_latency(
        self, use_case, mock_model_repository, mock_model_inference, deployed_model
    ):
        """Should include latency in response."""
        mock_model_repository.get_by_id.return_value = deployed_model
        mock_model_inference.predict.return_value = {"response": "Hello!"}

        request = PredictionRequest(
            input_data={"prompt": "Hello"},
            model_id=deployed_model.id,
        )

        result = await use_case.execute(request)

        assert result.latency_ms is not None
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_predict_response_includes_prediction_id(
        self, use_case, mock_model_repository, mock_model_inference, deployed_model
    ):
        """Should include unique prediction ID in response."""
        mock_model_repository.get_by_id.return_value = deployed_model
        mock_model_inference.predict.return_value = {"response": "Hello!"}

        request = PredictionRequest(
            input_data={"prompt": "Hello"},
            model_id=deployed_model.id,
        )

        result = await use_case.execute(request)

        assert result.prediction_id is not None
