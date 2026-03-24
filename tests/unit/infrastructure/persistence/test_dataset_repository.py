"""Tests for SQLAlchemy Dataset Repository.

This module tests:
- Repository initialization
- Domain-DB model conversion
- CRUD operations (save, get, delete)
- Query operations (get_by_name, get_by_type, get_by_status, etc.)
- Pagination
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch
from uuid import uuid4

import pytest

from src.domain.entities.dataset import Dataset, DatasetMetadata, DatasetStatus, DatasetType
from src.infrastructure.persistence.repositories.dataset_repository import (
    SQLAlchemyDatasetRepository,
)


class MockResult:
    """Mock SQLAlchemy result."""

    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None


class TestRepositoryInitialization:
    """Test suite for repository initialization."""

    def test_repository_requires_session(self):
        """Repository should require an async session."""
        session = MagicMock()
        repo = SQLAlchemyDatasetRepository(session)
        assert repo.session is session

    def test_repository_stores_session(self):
        """Repository should store session for later use."""
        session = MagicMock()
        repo = SQLAlchemyDatasetRepository(session)
        assert repo.session == session


class TestDomainConversion:
    """Test suite for domain-DB model conversion."""

    @pytest.fixture
    def mock_db_model(self):
        """Create mock database model."""
        db_model = MagicMock()
        db_model.id = uuid4()
        db_model.name = "Test Dataset"
        db_model.dataset_type = "training"  # Valid DatasetType value
        db_model.status = "ready"
        db_model.size = 1000
        db_model.source = "api"
        db_model.format = "csv"
        db_model.schema_version = "1.0"
        db_model.annotations_required = True
        db_model.annotations_completed = 500
        db_model.storage_path = "/data/datasets/test"
        db_model.dvc_path = None
        db_model.label_studio_project_id = 42
        db_model.statistics = {"mean": 0.5}
        db_model.tags = {"env": "production"}
        db_model.created_at = datetime(2025, 1, 1, 0, 0, 0)
        db_model.updated_at = datetime(2025, 1, 2, 12, 0, 0)
        return db_model

    def test_to_domain_converts_basic_fields(self, mock_db_model):
        """_to_domain should convert basic fields."""
        session = MagicMock()
        repo = SQLAlchemyDatasetRepository(session)

        dataset = repo._to_domain(mock_db_model)

        assert dataset.id == mock_db_model.id
        assert dataset.name == "Test Dataset"
        assert dataset.dataset_type == DatasetType.TRAINING
        assert dataset.status == DatasetStatus.READY

    def test_to_domain_converts_metadata(self, mock_db_model):
        """_to_domain should convert metadata."""
        session = MagicMock()
        repo = SQLAlchemyDatasetRepository(session)

        dataset = repo._to_domain(mock_db_model)

        assert dataset.metadata is not None
        assert dataset.metadata.size == 1000
        assert dataset.metadata.source == "api"
        assert dataset.metadata.format == "csv"

    def test_to_domain_handles_null_size(self, mock_db_model):
        """_to_domain should handle null size (no metadata)."""
        mock_db_model.size = None
        session = MagicMock()
        repo = SQLAlchemyDatasetRepository(session)

        dataset = repo._to_domain(mock_db_model)

        assert dataset.metadata is None

    def test_to_domain_restores_internal_state(self, mock_db_model):
        """_to_domain should restore internal state."""
        session = MagicMock()
        repo = SQLAlchemyDatasetRepository(session)

        dataset = repo._to_domain(mock_db_model)

        assert dataset.storage_path == "/data/datasets/test"
        assert dataset.label_studio_project_id == 42
        assert dataset._tags == {"env": "production"}

    def test_to_domain_handles_null_collections(self, mock_db_model):
        """_to_domain should handle null statistics and tags."""
        mock_db_model.statistics = None
        mock_db_model.tags = None
        session = MagicMock()
        repo = SQLAlchemyDatasetRepository(session)

        dataset = repo._to_domain(mock_db_model)

        assert dataset._statistics == {}
        assert dataset._tags == {}

    def test_to_db_converts_domain_entity(self):
        """_to_db should convert domain entity to DB model."""
        session = MagicMock()
        repo = SQLAlchemyDatasetRepository(session)

        dataset = Dataset(
            name="New Dataset",
            dataset_type=DatasetType.TRAINING,
        )

        db_model = repo._to_db(dataset)

        assert db_model.id == dataset.id
        assert db_model.name == "New Dataset"
        assert db_model.dataset_type == "training"
        assert db_model.status == "draft"  # Default status for new Dataset


class TestSaveOperation:
    """Test suite for save operation."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = MagicMock()
        session.get = AsyncMock(return_value=None)
        session.add = MagicMock()
        session.flush = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_save_new_entity(self, mock_session):
        """Save should add new entity to session."""
        repo = SQLAlchemyDatasetRepository(mock_session)
        dataset = Dataset(name="New Dataset", dataset_type=DatasetType.TRAINING)

        mock_session.get = AsyncMock(return_value=None)  # Entity doesn't exist

        result = await repo.save(dataset)

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        assert result == dataset

    @pytest.mark.asyncio
    async def test_save_existing_entity(self, mock_session):
        """Save should update existing entity."""
        repo = SQLAlchemyDatasetRepository(mock_session)
        dataset = Dataset(name="Updated Dataset", dataset_type=DatasetType.TRAINING)

        # Mock existing entity with proper __dict__ structure
        from src.infrastructure.persistence.models.dataset_model import DatasetDB

        existing = DatasetDB(
            id=dataset.id,
            name="Old Name",
            dataset_type="training",
            status="draft",
        )
        mock_session.get = AsyncMock(return_value=existing)

        result = await repo.save(dataset)

        mock_session.add.assert_not_called()  # Should not add, just update
        mock_session.flush.assert_called_once()
        assert result == dataset


class TestGetOperations:
    """Test suite for get operations."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = MagicMock()
        return session

    @pytest.fixture
    def mock_db_model(self):
        """Create mock database model."""
        db_model = MagicMock()
        db_model.id = uuid4()
        db_model.name = "Test Dataset"
        db_model.dataset_type = "training"  # Valid DatasetType value
        db_model.status = "ready"
        db_model.size = 1000
        db_model.source = "api"
        db_model.format = "csv"
        db_model.schema_version = "1.0"
        db_model.annotations_required = True
        db_model.annotations_completed = 500
        db_model.storage_path = None
        db_model.dvc_path = None
        db_model.label_studio_project_id = None
        db_model.statistics = {}
        db_model.tags = {}
        db_model.created_at = datetime.now()
        db_model.updated_at = datetime.now()
        return db_model

    @pytest.mark.asyncio
    async def test_get_by_id_found(self, mock_session, mock_db_model):
        """get_by_id should return dataset when found."""
        mock_session.get = AsyncMock(return_value=mock_db_model)
        repo = SQLAlchemyDatasetRepository(mock_session)

        result = await repo.get_by_id(mock_db_model.id)

        assert result is not None
        assert result.id == mock_db_model.id
        mock_session.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, mock_session):
        """get_by_id should return None when not found."""
        mock_session.get = AsyncMock(return_value=None)
        repo = SQLAlchemyDatasetRepository(mock_session)

        result = await repo.get_by_id(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_with_pagination(self, mock_session, mock_db_model):
        """get_all should return paginated results."""
        mock_result = MockResult([mock_db_model])
        mock_session.execute = AsyncMock(return_value=mock_result)
        repo = SQLAlchemyDatasetRepository(mock_session)

        result = await repo.get_all(skip=0, limit=10)

        assert len(result) == 1
        assert result[0].id == mock_db_model.id
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_empty(self, mock_session):
        """get_all should return empty list when no datasets."""
        mock_result = MockResult([])
        mock_session.execute = AsyncMock(return_value=mock_result)
        repo = SQLAlchemyDatasetRepository(mock_session)

        result = await repo.get_all()

        assert result == []


class TestDeleteOperation:
    """Test suite for delete operation."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = MagicMock()
        session.delete = AsyncMock()
        session.flush = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_delete_existing(self, mock_session):
        """delete should remove existing entity and return True."""
        db_model = MagicMock()
        mock_session.get = AsyncMock(return_value=db_model)
        repo = SQLAlchemyDatasetRepository(mock_session)

        result = await repo.delete(uuid4())

        assert result is True
        mock_session.delete.assert_called_once_with(db_model)
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_not_found(self, mock_session):
        """delete should return False when entity not found."""
        mock_session.get = AsyncMock(return_value=None)
        repo = SQLAlchemyDatasetRepository(mock_session)

        result = await repo.delete(uuid4())

        assert result is False
        mock_session.delete.assert_not_called()


class TestExistsOperation:
    """Test suite for exists operation."""

    @pytest.mark.asyncio
    async def test_exists_true(self):
        """exists should return True when entity exists."""
        session = MagicMock()
        session.get = AsyncMock(return_value=MagicMock())
        repo = SQLAlchemyDatasetRepository(session)

        result = await repo.exists(uuid4())

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(self):
        """exists should return False when entity doesn't exist."""
        session = MagicMock()
        session.get = AsyncMock(return_value=None)
        repo = SQLAlchemyDatasetRepository(session)

        result = await repo.exists(uuid4())

        assert result is False


class TestCountOperation:
    """Test suite for count operation."""

    @pytest.mark.asyncio
    async def test_count_returns_total(self):
        """count should return total number of datasets."""
        session = MagicMock()
        mock_result = MockResult([MagicMock(), MagicMock(), MagicMock()])
        session.execute = AsyncMock(return_value=mock_result)
        repo = SQLAlchemyDatasetRepository(session)

        result = await repo.count()

        assert result == 3

    @pytest.mark.asyncio
    async def test_count_empty(self):
        """count should return 0 when no datasets."""
        session = MagicMock()
        mock_result = MockResult([])
        session.execute = AsyncMock(return_value=mock_result)
        repo = SQLAlchemyDatasetRepository(session)

        result = await repo.count()

        assert result == 0


class TestQueryOperations:
    """Test suite for query operations."""

    @pytest.fixture
    def mock_db_model(self):
        """Create mock database model."""
        db_model = MagicMock()
        db_model.id = uuid4()
        db_model.name = "Query Test Dataset"
        db_model.dataset_type = "training"  # Valid DatasetType value
        db_model.status = "ready"
        db_model.size = 1000
        db_model.source = "api"
        db_model.format = "json"
        db_model.schema_version = "1.0"
        db_model.annotations_required = True
        db_model.annotations_completed = 500
        db_model.storage_path = None
        db_model.dvc_path = None
        db_model.label_studio_project_id = 123
        db_model.statistics = {}
        db_model.tags = {}
        db_model.created_at = datetime.now()
        db_model.updated_at = datetime.now()
        return db_model

    @pytest.mark.asyncio
    async def test_get_by_name_found(self, mock_db_model):
        """get_by_name should return dataset when found."""
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_db_model)
        session.execute = AsyncMock(return_value=mock_result)
        repo = SQLAlchemyDatasetRepository(session)

        result = await repo.get_by_name("Query Test Dataset")

        assert result is not None
        assert result.name == "Query Test Dataset"

    @pytest.mark.asyncio
    async def test_get_by_name_not_found(self):
        """get_by_name should return None when not found."""
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        session.execute = AsyncMock(return_value=mock_result)
        repo = SQLAlchemyDatasetRepository(session)

        result = await repo.get_by_name("Nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_type(self, mock_db_model):
        """get_by_type should filter by dataset type."""
        session = MagicMock()
        mock_result = MockResult([mock_db_model])
        session.execute = AsyncMock(return_value=mock_result)
        repo = SQLAlchemyDatasetRepository(session)

        result = await repo.get_by_type(DatasetType.TRAINING)

        assert len(result) == 1
        assert result[0].dataset_type == DatasetType.TRAINING

    @pytest.mark.asyncio
    async def test_get_by_status(self, mock_db_model):
        """get_by_status should filter by status."""
        session = MagicMock()
        mock_result = MockResult([mock_db_model])
        session.execute = AsyncMock(return_value=mock_result)
        repo = SQLAlchemyDatasetRepository(session)

        result = await repo.get_by_status(DatasetStatus.READY)

        assert len(result) == 1
        assert result[0].status == DatasetStatus.READY

    @pytest.mark.asyncio
    async def test_get_ready_datasets(self, mock_db_model):
        """get_ready_datasets should return only ready datasets."""
        session = MagicMock()
        mock_result = MockResult([mock_db_model])
        session.execute = AsyncMock(return_value=mock_result)
        repo = SQLAlchemyDatasetRepository(session)

        result = await repo.get_ready_datasets()

        assert len(result) == 1
        assert result[0].status == DatasetStatus.READY

    @pytest.mark.asyncio
    async def test_get_ready_datasets_with_type_filter(self, mock_db_model):
        """get_ready_datasets should filter by type when provided."""
        session = MagicMock()
        mock_result = MockResult([mock_db_model])
        session.execute = AsyncMock(return_value=mock_result)
        repo = SQLAlchemyDatasetRepository(session)

        result = await repo.get_ready_datasets(dataset_type=DatasetType.TRAINING)

        assert len(result) == 1
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_label_studio_project_found(self, mock_db_model):
        """get_by_label_studio_project should return dataset when found."""
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_db_model)
        session.execute = AsyncMock(return_value=mock_result)
        repo = SQLAlchemyDatasetRepository(session)

        result = await repo.get_by_label_studio_project(123)

        assert result is not None
        assert result.label_studio_project_id == 123

    @pytest.mark.asyncio
    async def test_get_by_label_studio_project_not_found(self):
        """get_by_label_studio_project should return None when not found."""
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        session.execute = AsyncMock(return_value=mock_result)
        repo = SQLAlchemyDatasetRepository(session)

        result = await repo.get_by_label_studio_project(999)

        assert result is None
