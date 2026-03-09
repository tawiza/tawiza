"""SQLAlchemy implementation of retraining job repository."""

from collections.abc import Callable
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.retraining_job import (
    RetrainingJob,
    RetrainingStatus,
    RetrainingTriggerReason,
)
from src.domain.repositories.ml_repositories import IRetrainingJobRepository
from src.infrastructure.persistence.models.retraining_job_model import RetrainingJobDB


class SQLAlchemyRetrainingJobRepository(IRetrainingJobRepository):
    """SQLAlchemy implementation of the retraining job repository."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        """Initialize the repository.

        Args:
            session_factory: Factory function to create database sessions
        """
        self._session_factory = session_factory

    def _to_domain(self, db_model: RetrainingJobDB) -> RetrainingJob:
        """Convert database model to domain entity.

        Args:
            db_model: Database model

        Returns:
            Domain entity
        """
        job = RetrainingJob(
            id=db_model.id,
            trigger_reason=RetrainingTriggerReason(db_model.trigger_reason),
            model_name=db_model.model_name,
            base_model_version=db_model.base_model_version,
            new_samples_count=db_model.new_samples_count,
            status=RetrainingStatus(db_model.status),
            fine_tuning_job_id=db_model.fine_tuning_job_id,
            new_model_version=db_model.new_model_version,
            drift_report_id=db_model.drift_report_id,
            started_at=db_model.started_at,
            completed_at=db_model.completed_at,
            error_message=db_model.error_message,
            config=db_model.config or {},
            metrics=db_model.metrics or {},
            metadata=db_model.job_metadata or {},
        )
        return job

    def _to_db_model(self, job: RetrainingJob) -> RetrainingJobDB:
        """Convert domain entity to database model.

        Args:
            job: Domain entity

        Returns:
            Database model
        """
        return RetrainingJobDB(
            id=job.id,
            trigger_reason=job.trigger_reason.value,
            model_name=job.model_name,
            base_model_version=job.base_model_version,
            new_samples_count=job.new_samples_count,
            status=job.status.value,
            fine_tuning_job_id=job.fine_tuning_job_id,
            new_model_version=job.new_model_version,
            drift_report_id=job.drift_report_id,
            started_at=job.started_at,
            completed_at=job.completed_at,
            error_message=job.error_message,
            config=job.config,
            metrics=job.metrics,
            job_metadata=job.metadata,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )

    async def save(self, job: RetrainingJob) -> RetrainingJob:
        """Save a retraining job entity."""
        async with self._session_factory() as session:
            db_model = self._to_db_model(job)
            session.add(db_model)
            await session.commit()
            await session.refresh(db_model)
            return self._to_domain(db_model)

    async def get_by_id(self, job_id: UUID) -> RetrainingJob | None:
        """Get retraining job by ID."""
        async with self._session_factory() as session:
            query = select(RetrainingJobDB).where(RetrainingJobDB.id == job_id)
            result = await session.execute(query)
            db_model = result.scalar_one_or_none()
            return self._to_domain(db_model) if db_model else None

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[RetrainingJob]:
        """Get all retraining jobs with pagination."""
        async with self._session_factory() as session:
            query = (
                select(RetrainingJobDB)
                .order_by(RetrainingJobDB.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            result = await session.execute(query)
            db_models = result.scalars().all()
            return [self._to_domain(db_model) for db_model in db_models]

    async def delete(self, job_id: UUID) -> bool:
        """Delete retraining job by ID."""
        async with self._session_factory() as session:
            query = select(RetrainingJobDB).where(RetrainingJobDB.id == job_id)
            result = await session.execute(query)
            db_model = result.scalar_one_or_none()
            if db_model:
                await session.delete(db_model)
                await session.commit()
                return True
            return False

    async def exists(self, entity_id: UUID) -> bool:
        """Check if retraining job exists."""
        async with self._session_factory() as session:
            query = select(func.count(RetrainingJobDB.id)).where(
                RetrainingJobDB.id == entity_id
            )
            result = await session.execute(query)
            count = result.scalar() or 0
            return count > 0

    async def count(self) -> int:
        """Count total number of retraining jobs."""
        async with self._session_factory() as session:
            query = select(func.count(RetrainingJobDB.id))
            result = await session.execute(query)
            return result.scalar() or 0

    async def get_by_model(
        self, model_name: str, skip: int = 0, limit: int = 100
    ) -> list[RetrainingJob]:
        """Get retraining jobs by model name."""
        async with self._session_factory() as session:
            query = (
                select(RetrainingJobDB)
                .where(RetrainingJobDB.model_name == model_name)
                .order_by(RetrainingJobDB.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            result = await session.execute(query)
            db_models = result.scalars().all()
            return [self._to_domain(db_model) for db_model in db_models]

    async def get_by_status(
        self, status: RetrainingStatus, skip: int = 0, limit: int = 100
    ) -> list[RetrainingJob]:
        """Get retraining jobs by status."""
        async with self._session_factory() as session:
            query = (
                select(RetrainingJobDB)
                .where(RetrainingJobDB.status == status.value)
                .order_by(RetrainingJobDB.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            result = await session.execute(query)
            db_models = result.scalars().all()
            return [self._to_domain(db_model) for db_model in db_models]

    async def get_by_trigger_reason(
        self,
        trigger_reason: RetrainingTriggerReason,
        skip: int = 0,
        limit: int = 100,
    ) -> list[RetrainingJob]:
        """Get retraining jobs by trigger reason."""
        async with self._session_factory() as session:
            query = (
                select(RetrainingJobDB)
                .where(RetrainingJobDB.trigger_reason == trigger_reason.value)
                .order_by(RetrainingJobDB.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            result = await session.execute(query)
            db_models = result.scalars().all()
            return [self._to_domain(db_model) for db_model in db_models]

    async def get_running_jobs(self) -> list[RetrainingJob]:
        """Get all currently running retraining jobs."""
        async with self._session_factory() as session:
            query = (
                select(RetrainingJobDB)
                .where(RetrainingJobDB.status == RetrainingStatus.RUNNING.value)
                .order_by(RetrainingJobDB.started_at.desc())
            )
            result = await session.execute(query)
            db_models = result.scalars().all()
            return [self._to_domain(db_model) for db_model in db_models]

    async def get_latest_by_model(self, model_name: str) -> RetrainingJob | None:
        """Get the most recent retraining job for a model."""
        async with self._session_factory() as session:
            query = (
                select(RetrainingJobDB)
                .where(RetrainingJobDB.model_name == model_name)
                .order_by(RetrainingJobDB.created_at.desc())
                .limit(1)
            )
            result = await session.execute(query)
            db_model = result.scalar_one_or_none()
            return self._to_domain(db_model) if db_model else None

    async def get_by_drift_report(self, drift_report_id: UUID) -> list[RetrainingJob]:
        """Get retraining jobs triggered by a specific drift report."""
        async with self._session_factory() as session:
            query = (
                select(RetrainingJobDB)
                .where(RetrainingJobDB.drift_report_id == drift_report_id)
                .order_by(RetrainingJobDB.created_at.desc())
            )
            result = await session.execute(query)
            db_models = result.scalars().all()
            return [self._to_domain(db_model) for db_model in db_models]
