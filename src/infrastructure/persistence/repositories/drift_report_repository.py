"""SQLAlchemy implementation of drift report repository."""

from collections.abc import Callable
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.drift_report import DriftReport, DriftSeverity, DriftType
from src.domain.repositories.ml_repositories import IDriftReportRepository
from src.infrastructure.persistence.models.drift_report_model import DriftReportDB


class SQLAlchemyDriftReportRepository(IDriftReportRepository):
    """SQLAlchemy implementation of the drift report repository."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        """Initialize the repository.

        Args:
            session_factory: Factory function to create database sessions
        """
        self._session_factory = session_factory

    def _to_domain(self, db_model: DriftReportDB) -> DriftReport:
        """Convert database model to domain entity.

        Args:
            db_model: Database model

        Returns:
            Domain entity
        """
        return DriftReport(
            id=db_model.id,
            model_name=db_model.model_name,
            model_version=db_model.model_version,
            drift_type=DriftType(db_model.drift_type),
            metric_name=db_model.metric_name,
            current_value=db_model.current_value,
            baseline_value=db_model.baseline_value,
            drift_score=db_model.drift_score,
            is_drifted=db_model.is_drifted,
            severity=DriftSeverity(db_model.severity),
            threshold=db_model.threshold,
            window_start=db_model.window_start,
            window_end=db_model.window_end,
            sample_count=db_model.sample_count,
            details=db_model.details or {},
        )

    def _to_db_model(self, drift_report: DriftReport) -> DriftReportDB:
        """Convert domain entity to database model.

        Args:
            drift_report: Domain entity

        Returns:
            Database model
        """
        return DriftReportDB(
            id=drift_report.id,
            model_name=drift_report.model_name,
            model_version=drift_report.model_version,
            drift_type=drift_report.drift_type.value,
            metric_name=drift_report.metric_name,
            current_value=drift_report.current_value,
            baseline_value=drift_report.baseline_value,
            drift_score=drift_report.drift_score,
            is_drifted=drift_report.is_drifted,
            severity=drift_report.severity.value,
            threshold=drift_report.threshold,
            window_start=drift_report.window_start,
            window_end=drift_report.window_end,
            sample_count=drift_report.sample_count,
            details=drift_report.details,
            created_at=drift_report.created_at,
            updated_at=drift_report.updated_at,
        )

    async def save(self, drift_report: DriftReport) -> DriftReport:
        """Save a drift report entity."""
        async with self._session_factory() as session:
            db_model = self._to_db_model(drift_report)
            session.add(db_model)
            await session.commit()
            await session.refresh(db_model)
            return self._to_domain(db_model)

    async def get_by_id(self, drift_report_id: UUID) -> DriftReport | None:
        """Get drift report by ID."""
        async with self._session_factory() as session:
            query = select(DriftReportDB).where(DriftReportDB.id == drift_report_id)
            result = await session.execute(query)
            db_model = result.scalar_one_or_none()
            return self._to_domain(db_model) if db_model else None

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[DriftReport]:
        """Get all drift reports with pagination."""
        async with self._session_factory() as session:
            query = (
                select(DriftReportDB)
                .order_by(DriftReportDB.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            result = await session.execute(query)
            db_models = result.scalars().all()
            return [self._to_domain(db_model) for db_model in db_models]

    async def delete(self, drift_report_id: UUID) -> bool:
        """Delete drift report by ID."""
        async with self._session_factory() as session:
            query = select(DriftReportDB).where(DriftReportDB.id == drift_report_id)
            result = await session.execute(query)
            db_model = result.scalar_one_or_none()
            if db_model:
                await session.delete(db_model)
                await session.commit()
                return True
            return False

    async def exists(self, entity_id: UUID) -> bool:
        """Check if drift report exists."""
        async with self._session_factory() as session:
            query = select(func.count(DriftReportDB.id)).where(DriftReportDB.id == entity_id)
            result = await session.execute(query)
            count = result.scalar() or 0
            return count > 0

    async def count(self) -> int:
        """Count total number of drift reports."""
        async with self._session_factory() as session:
            query = select(func.count(DriftReportDB.id))
            result = await session.execute(query)
            return result.scalar() or 0

    async def get_by_model(
        self, model_name: str, model_version: str, skip: int = 0, limit: int = 100
    ) -> list[DriftReport]:
        """Get drift reports by model."""
        async with self._session_factory() as session:
            query = (
                select(DriftReportDB)
                .where(
                    DriftReportDB.model_name == model_name,
                    DriftReportDB.model_version == model_version,
                )
                .order_by(DriftReportDB.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            result = await session.execute(query)
            db_models = result.scalars().all()
            return [self._to_domain(db_model) for db_model in db_models]

    async def get_by_drift_type(
        self, drift_type: DriftType, skip: int = 0, limit: int = 100
    ) -> list[DriftReport]:
        """Get drift reports by type."""
        async with self._session_factory() as session:
            query = (
                select(DriftReportDB)
                .where(DriftReportDB.drift_type == drift_type.value)
                .order_by(DriftReportDB.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            result = await session.execute(query)
            db_models = result.scalars().all()
            return [self._to_domain(db_model) for db_model in db_models]

    async def get_drifted_reports(
        self, model_name: str | None = None, skip: int = 0, limit: int = 100
    ) -> list[DriftReport]:
        """Get reports where drift was detected."""
        async with self._session_factory() as session:
            query = select(DriftReportDB).where(DriftReportDB.is_drifted)

            if model_name:
                query = query.where(DriftReportDB.model_name == model_name)

            query = query.order_by(DriftReportDB.created_at.desc()).offset(skip).limit(limit)

            result = await session.execute(query)
            db_models = result.scalars().all()
            return [self._to_domain(db_model) for db_model in db_models]

    async def get_latest_by_model(self, model_name: str, model_version: str) -> DriftReport | None:
        """Get the latest drift report for a model."""
        async with self._session_factory() as session:
            query = (
                select(DriftReportDB)
                .where(
                    DriftReportDB.model_name == model_name,
                    DriftReportDB.model_version == model_version,
                )
                .order_by(DriftReportDB.created_at.desc())
                .limit(1)
            )
            result = await session.execute(query)
            db_model = result.scalar_one_or_none()
            return self._to_domain(db_model) if db_model else None
