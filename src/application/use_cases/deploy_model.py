"""Deploy model use case."""

import os

from loguru import logger

from src.application.dtos.ml_dtos import DeployModelRequest, DeployModelResponse
from src.application.ports.ml_ports import IModelDeployer
from src.domain.entities.ml_model import DeploymentStrategy, ModelStatus
from src.domain.repositories.ml_repositories import IMLModelRepository


class DeployModelUseCase:
    """Use case for deploying a trained model.

    This orchestrates the deployment process:
    1. Validate the model exists and is ready for deployment
    2. Deploy using the specified strategy (canary, blue-green, etc.)
    3. Update model entity with deployment information
    4. Handle rollback if deployment fails
    """

    def __init__(
        self,
        model_repository: IMLModelRepository,
        model_deployer: IModelDeployer,
    ) -> None:
        """Initialize the use case with required dependencies.

        Args:
            model_repository: Repository for ML models
            model_deployer: Service for deploying models
        """
        self.model_repository = model_repository
        self.model_deployer = model_deployer

    async def execute(self, request: DeployModelRequest) -> DeployModelResponse:
        """Execute the deployment use case.

        Args:
            request: Deployment request with model ID and strategy

        Returns:
            Deployment response with status and endpoint

        Raises:
            ValueError: If model doesn't exist or isn't ready for deployment
        """
        logger.info(
            f"Starting deployment for model {request.model_id} with strategy {request.strategy}"
        )

        # 1. Get the model
        model = await self.model_repository.get_by_id(request.model_id)
        if not model:
            raise ValueError(f"Model {request.model_id} not found")

        # 2. Validate model is ready for deployment
        if model.status != ModelStatus.VALIDATED:
            raise ValueError(
                f"Model {model.name} is not ready for deployment "
                f"(status: {model.status.value}). Model must be validated first."
            )

        if not model.model_path:
            raise ValueError(f"Model {model.name} has no model path set")

        logger.info(f"Deploying model {model.name} v{model.version} from path: {model.model_path}")

        # 3. Map strategy string to enum
        try:
            strategy_enum = DeploymentStrategy(request.strategy.lower())
        except ValueError:
            raise ValueError(
                f"Invalid deployment strategy: {request.strategy}. "
                f"Must be one of: {[s.value for s in DeploymentStrategy]}"
            )

        # 4. For canary deployment, check if another model is already deployed
        if strategy_enum == DeploymentStrategy.CANARY:
            deployed_models = await self.model_repository.get_deployed_models()
            if not deployed_models:
                logger.warning(
                    "No existing deployed model found. "
                    "Deploying with 100% traffic instead of canary."
                )
                request.traffic_percentage = 100

        # 5. Start deployment
        try:
            model.deploy(
                strategy=strategy_enum,
                traffic_percentage=request.traffic_percentage,
            )
            await self.model_repository.save(model)

            # Call infrastructure to deploy
            endpoint_url = await self.model_deployer.deploy(
                model_path=model.model_path,
                model_id=model.id,
                strategy=request.strategy,
                traffic_percentage=request.traffic_percentage,
            )

            logger.info(f"Model deployed successfully at: {endpoint_url}")

        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            # Model status is already set to DEPLOYING, we should mark it as failed
            model._status = ModelStatus.FAILED
            model.add_tag("deployment_error", str(e))
            await self.model_repository.save(model)
            raise

        # 6. Complete deployment
        try:
            model.complete_deployment()
            await self.model_repository.save(model)

            logger.info(
                f"Model {model.name} v{model.version} deployed with "
                f"{model.traffic_percentage}% traffic"
            )

            # 7. If auto-promote and canary, schedule traffic increase
            if request.auto_promote and strategy_enum == DeploymentStrategy.CANARY:
                logger.info("Auto-promote enabled. Traffic will be increased gradually.")
                # TODO: Schedule traffic increase (could be done with Prefect workflow)

        except Exception as e:
            logger.error(f"Failed to complete deployment: {e}")
            # Attempt rollback
            try:
                await self.model_deployer.rollback(model.id)
                logger.info("Deployment rolled back successfully")
            except Exception as rollback_error:
                logger.error(f"Rollback also failed: {rollback_error}")
            raise

        # 8. Return response
        return DeployModelResponse(
            model_id=model.id,
            deployment_status=model.status.value,
            traffic_percentage=model.traffic_percentage,
            endpoint_url=endpoint_url,
        )
