"""Tests for train model use case.

This module tests:
- TrainModelUseCase
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.dtos.ml_dtos import TrainModelRequest, TrainModelResponse
from src.application.use_cases.train_model import TrainModelUseCase


class TestTrainModelUseCase:
    """Test suite for TrainModelUseCase."""

    @pytest.fixture
    def mock_model_repository(self):
        """Create mock model repository."""
        repo = AsyncMock()
        repo.get_by_name_and_version = AsyncMock()
        repo.save = AsyncMock()
        return repo

    @pytest.fixture
    def mock_dataset_repository(self):
        """Create mock dataset repository."""
        repo = AsyncMock()
        repo.get_by_id = AsyncMock()
        return repo

    @pytest.fixture
    def mock_training_job_repository(self):
        """Create mock training job repository."""
        repo = AsyncMock()
        repo.save = AsyncMock()
        return repo

    @pytest.fixture
    def mock_model_trainer(self):
        """Create mock model trainer."""
        trainer = AsyncMock()
        trainer.train = AsyncMock()
        return trainer

    @pytest.fixture
    def mock_experiment_tracker(self):
        """Create mock experiment tracker."""
        tracker = AsyncMock()
        tracker.log_parameters = AsyncMock()
        return tracker

    @pytest.fixture
    def mock_workflow_orchestrator(self):
        """Create mock workflow orchestrator."""
        orchestrator = AsyncMock()
        orchestrator.trigger_training_workflow = AsyncMock()
        return orchestrator

    @pytest.fixture
    def use_case(
        self,
        mock_model_repository,
        mock_dataset_repository,
        mock_training_job_repository,
        mock_model_trainer,
        mock_experiment_tracker,
    ):
        """Create use case with mocks."""
        return TrainModelUseCase(
            model_repository=mock_model_repository,
            dataset_repository=mock_dataset_repository,
            training_job_repository=mock_training_job_repository,
            model_trainer=mock_model_trainer,
            experiment_tracker=mock_experiment_tracker,
            workflow_orchestrator=None,
        )

    @pytest.fixture
    def use_case_with_orchestrator(
        self,
        mock_model_repository,
        mock_dataset_repository,
        mock_training_job_repository,
        mock_model_trainer,
        mock_experiment_tracker,
        mock_workflow_orchestrator,
    ):
        """Create use case with workflow orchestrator."""
        return TrainModelUseCase(
            model_repository=mock_model_repository,
            dataset_repository=mock_dataset_repository,
            training_job_repository=mock_training_job_repository,
            model_trainer=mock_model_trainer,
            experiment_tracker=mock_experiment_tracker,
            workflow_orchestrator=mock_workflow_orchestrator,
        )

    @pytest.fixture
    def ready_dataset(self):
        """Create a ready mock dataset."""
        dataset = MagicMock()
        dataset.id = uuid4()
        dataset.name = "test-dataset"
        dataset.is_ready = True
        dataset.status = MagicMock()
        dataset.status.value = "ready"
        dataset.storage_path = "/data/datasets/test"
        dataset.metadata = MagicMock()
        dataset.metadata.size = 1000
        return dataset

    @pytest.fixture
    def not_ready_dataset(self):
        """Create a not ready mock dataset."""
        dataset = MagicMock()
        dataset.id = uuid4()
        dataset.name = "test-dataset"
        dataset.is_ready = False
        dataset.status = MagicMock()
        dataset.status.value = "processing"
        return dataset

    @pytest.fixture
    def train_request(self, ready_dataset):
        """Create a training request."""
        return TrainModelRequest(
            name="my-model",
            version="1.0",
            base_model="qwen2.5-coder-7b",
            dataset_id=ready_dataset.id,
            description="Test model",
            batch_size=16,
            learning_rate=1e-4,
            num_epochs=3,
            max_seq_length=2048,
            lora_rank=8,
            lora_alpha=16,
            use_rlhf=False,
        )

    @pytest.mark.asyncio
    async def test_train_model_success(
        self,
        use_case,
        mock_model_repository,
        mock_dataset_repository,
        mock_training_job_repository,
        mock_model_trainer,
        mock_experiment_tracker,
        ready_dataset,
        train_request,
    ):
        """Should train model successfully."""
        mock_dataset_repository.get_by_id.return_value = ready_dataset
        mock_model_repository.get_by_name_and_version.return_value = None

        # Make save return the model/job passed in
        async def save_model(model):
            return model

        async def save_job(job):
            return job

        mock_model_repository.save.side_effect = save_model
        mock_training_job_repository.save.side_effect = save_job
        mock_model_trainer.train.return_value = "mlflow-run-123"

        result = await use_case.execute(train_request)

        assert isinstance(result, TrainModelResponse)
        assert result.mlflow_run_id == "mlflow-run-123"
        mock_dataset_repository.get_by_id.assert_called_once_with(train_request.dataset_id)
        mock_model_trainer.train.assert_called_once()

    @pytest.mark.asyncio
    async def test_train_model_dataset_not_found(
        self, use_case, mock_dataset_repository, train_request
    ):
        """Should raise error when dataset not found."""
        mock_dataset_repository.get_by_id.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await use_case.execute(train_request)

    @pytest.mark.asyncio
    async def test_train_model_dataset_not_ready(
        self, use_case, mock_dataset_repository, not_ready_dataset
    ):
        """Should raise error when dataset is not ready."""
        mock_dataset_repository.get_by_id.return_value = not_ready_dataset

        request = TrainModelRequest(
            name="my-model",
            version="1.0",
            base_model="qwen2.5-coder-7b",
            dataset_id=not_ready_dataset.id,
        )

        with pytest.raises(ValueError, match="not ready"):
            await use_case.execute(request)

    @pytest.mark.asyncio
    async def test_train_model_already_exists(
        self, use_case, mock_model_repository, mock_dataset_repository, ready_dataset, train_request
    ):
        """Should raise error when model version already exists."""
        mock_dataset_repository.get_by_id.return_value = ready_dataset

        existing_model = MagicMock()
        existing_model.id = uuid4()
        mock_model_repository.get_by_name_and_version.return_value = existing_model

        with pytest.raises(ValueError, match="already exists"):
            await use_case.execute(train_request)

    @pytest.mark.asyncio
    async def test_train_model_logs_parameters(
        self,
        use_case,
        mock_model_repository,
        mock_dataset_repository,
        mock_training_job_repository,
        mock_model_trainer,
        mock_experiment_tracker,
        ready_dataset,
        train_request,
    ):
        """Should log parameters to experiment tracker."""
        mock_dataset_repository.get_by_id.return_value = ready_dataset
        mock_model_repository.get_by_name_and_version.return_value = None

        async def save_model(model):
            return model

        mock_model_repository.save.side_effect = save_model
        mock_training_job_repository.save.side_effect = save_model
        mock_model_trainer.train.return_value = "mlflow-run-123"

        await use_case.execute(train_request)

        mock_experiment_tracker.log_parameters.assert_called_once()
        call_args = mock_experiment_tracker.log_parameters.call_args
        assert call_args.kwargs["run_id"] == "mlflow-run-123"
        assert "batch_size" in call_args.kwargs["parameters"]

    @pytest.mark.asyncio
    async def test_train_model_training_failure(
        self,
        use_case,
        mock_model_repository,
        mock_dataset_repository,
        mock_training_job_repository,
        mock_model_trainer,
        ready_dataset,
        train_request,
    ):
        """Should handle training failure and update status."""
        mock_dataset_repository.get_by_id.return_value = ready_dataset
        mock_model_repository.get_by_name_and_version.return_value = None

        async def save_model(model):
            return model

        mock_model_repository.save.side_effect = save_model
        mock_training_job_repository.save.side_effect = save_model
        mock_model_trainer.train.side_effect = Exception("Training failed")

        with pytest.raises(Exception, match="Training failed"):
            await use_case.execute(train_request)

        # Verify entities were updated with failure status
        # (save called multiple times for updates)
        assert mock_model_repository.save.call_count >= 1
        assert mock_training_job_repository.save.call_count >= 1

    @pytest.mark.asyncio
    async def test_train_model_with_orchestrator(
        self,
        use_case_with_orchestrator,
        mock_model_repository,
        mock_dataset_repository,
        mock_training_job_repository,
        mock_model_trainer,
        mock_experiment_tracker,
        mock_workflow_orchestrator,
        ready_dataset,
        train_request,
    ):
        """Should use workflow orchestrator when available."""
        mock_dataset_repository.get_by_id.return_value = ready_dataset
        mock_model_repository.get_by_name_and_version.return_value = None

        async def save_model(model):
            return model

        mock_model_repository.save.side_effect = save_model
        mock_training_job_repository.save.side_effect = save_model
        mock_workflow_orchestrator.trigger_training_workflow.return_value = "prefect-run-456"
        mock_model_trainer.train.return_value = "mlflow-run-123"

        result = await use_case_with_orchestrator.execute(train_request)

        mock_workflow_orchestrator.trigger_training_workflow.assert_called_once()
        assert result.mlflow_run_id == "mlflow-run-123"

    @pytest.mark.asyncio
    async def test_train_model_orchestrator_failure(
        self,
        use_case_with_orchestrator,
        mock_model_repository,
        mock_dataset_repository,
        mock_training_job_repository,
        mock_workflow_orchestrator,
        ready_dataset,
        train_request,
    ):
        """Should handle workflow orchestrator failure."""
        mock_dataset_repository.get_by_id.return_value = ready_dataset
        mock_model_repository.get_by_name_and_version.return_value = None

        async def save_model(model):
            return model

        mock_model_repository.save.side_effect = save_model
        mock_training_job_repository.save.side_effect = save_model
        mock_workflow_orchestrator.trigger_training_workflow.side_effect = Exception(
            "Prefect error"
        )

        with pytest.raises(Exception, match="Prefect error"):
            await use_case_with_orchestrator.execute(train_request)

    @pytest.mark.asyncio
    async def test_train_model_hyperparameters_passed_correctly(
        self,
        use_case,
        mock_model_repository,
        mock_dataset_repository,
        mock_training_job_repository,
        mock_model_trainer,
        mock_experiment_tracker,
        ready_dataset,
    ):
        """Should pass hyperparameters correctly to trainer."""
        mock_dataset_repository.get_by_id.return_value = ready_dataset
        mock_model_repository.get_by_name_and_version.return_value = None

        async def save_model(model):
            return model

        mock_model_repository.save.side_effect = save_model
        mock_training_job_repository.save.side_effect = save_model
        mock_model_trainer.train.return_value = "mlflow-run-123"

        request = TrainModelRequest(
            name="my-model",
            version="1.0",
            base_model="llama3.2",
            dataset_id=ready_dataset.id,
            batch_size=32,
            learning_rate=5e-5,
            num_epochs=5,
            max_seq_length=4096,
            lora_rank=16,
            lora_alpha=32,
        )

        await use_case.execute(request)

        call_args = mock_model_trainer.train.call_args
        assert call_args.kwargs["hyperparameters"]["batch_size"] == 32
        assert call_args.kwargs["hyperparameters"]["learning_rate"] == 5e-5
        assert call_args.kwargs["hyperparameters"]["num_epochs"] == 5
        assert call_args.kwargs["hyperparameters"]["lora_rank"] == 16
