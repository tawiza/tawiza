"""SQLAlchemy implementation of ML Model repository."""

from collections.abc import Callable
from uuid import UUID

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.ml_model import DeploymentStrategy, MLModel, ModelMetrics, ModelStatus
from src.domain.repositories.ml_repositories import IMLModelRepository
from src.infrastructure.persistence.models.ml_model import MLModelDB


class SQLAlchemyMLModelRepository(IMLModelRepository):
    """SQLAlchemy implementation of IMLModelRepository.

    This adapter converts between domain entities (MLModel) and
    persistence models (MLModelDB).
    """

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        """Initialize repository.

        Args:
            session_factory: Factory function to create database sessions
        """
        self._session_factory = session_factory

    def _to_domain(self, db_model: MLModelDB) -> MLModel:
        """Convert database model to domain entity.

        Args:
            db_model: Database model

        Returns:
            Domain entity
        """
        model = MLModel(
            id=db_model.id,
            name=db_model.name,
            version=db_model.version,
            base_model=db_model.base_model,
            description=db_model.description or "",
            status=ModelStatus(db_model.status),
        )

        # Restore internal state
        if db_model.metrics:
            model._metrics = ModelMetrics(**db_model.metrics)

        model._mlflow_run_id = db_model.mlflow_run_id
        model._model_path = db_model.model_path

        if db_model.deployment_strategy:
            model._deployment_strategy = DeploymentStrategy(db_model.deployment_strategy)

        model._traffic_percentage = db_model.traffic_percentage
        model._deployed_at = db_model.deployed_at
        model._retired_at = db_model.retired_at
        model._hyperparameters = db_model.hyperparameters or {}
        model._tags = db_model.tags or {}
        model._created_at = db_model.created_at
        model._updated_at = db_model.updated_at

        return model

    def _to_db(self, model: MLModel) -> MLModelDB:
        """Convert domain entity to database model.

        Args:
            model: Domain entity

        Returns:
            Database model
        """
        return MLModelDB(
            id=model.id,
            name=model.name,
            version=model.version,
            base_model=model.base_model,
            description=model.description,
            status=model.status.value,
            metrics=model.metrics.to_dict() if model.metrics else None,
            mlflow_run_id=model.mlflow_run_id,
            model_path=model.model_path,
            deployment_strategy=model.deployment_strategy.value
            if model.deployment_strategy
            else None,
            traffic_percentage=model.traffic_percentage,
            deployed_at=model._deployed_at,
            retired_at=model._retired_at,
            hyperparameters=model.hyperparameters,
            tags=model._tags,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def save(self, entity: MLModel) -> MLModel:
        """Save a model entity.

        Args:
            entity: Model entity to save

        Returns:
            Saved model entity
        """
        async with self._session_factory() as session:
            # Check if exists
            existing = await session.get(MLModelDB, entity.id)

            if existing:
                # Update existing
                db_model = self._to_db(entity)
                for key, value in db_model.__dict__.items():
                    if not key.startswith("_") and key != "id":
                        setattr(existing, key, value)
            else:
                # Create new
                db_model = self._to_db(entity)
                session.add(db_model)

            await session.commit()
            await session.refresh(existing if existing else db_model)

            logger.debug(f"Saved model {entity.id}")
            return self._to_domain(existing if existing else db_model)

    async def get_by_id(self, entity_id: UUID) -> MLModel | None:
        """Get a model by ID.

        Args:
            entity_id: Model ID

        Returns:
            Model entity or None
        """
        async with self._session_factory() as session:
            db_model = await session.get(MLModelDB, entity_id)
            if db_model:
                return self._to_domain(db_model)
            return None

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[MLModel]:
        """Get all models with pagination.

        Args:
            skip: Number to skip
            limit: Maximum to return

        Returns:
            List of model entities
        """
        async with self._session_factory() as session:
            query = (
                select(MLModelDB).offset(skip).limit(limit).order_by(MLModelDB.created_at.desc())
            )
            result = await session.execute(query)
            db_models = result.scalars().all()
            return [self._to_domain(db_model) for db_model in db_models]

    async def delete(self, entity_id: UUID) -> bool:
        """Delete a model.

        Args:
            entity_id: Model ID

        Returns:
            True if deleted, False if not found
        """
        async with self._session_factory() as session:
            db_model = await session.get(MLModelDB, entity_id)
            if db_model:
                await session.delete(db_model)
                await session.commit()
                logger.info(f"Deleted model {entity_id}")
                return True
            return False

    async def exists(self, entity_id: UUID) -> bool:
        """Check if a model exists.

        Args:
            entity_id: Model ID

        Returns:
            True if exists
        """
        async with self._session_factory() as session:
            db_model = await session.get(MLModelDB, entity_id)
            return db_model is not None

    async def count(self, status: ModelStatus | None = None) -> int:
        """Count total models.

        Args:
            status: Optional status filter

        Returns:
            Total count
        """
        async with self._session_factory() as session:
            query = select(func.count()).select_from(MLModelDB)
            if status:
                query = query.where(MLModelDB.status == status.value)

            result = await session.execute(query)
            return result.scalar() or 0

    async def get_by_name_and_version(
        self,
        name: str,
        version: str,
    ) -> MLModel | None:
        """Get a model by name and version.

        Args:
            name: Model name
            version: Model version

        Returns:
            Model entity or None
        """
        async with self._session_factory() as session:
            query = select(MLModelDB).where(
                MLModelDB.name == name,
                MLModelDB.version == version,
            )
            result = await session.execute(query)
            db_model = result.scalar_one_or_none()

            if db_model:
                return self._to_domain(db_model)
            return None

    async def get_deployed_models(self) -> list[MLModel]:
        """Get all deployed models.

        Returns:
            List of deployed models
        """
        async with self._session_factory() as session:
            query = select(MLModelDB).where(MLModelDB.status == ModelStatus.DEPLOYED.value)
            result = await session.execute(query)
            db_models = result.scalars().all()
            return [self._to_domain(db_model) for db_model in db_models]

    async def get_by_status(
        self,
        status: ModelStatus,
        skip: int = 0,
        limit: int = 100,
    ) -> list[MLModel]:
        """Get models by status.

        Args:
            status: Model status
            skip: Number to skip
            limit: Maximum to return

        Returns:
            List of models
        """
        async with self._session_factory() as session:
            query = (
                select(MLModelDB)
                .where(MLModelDB.status == status.value)
                .offset(skip)
                .limit(limit)
                .order_by(MLModelDB.created_at.desc())
            )
            result = await session.execute(query)
            db_models = result.scalars().all()
            return [self._to_domain(db_model) for db_model in db_models]

    async def get_latest_deployed(self) -> MLModel | None:
        """Get the latest deployed model.

        Returns:
            Latest deployed model or None
        """
        async with self._session_factory() as session:
            query = (
                select(MLModelDB)
                .where(MLModelDB.status == ModelStatus.DEPLOYED.value)
                .order_by(MLModelDB.deployed_at.desc())
                .limit(1)
            )
            result = await session.execute(query)
            db_model = result.scalar_one_or_none()

            if db_model:
                return self._to_domain(db_model)
            return None

    async def get_by_mlflow_run_id(self, mlflow_run_id: str) -> MLModel | None:
        """Get a model by MLflow run ID.

        Args:
            mlflow_run_id: MLflow run ID

        Returns:
            Model entity or None
        """
        async with self._session_factory() as session:
            query = select(MLModelDB).where(MLModelDB.mlflow_run_id == mlflow_run_id)
            result = await session.execute(query)
            db_model = result.scalar_one_or_none()

            if db_model:
                return self._to_domain(db_model)
            return None

    async def list_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        status: ModelStatus | None = None,
    ) -> tuple[list[MLModel], int]:
        """Get paginated list of models with total count.

        Args:
            page: Page number (1-indexed)
            page_size: Items per page
            status: Optional status filter

        Returns:
            Tuple of (models, total_count)
        """
        async with self._session_factory() as session:
            # Calculate offset
            offset = (page - 1) * page_size

            # Build query
            query = select(MLModelDB)
            if status:
                query = query.where(MLModelDB.status == status.value)

            # Get total count
            count_query = select(func.count()).select_from(MLModelDB)
            if status:
                count_query = count_query.where(MLModelDB.status == status.value)
            total = await session.scalar(count_query) or 0

            # Get paginated results
            query = query.offset(offset).limit(page_size).order_by(MLModelDB.created_at.desc())
            result = await session.execute(query)
            db_models = result.scalars().all()

            # Convert to domain entities
            models = [self._to_domain(db_model) for db_model in db_models]

            return models, total
