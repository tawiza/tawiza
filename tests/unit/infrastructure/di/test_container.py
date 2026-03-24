"""Tests for Dependency Injection Container."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.infrastructure.config.settings import Settings
from src.infrastructure.di.container import (
    Container,
    get_container,
    set_container,
)


class TestContainer:
    """Test Container class."""

    def setup_method(self):
        """Reset global container before each test."""
        import src.infrastructure.di.container as container_module

        container_module._container = None

    def test_container_initialization(self):
        """Test container initializes with settings."""
        container = Container()

        assert container._settings is not None
        assert isinstance(container._settings, Settings)

    def test_container_with_custom_settings(self):
        """Test container with custom settings."""
        custom_settings = Settings(app_name="TestApp", debug=True)
        container = Container(settings=custom_settings)

        assert container._settings.app_name == "TestApp"
        assert container._settings.debug is True

    def test_lazy_initialization(self):
        """Test that adapters are lazily initialized."""
        container = Container()

        # Adapters should be None before first access
        assert container._mlflow_adapter is None
        assert container._vllm_adapter is None

    def test_mlflow_adapter_lazy_load(self):
        """Test MLflow adapter is lazily loaded."""
        container = Container()

        with patch("src.infrastructure.di.container.MLflowAdapter") as MockAdapter:
            mock_instance = Mock()
            MockAdapter.return_value = mock_instance

            adapter = container.mlflow_adapter()

            MockAdapter.assert_called_once()
            assert adapter == mock_instance

    def test_mlflow_adapter_singleton(self):
        """Test MLflow adapter is a singleton."""
        container = Container()

        with patch("src.infrastructure.di.container.MLflowAdapter") as MockAdapter:
            mock_instance = Mock()
            MockAdapter.return_value = mock_instance

            adapter1 = container.mlflow_adapter()
            adapter2 = container.mlflow_adapter()

            # Should only be created once
            MockAdapter.assert_called_once()
            assert adapter1 is adapter2


class TestGetContainer:
    """Test get_container function."""

    def setup_method(self):
        """Reset global container before each test."""
        import src.infrastructure.di.container as container_module

        container_module._container = None

    def test_get_container_creates_singleton(self):
        """Test get_container creates a singleton."""
        container1 = get_container()
        container2 = get_container()

        assert container1 is container2
        assert isinstance(container1, Container)

    def test_get_container_returns_container(self):
        """Test get_container returns Container instance."""
        container = get_container()

        assert isinstance(container, Container)


class TestSetContainer:
    """Test set_container function."""

    def setup_method(self):
        """Reset global container before each test."""
        import src.infrastructure.di.container as container_module

        container_module._container = None

    def test_set_container_replaces_global(self):
        """Test set_container replaces global container."""
        custom_container = Container(settings=Settings(app_name="CustomApp"))

        set_container(custom_container)
        retrieved = get_container()

        assert retrieved is custom_container
        assert retrieved._settings.app_name == "CustomApp"

    def test_set_container_for_testing(self):
        """Test set_container can be used for mock injection."""
        mock_container = Mock(spec=Container)
        mock_container.mlflow_adapter.return_value = Mock()

        set_container(mock_container)
        container = get_container()

        assert container is mock_container


class TestContainerShutdown:
    """Test Container shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown_calls_close_engine(self):
        """Test shutdown closes database engine."""
        container = Container()

        with patch(
            "src.infrastructure.persistence.database.close_engine", new_callable=AsyncMock
        ) as mock_close:
            await container.shutdown()

            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_handles_errors_gracefully(self):
        """Test shutdown handles errors without raising."""
        container = Container()

        with patch(
            "src.infrastructure.persistence.database.close_engine", new_callable=AsyncMock
        ) as mock_close:
            mock_close.side_effect = Exception("Database error")

            # Should not raise
            await container.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_closes_vllm_adapter(self):
        """Test shutdown closes vLLM adapter if present."""
        container = Container()

        mock_vllm = AsyncMock()
        container._vllm_adapter = mock_vllm

        with patch("src.infrastructure.persistence.database.close_engine", new_callable=AsyncMock):
            await container.shutdown()

            mock_vllm.close.assert_called_once()


class TestContainerUseCases:
    """Test Container use case factories."""

    def test_predict_use_case_creation(self):
        """Test predict use case can be created."""
        container = Container()

        with patch.object(container, "vllm_adapter") as mock_inference:
            with patch.object(container, "model_repository") as mock_repo:
                mock_inference.return_value = Mock()
                mock_repo.return_value = Mock()

                use_case = container.predict_use_case()

                assert use_case is not None

    def test_train_use_case_creation(self):
        """Test train use case can be created."""
        container = Container()

        with patch.object(container, "model_trainer") as mock_trainer:
            with patch.object(container, "mlflow_adapter") as mock_tracker:
                with patch.object(container, "model_repository") as mock_repo:
                    with patch.object(container, "dataset_repository") as mock_dataset:
                        with patch.object(container, "training_job_repository") as mock_job:
                            with patch.object(container, "workflow_orchestrator") as mock_workflow:
                                mock_trainer.return_value = Mock()
                                mock_tracker.return_value = Mock()
                                mock_repo.return_value = Mock()
                                mock_dataset.return_value = Mock()
                                mock_job.return_value = Mock()
                                mock_workflow.return_value = None

                                use_case = container.train_model_use_case()

                                assert use_case is not None


class TestContainerRepositories:
    """Test Container repository access."""

    def test_model_repository_not_initialized(self):
        """Test model_repository raises if not initialized."""
        container = Container()

        with pytest.raises(RuntimeError, match="not initialized"):
            container.model_repository()

    def test_dataset_repository_not_initialized(self):
        """Test dataset_repository raises if not initialized."""
        container = Container()

        with pytest.raises(RuntimeError, match="not initialized"):
            container.dataset_repository()

    @pytest.mark.asyncio
    async def test_init_repositories(self):
        """Test init() initializes all repositories."""
        container = Container()

        with patch("src.infrastructure.persistence.database.get_session") as mock_session:
            mock_session.return_value = Mock()

            await container.init()

            assert container._model_repository is not None
            assert container._dataset_repository is not None
            assert container._training_job_repository is not None
            assert container._feedback_repository is not None


class TestContainerOptionalDependencies:
    """Test Container optional dependencies."""

    def test_workflow_orchestrator_returns_none_when_prefect_not_installed(self):
        """Test workflow_orchestrator returns None when Prefect not installed."""
        container = Container()

        with patch(
            "src.infrastructure.di.container.PrefectAdapter", side_effect=ImportError("prefect")
        ):
            result = container.workflow_orchestrator()

            assert result is None

    def test_data_drift_detector_returns_evidently_adapter(self):
        """Test data_drift_detector returns EvidentlyAdapter."""
        container = Container()

        with patch("src.infrastructure.di.container.EvidentlyAdapter") as MockAdapter:
            mock_instance = Mock()
            MockAdapter.return_value = mock_instance

            result = container.data_drift_detector()

            assert result == mock_instance
            MockAdapter.assert_called_once()
