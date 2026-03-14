"""Dependency Injection Container.

This module provides a DI container for managing dependencies and their lifecycle.
It uses the dependency-injector library pattern but implemented manually for clarity.
"""

from src.application.ports.ml_ports import (
    IDataAnnotator,
    IDataDriftDetector,
    IMLExperimentTracker,
    IModelDeployer,
    IModelInference,
    IModelTrainer,
    IWorkflowOrchestrator,
)
from src.application.use_cases.deploy_model import DeployModelUseCase
from src.application.use_cases.predict import PredictUseCase
from src.application.use_cases.train_model import TrainModelUseCase
from src.domain.repositories.ml_repositories import (
    IDatasetRepository,
    IDriftReportRepository,
    IFeedbackRepository,
    IMLModelRepository,
    IRetrainingJobRepository,
    ITrainingJobRepository,
)
from src.infrastructure.caching import (
    CachedDatasetRepository,
    CachedMLModelRepository,
)
from src.infrastructure.config.settings import Settings, get_settings
from src.infrastructure.ml.deployment.model_deployer import ModelDeployer
from src.infrastructure.ml.evidently.evidently_adapter import EvidentlyAdapter
from src.infrastructure.ml.label_studio.label_studio_adapter import LabelStudioAdapter
from src.infrastructure.ml.llama_factory.llama_factory_adapter import LlamaFactoryAdapter
from src.infrastructure.ml.mlflow.mlflow_adapter import MLflowAdapter
from src.infrastructure.ml.prefect.prefect_adapter import PrefectAdapter
from src.infrastructure.ml.vllm.vllm_adapter import VLLMAdapter
from src.infrastructure.persistence.repositories.dataset_repository import (
    SQLAlchemyDatasetRepository,
)
from src.infrastructure.persistence.repositories.drift_report_repository import (
    SQLAlchemyDriftReportRepository,
)
from src.infrastructure.persistence.repositories.feedback_repository import (
    SQLAlchemyFeedbackRepository,
)
from src.infrastructure.persistence.repositories.ml_model_repository import (
    SQLAlchemyMLModelRepository,
)
from src.infrastructure.persistence.repositories.retraining_job_repository import (
    SQLAlchemyRetrainingJobRepository,
)
from src.infrastructure.persistence.repositories.training_job_repository import (
    SQLAlchemyTrainingJobRepository,
)


class Container:
    """Dependency Injection Container.

    Manages the lifecycle and dependencies of all application components.
    Uses lazy initialization for better performance.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the container.

        Args:
            settings: Application settings (uses default if not provided)
        """
        self._settings = settings or get_settings()

        # Lazy-loaded singletons
        self._mlflow_adapter: MLflowAdapter | None = None
        self._vllm_adapter: VLLMAdapter | None = None

        # Repositories (will be initialized when DB is ready)
        self._model_repository: IMLModelRepository | None = None
        self._dataset_repository: IDatasetRepository | None = None
        self._training_job_repository: ITrainingJobRepository | None = None
        self._feedback_repository: IFeedbackRepository | None = None
        self._drift_report_repository: IDriftReportRepository | None = None
        self._retraining_job_repository: IRetrainingJobRepository | None = None

        # Other adapters
        self._model_trainer: IModelTrainer | None = None
        self._model_deployer: IModelDeployer | None = None
        self._data_annotator: IDataAnnotator | None = None
        self._data_drift_detector: IDataDriftDetector | None = None
        self._workflow_orchestrator: IWorkflowOrchestrator | None = None

    @property
    def settings(self) -> Settings:
        """Get application settings."""
        return self._settings

    # Infrastructure Adapters

    def mlflow_adapter(self) -> IMLExperimentTracker:
        """Get MLflow adapter (singleton).

        Returns:
            MLflow experiment tracker adapter
        """
        if self._mlflow_adapter is None:
            self._mlflow_adapter = MLflowAdapter(
                tracking_uri=self._settings.mlflow.tracking_uri,
                experiment_name=self._settings.mlflow.experiment_name,
            )
        return self._mlflow_adapter

    def vllm_adapter(self) -> IModelInference:
        """Get vLLM adapter (singleton).

        Returns:
            vLLM inference adapter
        """
        if self._vllm_adapter is None:
            self._vllm_adapter = VLLMAdapter(
                base_url=self._settings.vllm.url,
                api_key=self._settings.vllm.api_key,
                timeout=self._settings.vllm.timeout,
            )
        return self._vllm_adapter

    def model_trainer(self) -> IModelTrainer:
        """Get model trainer adapter.

        Returns:
            Model trainer (LLaMA-Factory adapter)
        """
        if self._model_trainer is None:
            self._model_trainer = LlamaFactoryAdapter(
                llamafactory_path=self._settings.training.llamafactory_path,
                venv_path=self._settings.training.venv_path,
                use_cli=self._settings.training.use_cli,
                mlflow_tracking_uri=self._settings.mlflow.tracking_uri,
            )
        return self._model_trainer

    def model_deployer(self) -> IModelDeployer:
        """Get model deployer.

        Returns:
            Model deployer
        """
        if self._model_deployer is None:
            self._model_deployer = ModelDeployer(
                kubernetes_namespace=self._settings.deployment.kubernetes_namespace,
                registry_url=self._settings.deployment.registry_url,
                default_replicas=self._settings.deployment.default_replicas,
                auto_scaling_enabled=self._settings.deployment.auto_scaling_enabled,
            )
        return self._model_deployer

    def data_annotator(self) -> IDataAnnotator:
        """Get data annotator adapter.

        Returns:
            Data annotator (Label Studio adapter)
        """
        if self._data_annotator is None:
            self._data_annotator = LabelStudioAdapter(
                url=self._settings.label_studio.url,
                api_key=self._settings.label_studio.api_key,
            )
        return self._data_annotator

    def data_drift_detector(self) -> IDataDriftDetector:
        """Get data drift detector.

        Returns:
            Data drift detector (Evidently adapter)
        """
        if self._data_drift_detector is None:
            self._data_drift_detector = EvidentlyAdapter(
                drift_share_threshold=0.5,
            )
        return self._data_drift_detector

    def workflow_orchestrator(self) -> IWorkflowOrchestrator | None:
        """Get workflow orchestrator.

        Returns:
            Workflow orchestrator (Prefect adapter) or None if Prefect not available

        Note:
            Returns None if Prefect is not installed, which is acceptable
            for simple deployments that don't need workflow orchestration.
        """
        if self._workflow_orchestrator is None:
            try:
                self._workflow_orchestrator = PrefectAdapter(
                    work_pool="default",
                )
            except ImportError:
                # Prefect not installed - optional dependency
                return None
        return self._workflow_orchestrator

    # Repositories

    def model_repository(self) -> IMLModelRepository:
        """Get ML model repository.

        Returns:
            Model repository

        Raises:
            RuntimeError: If repository not initialized
        """
        if self._model_repository is None:
            raise RuntimeError(
                "Model repository not initialized. "
                "Call container.init_repositories() first or implement SQLAlchemy repository."
            )
        return self._model_repository

    def dataset_repository(self) -> IDatasetRepository:
        """Get dataset repository.

        Returns:
            Dataset repository

        Raises:
            RuntimeError: If repository not initialized
        """
        if self._dataset_repository is None:
            raise RuntimeError(
                "Dataset repository not initialized. "
                "Call container.init_repositories() first or implement SQLAlchemy repository."
            )
        return self._dataset_repository

    def training_job_repository(self) -> ITrainingJobRepository:
        """Get training job repository.

        Returns:
            Training job repository

        Raises:
            RuntimeError: If repository not initialized
        """
        if self._training_job_repository is None:
            raise RuntimeError(
                "Training job repository not initialized. "
                "Call container.init_repositories() first or implement SQLAlchemy repository."
            )
        return self._training_job_repository

    def feedback_repository(self) -> IFeedbackRepository:
        """Get feedback repository.

        Returns:
            Feedback repository

        Raises:
            RuntimeError: If repository not initialized
        """
        if self._feedback_repository is None:
            raise RuntimeError(
                "Feedback repository not initialized. "
                "Call container.init_repositories() first or implement SQLAlchemy repository."
            )
        return self._feedback_repository

    def drift_report_repository(self) -> IDriftReportRepository:
        """Get drift report repository.

        Returns:
            Drift report repository

        Raises:
            RuntimeError: If repository not initialized
        """
        if self._drift_report_repository is None:
            raise RuntimeError(
                "Drift report repository not initialized. "
                "Call container.init_repositories() first or implement SQLAlchemy repository."
            )
        return self._drift_report_repository

    def retraining_job_repository(self) -> IRetrainingJobRepository:
        """Get retraining job repository.

        Returns:
            Retraining job repository

        Raises:
            RuntimeError: If repository not initialized
        """
        if self._retraining_job_repository is None:
            raise RuntimeError(
                "Retraining job repository not initialized. "
                "Call container.init_repositories() first or implement SQLAlchemy repository."
            )
        return self._retraining_job_repository

    def set_repositories(
        self,
        model_repo: IMLModelRepository,
        dataset_repo: IDatasetRepository,
        training_job_repo: ITrainingJobRepository,
    ) -> None:
        """Set repositories (used during initialization).

        Args:
            model_repo: Model repository
            dataset_repo: Dataset repository
            training_job_repo: Training job repository
        """
        self._model_repository = model_repo
        self._dataset_repository = dataset_repo
        self._training_job_repository = training_job_repo

    # Use Cases

    def train_model_use_case(self) -> TrainModelUseCase:
        """Get TrainModelUseCase instance.

        Returns:
            Configured TrainModelUseCase

        Raises:
            RuntimeError: If dependencies not available
        """
        try:
            return TrainModelUseCase(
                model_repository=self.model_repository(),
                dataset_repository=self.dataset_repository(),
                training_job_repository=self.training_job_repository(),
                model_trainer=self.model_trainer(),
                experiment_tracker=self.mlflow_adapter(),
                workflow_orchestrator=self.workflow_orchestrator(),
            )
        except (RuntimeError, NotImplementedError) as e:
            raise RuntimeError(
                f"Cannot create TrainModelUseCase: {e}. "
                "Ensure all dependencies are implemented and initialized."
            ) from e

    def deploy_model_use_case(self) -> DeployModelUseCase:
        """Get DeployModelUseCase instance.

        Returns:
            Configured DeployModelUseCase

        Raises:
            RuntimeError: If dependencies not available
        """
        try:
            return DeployModelUseCase(
                model_repository=self.model_repository(),
                model_deployer=self.model_deployer(),
            )
        except (RuntimeError, NotImplementedError) as e:
            raise RuntimeError(
                f"Cannot create DeployModelUseCase: {e}. "
                "Ensure all dependencies are implemented and initialized."
            ) from e

    def predict_use_case(self) -> PredictUseCase:
        """Get PredictUseCase instance.

        Returns:
            Configured PredictUseCase

        Raises:
            RuntimeError: If dependencies not available
        """
        try:
            return PredictUseCase(
                model_repository=self.model_repository(),
                model_inference=self.vllm_adapter(),
            )
        except RuntimeError as e:
            raise RuntimeError(
                f"Cannot create PredictUseCase: {e}. Ensure model repository is initialized."
            ) from e

    # Lifecycle management

    async def init(self) -> None:
        """Initialize the container and all dependencies.

        This should be called during application startup.
        """
        from loguru import logger

        # Setup ROCm environment if needed
        self._settings.setup_rocm_env()

        # Initialize repositories (database must be initialized first in main.py)
        from src.infrastructure.persistence.database import get_session

        session_factory = get_session

        # Create raw repositories
        raw_model_repo = SQLAlchemyMLModelRepository(session_factory)
        raw_dataset_repo = SQLAlchemyDatasetRepository(session_factory)

        # Wrap with caching layer for performance
        # Cache TTL: 5 minutes for models (frequently accessed, slow changing)
        self._model_repository = CachedMLModelRepository(
            raw_model_repo,
            cache_ttl=300,
            cache_prefix="ml_models",
        )
        logger.info("✓ ML Model repository initialized with caching")

        # Dataset repository with caching
        self._dataset_repository = CachedDatasetRepository(
            raw_dataset_repo,
            cache_ttl=300,
            cache_prefix="datasets",
        )
        logger.info("✓ Dataset repository initialized with caching")

        # Other repositories (no caching - less frequently accessed)
        self._training_job_repository = SQLAlchemyTrainingJobRepository(session_factory)
        self._feedback_repository = SQLAlchemyFeedbackRepository(session_factory)
        self._drift_report_repository = SQLAlchemyDriftReportRepository(session_factory)
        self._retraining_job_repository = SQLAlchemyRetrainingJobRepository(session_factory)

    async def shutdown(self) -> None:
        """Shutdown the container and cleanup resources.

        This should be called during application shutdown.
        """
        from loguru import logger

        from src.infrastructure.persistence.database import close_engine

        logger.info("Shutting down DI container...")

        # Close database engine
        try:
            await close_engine()
            logger.debug("Database engine closed")
        except Exception as e:
            logger.warning(f"Error closing database engine: {e}")

        # Close adapters with cleanup methods
        if self._vllm_adapter is not None:
            try:
                await self._vllm_adapter.close()
                logger.debug("vLLM adapter closed")
            except Exception as e:
                logger.warning(f"Error closing vLLM adapter: {e}")

        logger.info("DI container shutdown complete")


# Global container instance
_container: Container | None = None


def get_container() -> Container:
    """Get the global container instance.

    Returns:
        Container: Global DI container

    Example:
        >>> from src.infrastructure.di.container import get_container
        >>> container = get_container()
        >>> use_case = container.predict_use_case()
    """
    global _container
    if _container is None:
        _container = Container()
    return _container


def set_container(container: Container) -> None:
    """Set the global container instance.

    Args:
        container: Container instance to use

    Note:
        Useful for testing with mock dependencies
    """
    global _container
    _container = container
