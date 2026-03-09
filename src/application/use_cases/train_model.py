"""Train model use case."""

from uuid import uuid4

from loguru import logger

from src.application.dtos.ml_dtos import TrainModelRequest, TrainModelResponse
from src.application.ports.ml_ports import (
    IMLExperimentTracker,
    IModelTrainer,
    IWorkflowOrchestrator,
)
from src.domain.entities.ml_model import MLModel, ModelStatus
from src.domain.entities.training_job import TrainingConfig, TrainingJob, TrainingTrigger
from src.domain.repositories.ml_repositories import (
    IDatasetRepository,
    IMLModelRepository,
    ITrainingJobRepository,
)


class TrainModelUseCase:
    """Use case for training a machine learning model.

    This orchestrates the entire training process:
    1. Validate the dataset exists and is ready
    2. Create model and training job entities
    3. Start the training workflow
    4. Track progress with MLflow
    5. Update entities based on training results

    This is the application layer in hexagonal architecture.
    """

    def __init__(
        self,
        model_repository: IMLModelRepository,
        dataset_repository: IDatasetRepository,
        training_job_repository: ITrainingJobRepository,
        model_trainer: IModelTrainer,
        experiment_tracker: IMLExperimentTracker,
        workflow_orchestrator: IWorkflowOrchestrator | None = None,
    ) -> None:
        """Initialize the use case with required dependencies.

        Args:
            model_repository: Repository for ML models
            dataset_repository: Repository for datasets
            training_job_repository: Repository for training jobs
            model_trainer: Service for training models
            experiment_tracker: Service for tracking experiments
            workflow_orchestrator: Optional service for orchestrating workflows
        """
        self.model_repository = model_repository
        self.dataset_repository = dataset_repository
        self.training_job_repository = training_job_repository
        self.model_trainer = model_trainer
        self.experiment_tracker = experiment_tracker
        self.workflow_orchestrator = workflow_orchestrator

    async def execute(self, request: TrainModelRequest) -> TrainModelResponse:
        """Execute the training use case.

        Args:
            request: Training request with all parameters

        Returns:
            Training response with job and model IDs

        Raises:
            ValueError: If dataset doesn't exist or isn't ready
        """
        logger.info(f"Starting training for model {request.name} v{request.version}")

        # 1. Validate dataset
        dataset = await self.dataset_repository.get_by_id(request.dataset_id)
        if not dataset:
            raise ValueError(f"Dataset {request.dataset_id} not found")

        if not dataset.is_ready:
            raise ValueError(
                f"Dataset {dataset.name} is not ready (status: {dataset.status.value})"
            )

        logger.info(f"Using dataset: {dataset.name} ({dataset.metadata.size} samples)")

        # 2. Check if model with same name/version exists
        existing_model = await self.model_repository.get_by_name_and_version(
            request.name, request.version
        )
        if existing_model:
            raise ValueError(
                f"Model {request.name} v{request.version} already exists with ID {existing_model.id}"
            )

        # 3. Create model entity
        model = MLModel(
            id=uuid4(),
            name=request.name,
            version=request.version,
            base_model=request.base_model,
            description=request.description,
            status=ModelStatus.DRAFT,
        )

        # 4. Create training config
        training_config = TrainingConfig(
            base_model=request.base_model,
            dataset_id=request.dataset_id,
            batch_size=request.batch_size,
            learning_rate=request.learning_rate,
            num_epochs=request.num_epochs,
            max_seq_length=request.max_seq_length,
            lora_rank=request.lora_rank,
            lora_alpha=request.lora_alpha,
            use_rlhf=request.use_rlhf,
        )

        # 5. Create training job entity
        training_job = TrainingJob(
            id=uuid4(),
            name=f"train_{request.name}_{request.version}",
            trigger=TrainingTrigger.MANUAL,
        )
        training_job.configure(config=training_config)

        # 6. Save entities
        model = await self.model_repository.save(model)
        training_job = await self.training_job_repository.save(training_job)

        logger.info(f"Created model {model.id} and training job {training_job.id}")

        # 7. Start training workflow (if orchestrator available)
        mlflow_run_id: str | None = None
        prefect_flow_run_id: str | None = None

        if self.workflow_orchestrator:
            try:
                # Use workflow orchestrator (Prefect)
                workflow_params = {
                    "model_id": str(model.id),
                    "training_job_id": str(training_job.id),
                    "dataset_path": dataset.storage_path,
                    "config": training_config.__dict__,
                }
                prefect_flow_run_id = await self.workflow_orchestrator.trigger_training_workflow(
                    training_job_id=training_job.id,
                    parameters=workflow_params,
                )
                logger.info(f"Started Prefect workflow: {prefect_flow_run_id}")
            except Exception as e:
                logger.error(f"Failed to start workflow: {e}")
                training_job.fail(str(e))
                await self.training_job_repository.save(training_job)
                raise

        # 8. Start training directly
        try:
            # Start the training process
            hyperparameters = {
                "batch_size": request.batch_size,
                "learning_rate": request.learning_rate,
                "num_epochs": request.num_epochs,
                "max_seq_length": request.max_seq_length,
                "lora_rank": request.lora_rank,
                "lora_alpha": request.lora_alpha,
            }

            # Log parameters to experiment tracker
            mlflow_run_id = await self.model_trainer.train(
                model_name=model.name,
                base_model=request.base_model,
                dataset_path=dataset.storage_path,
                output_dir=f"/models/{model.id}",
                hyperparameters=hyperparameters,
            )

            # Update model and training job with run IDs
            model.start_training(mlflow_run_id=mlflow_run_id)
            training_job.start(
                mlflow_run_id=mlflow_run_id,
                prefect_flow_run_id=prefect_flow_run_id,
            )

            # Save updated entities
            await self.model_repository.save(model)
            await self.training_job_repository.save(training_job)

            logger.info(f"Training started with MLflow run ID: {mlflow_run_id}")

            # Log training parameters to MLflow
            await self.experiment_tracker.log_parameters(
                run_id=mlflow_run_id,
                parameters={
                    "model_name": model.name,
                    "model_version": model.version,
                    "base_model": request.base_model,
                    "dataset_id": str(request.dataset_id),
                    "dataset_size": dataset.metadata.size,
                    **hyperparameters,
                },
            )

        except Exception as e:
            logger.error(f"Failed to start training: {e}")
            model._status = ModelStatus.FAILED
            training_job.fail(str(e))
            await self.model_repository.save(model)
            await self.training_job_repository.save(training_job)
            raise

        # 9. Return response
        return TrainModelResponse(
            training_job_id=training_job.id,
            model_id=model.id,
            status=training_job.status.value,
            mlflow_run_id=mlflow_run_id,
        )
