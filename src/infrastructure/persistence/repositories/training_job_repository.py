"""SQLAlchemy implementation of TrainingJob repository."""

from uuid import UUID

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.training_job import (
    TrainingConfig,
    TrainingJob,
    TrainingJobStatus,
    TrainingTrigger,
)
from src.domain.repositories.ml_repositories import ITrainingJobRepository
from src.infrastructure.persistence.models.training_job_model import TrainingJobDB


class SQLAlchemyTrainingJobRepository(ITrainingJobRepository):
    """SQLAlchemy implementation of ITrainingJobRepository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    def _to_domain(self, db_model: TrainingJobDB) -> TrainingJob:
        """Convert database model to domain entity.

        Args:
            db_model: Database model

        Returns:
            Domain entity
        """
        job = TrainingJob(
            id=db_model.id,
            name=db_model.name,
            trigger=TrainingTrigger(db_model.trigger),
            status=TrainingJobStatus(db_model.status),
        )

        # Restore internal state
        if db_model.config:
            job._config = TrainingConfig(**db_model.config)

        job._current_model_id = db_model.current_model_id
        job._output_model_id = db_model.output_model_id
        job._mlflow_run_id = db_model.mlflow_run_id
        job._prefect_flow_run_id = db_model.prefect_flow_run_id
        job._started_at = db_model.started_at
        job._completed_at = db_model.completed_at
        job._duration_seconds = db_model.duration_seconds
        job._metrics = db_model.metrics or {}
        job._error_message = db_model.error_message
        job._logs_path = db_model.logs_path
        job._created_at = db_model.created_at
        job._updated_at = db_model.updated_at

        return job

    def _to_db(self, job: TrainingJob) -> TrainingJobDB:
        """Convert domain entity to database model.

        Args:
            job: Domain entity

        Returns:
            Database model
        """
        return TrainingJobDB(
            id=job.id,
            name=job.name,
            trigger=job.trigger.value,
            status=job.status.value,
            config=job.config.__dict__ if job.config else None,
            current_model_id=job.current_model_id,
            output_model_id=job.output_model_id,
            mlflow_run_id=job.mlflow_run_id,
            prefect_flow_run_id=job._prefect_flow_run_id,
            started_at=job._started_at,
            completed_at=job._completed_at,
            duration_seconds=job.duration_seconds,
            metrics=job.metrics,
            error_message=job._error_message,
            logs_path=job._logs_path,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )

    async def save(self, entity: TrainingJob) -> TrainingJob:
        """Save a training job entity.

        Args:
            entity: TrainingJob entity to save

        Returns:
            Saved training job entity
        """
        existing = await self.session.get(TrainingJobDB, entity.id)

        if existing:
            # Update existing
            db_model = self._to_db(entity)
            for key, value in db_model.__dict__.items():
                if not key.startswith("_") and key != "id":
                    setattr(existing, key, value)
        else:
            # Create new
            db_model = self._to_db(entity)
            self.session.add(db_model)

        await self.session.flush()
        logger.debug(f"Saved training job {entity.id}")
        return entity

    async def get_by_id(self, entity_id: UUID) -> TrainingJob | None:
        """Get a training job by ID.

        Args:
            entity_id: Training job ID

        Returns:
            TrainingJob entity or None
        """
        db_model = await self.session.get(TrainingJobDB, entity_id)
        if db_model:
            return self._to_domain(db_model)
        return None

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[TrainingJob]:
        """Get all training jobs with pagination.

        Args:
            skip: Number to skip
            limit: Maximum to return

        Returns:
            List of training job entities
        """
        query = (
            select(TrainingJobDB)
            .offset(skip)
            .limit(limit)
            .order_by(TrainingJobDB.created_at.desc())
        )
        result = await self.session.execute(query)
        db_models = result.scalars().all()
        return [self._to_domain(db_model) for db_model in db_models]

    async def delete(self, entity_id: UUID) -> bool:
        """Delete a training job.

        Args:
            entity_id: Training job ID

        Returns:
            True if deleted, False if not found
        """
        db_model = await self.session.get(TrainingJobDB, entity_id)
        if db_model:
            await self.session.delete(db_model)
            await self.session.flush()
            logger.info(f"Deleted training job {entity_id}")
            return True
        return False

    async def exists(self, entity_id: UUID) -> bool:
        """Check if a training job exists.

        Args:
            entity_id: Training job ID

        Returns:
            True if exists
        """
        db_model = await self.session.get(TrainingJobDB, entity_id)
        return db_model is not None

    async def count(self) -> int:
        """Count total training jobs.

        Returns:
            Total count
        """
        query = select(TrainingJobDB)
        result = await self.session.execute(query)
        return len(result.scalars().all())

    async def get_by_status(
        self,
        status: TrainingJobStatus,
        skip: int = 0,
        limit: int = 100,
    ) -> list[TrainingJob]:
        """Get training jobs by status.

        Args:
            status: Training job status
            skip: Number to skip
            limit: Maximum to return

        Returns:
            List of jobs
        """
        query = (
            select(TrainingJobDB)
            .where(TrainingJobDB.status == status.value)
            .offset(skip)
            .limit(limit)
            .order_by(TrainingJobDB.created_at.desc())
        )
        result = await self.session.execute(query)
        db_models = result.scalars().all()
        return [self._to_domain(db_model) for db_model in db_models]

    async def get_by_trigger(
        self,
        trigger: TrainingTrigger,
        skip: int = 0,
        limit: int = 100,
    ) -> list[TrainingJob]:
        """Get training jobs by trigger type.

        Args:
            trigger: Training trigger
            skip: Number to skip
            limit: Maximum to return

        Returns:
            List of jobs
        """
        query = (
            select(TrainingJobDB)
            .where(TrainingJobDB.trigger == trigger.value)
            .offset(skip)
            .limit(limit)
            .order_by(TrainingJobDB.created_at.desc())
        )
        result = await self.session.execute(query)
        db_models = result.scalars().all()
        return [self._to_domain(db_model) for db_model in db_models]

    async def get_running_jobs(self) -> list[TrainingJob]:
        """Get all currently running training jobs.

        Returns:
            List of running jobs
        """
        running_statuses = [
            TrainingJobStatus.PREPARING_DATA.value,
            TrainingJobStatus.TRAINING.value,
            TrainingJobStatus.EVALUATING.value,
        ]

        query = (
            select(TrainingJobDB)
            .where(TrainingJobDB.status.in_(running_statuses))
            .order_by(TrainingJobDB.started_at.desc())
        )

        result = await self.session.execute(query)
        db_models = result.scalars().all()
        return [self._to_domain(db_model) for db_model in db_models]

    async def get_by_mlflow_run_id(
        self,
        mlflow_run_id: str,
    ) -> TrainingJob | None:
        """Get a training job by its MLflow run ID.

        Args:
            mlflow_run_id: MLflow run ID

        Returns:
            TrainingJob entity or None
        """
        query = select(TrainingJobDB).where(TrainingJobDB.mlflow_run_id == mlflow_run_id)
        result = await self.session.execute(query)
        db_model = result.scalar_one_or_none()

        if db_model:
            return self._to_domain(db_model)
        return None

    async def get_latest_completed(self) -> TrainingJob | None:
        """Get the most recently completed training job.

        Returns:
            Latest completed job or None
        """
        query = (
            select(TrainingJobDB)
            .where(TrainingJobDB.status == TrainingJobStatus.COMPLETED.value)
            .order_by(TrainingJobDB.completed_at.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        db_model = result.scalar_one_or_none()

        if db_model:
            return self._to_domain(db_model)
        return None

    async def get_recent_jobs(
        self,
        limit: int = 10,
    ) -> list[TrainingJob]:
        """Get the most recent training jobs.

        Args:
            limit: Maximum number of jobs to return

        Returns:
            List of recent jobs
        """
        query = select(TrainingJobDB).order_by(TrainingJobDB.created_at.desc()).limit(limit)
        result = await self.session.execute(query)
        db_models = result.scalars().all()
        return [self._to_domain(db_model) for db_model in db_models]
