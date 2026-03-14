"""SQLAlchemy implementation of Dataset repository."""

from uuid import UUID

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.dataset import Dataset, DatasetMetadata, DatasetStatus, DatasetType
from src.domain.repositories.ml_repositories import IDatasetRepository
from src.infrastructure.persistence.models.dataset_model import DatasetDB


class SQLAlchemyDatasetRepository(IDatasetRepository):
    """SQLAlchemy implementation of IDatasetRepository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    def _to_domain(self, db_model: DatasetDB) -> Dataset:
        """Convert database model to domain entity.

        Args:
            db_model: Database model

        Returns:
            Domain entity
        """
        dataset = Dataset(
            id=db_model.id,
            name=db_model.name,
            dataset_type=DatasetType(db_model.dataset_type),
            status=DatasetStatus(db_model.status),
        )

        # Restore internal state
        if db_model.size is not None:
            dataset._metadata = DatasetMetadata(
                size=db_model.size,
                source=db_model.source,
                format=db_model.format,
                schema_version=db_model.schema_version,
                annotations_required=db_model.annotations_required,
                annotations_completed=db_model.annotations_completed,
            )

        dataset._storage_path = db_model.storage_path
        dataset._dvc_path = db_model.dvc_path
        dataset._label_studio_project_id = db_model.label_studio_project_id
        dataset._statistics = db_model.statistics or {}
        dataset._tags = db_model.tags or {}
        dataset._created_at = db_model.created_at
        dataset._updated_at = db_model.updated_at

        return dataset

    def _to_db(self, dataset: Dataset) -> DatasetDB:
        """Convert domain entity to database model.

        Args:
            dataset: Domain entity

        Returns:
            Database model
        """
        metadata = dataset.metadata

        return DatasetDB(
            id=dataset.id,
            name=dataset.name,
            dataset_type=dataset.dataset_type.value,
            status=dataset.status.value,
            size=metadata.size if metadata else 0,
            source=metadata.source if metadata else "",
            format=metadata.format if metadata else "",
            schema_version=metadata.schema_version if metadata else "1.0",
            annotations_required=metadata.annotations_required if metadata else True,
            annotations_completed=metadata.annotations_completed if metadata else 0,
            storage_path=dataset.storage_path,
            dvc_path=dataset.dvc_path,
            label_studio_project_id=dataset.label_studio_project_id,
            statistics=dataset._statistics,
            tags=dataset._tags,
            created_at=dataset.created_at,
            updated_at=dataset.updated_at,
        )

    async def save(self, entity: Dataset) -> Dataset:
        """Save a dataset entity.

        Args:
            entity: Dataset entity to save

        Returns:
            Saved dataset entity
        """
        existing = await self.session.get(DatasetDB, entity.id)

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
        logger.debug(f"Saved dataset {entity.id}")
        return entity

    async def get_by_id(self, entity_id: UUID) -> Dataset | None:
        """Get a dataset by ID.

        Args:
            entity_id: Dataset ID

        Returns:
            Dataset entity or None
        """
        db_model = await self.session.get(DatasetDB, entity_id)
        if db_model:
            return self._to_domain(db_model)
        return None

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[Dataset]:
        """Get all datasets with pagination.

        Args:
            skip: Number to skip
            limit: Maximum to return

        Returns:
            List of dataset entities
        """
        query = select(DatasetDB).offset(skip).limit(limit).order_by(DatasetDB.created_at.desc())
        result = await self.session.execute(query)
        db_models = result.scalars().all()
        return [self._to_domain(db_model) for db_model in db_models]

    async def delete(self, entity_id: UUID) -> bool:
        """Delete a dataset.

        Args:
            entity_id: Dataset ID

        Returns:
            True if deleted, False if not found
        """
        db_model = await self.session.get(DatasetDB, entity_id)
        if db_model:
            await self.session.delete(db_model)
            await self.session.flush()
            logger.info(f"Deleted dataset {entity_id}")
            return True
        return False

    async def exists(self, entity_id: UUID) -> bool:
        """Check if a dataset exists.

        Args:
            entity_id: Dataset ID

        Returns:
            True if exists
        """
        db_model = await self.session.get(DatasetDB, entity_id)
        return db_model is not None

    async def count(self) -> int:
        """Count total datasets.

        Returns:
            Total count
        """
        query = select(DatasetDB)
        result = await self.session.execute(query)
        return len(result.scalars().all())

    async def get_by_name(self, name: str) -> Dataset | None:
        """Get a dataset by name.

        Args:
            name: Dataset name

        Returns:
            Dataset entity or None
        """
        query = select(DatasetDB).where(DatasetDB.name == name)
        result = await self.session.execute(query)
        db_model = result.scalar_one_or_none()

        if db_model:
            return self._to_domain(db_model)
        return None

    async def get_by_type(
        self,
        dataset_type: DatasetType,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Dataset]:
        """Get datasets by type.

        Args:
            dataset_type: Dataset type
            skip: Number to skip
            limit: Maximum to return

        Returns:
            List of datasets
        """
        query = (
            select(DatasetDB)
            .where(DatasetDB.dataset_type == dataset_type.value)
            .offset(skip)
            .limit(limit)
            .order_by(DatasetDB.created_at.desc())
        )
        result = await self.session.execute(query)
        db_models = result.scalars().all()
        return [self._to_domain(db_model) for db_model in db_models]

    async def get_by_status(
        self,
        status: DatasetStatus,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Dataset]:
        """Get datasets by status.

        Args:
            status: Dataset status
            skip: Number to skip
            limit: Maximum to return

        Returns:
            List of datasets
        """
        query = (
            select(DatasetDB)
            .where(DatasetDB.status == status.value)
            .offset(skip)
            .limit(limit)
            .order_by(DatasetDB.created_at.desc())
        )
        result = await self.session.execute(query)
        db_models = result.scalars().all()
        return [self._to_domain(db_model) for db_model in db_models]

    async def get_ready_datasets(
        self,
        dataset_type: DatasetType | None = None,
    ) -> list[Dataset]:
        """Get all ready datasets, optionally filtered by type.

        Args:
            dataset_type: Optional dataset type to filter by

        Returns:
            List of ready datasets
        """
        query = select(DatasetDB).where(DatasetDB.status == DatasetStatus.READY.value)

        if dataset_type:
            query = query.where(DatasetDB.dataset_type == dataset_type.value)

        query = query.order_by(DatasetDB.created_at.desc())

        result = await self.session.execute(query)
        db_models = result.scalars().all()
        return [self._to_domain(db_model) for db_model in db_models]

    async def get_by_label_studio_project(
        self,
        project_id: int,
    ) -> Dataset | None:
        """Get dataset by Label Studio project ID.

        Args:
            project_id: Label Studio project ID

        Returns:
            Dataset entity or None
        """
        query = select(DatasetDB).where(DatasetDB.label_studio_project_id == project_id)
        result = await self.session.execute(query)
        db_model = result.scalar_one_or_none()

        if db_model:
            return self._to_domain(db_model)
        return None
