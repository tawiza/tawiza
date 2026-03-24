"""Tests for DataSourceManager facade."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.datasources.base import AdapterConfig, BaseAdapter
from src.infrastructure.datasources.manager import DataSourceManager


class MockAdapter(BaseAdapter):
    """Mock adapter for testing."""

    async def search(self, query):
        return [{"siret": "12345678901234", "nom": "Test Co"}]

    async def get_by_id(self, id):
        return {"siret": id, "nom": "Test Co"} if id == "12345678901234" else None

    async def health_check(self):
        return True


@pytest.fixture
def manager():
    return DataSourceManager()


@pytest.fixture
def mock_adapter():
    config = AdapterConfig(name="mock", base_url="http://test")
    return MockAdapter(config)


def test_manager_can_register_adapter(manager, mock_adapter):
    """Test registering an adapter."""
    manager.register(mock_adapter)
    assert "mock" in manager.adapters


def test_manager_can_unregister_adapter(manager, mock_adapter):
    """Test unregistering an adapter."""
    manager.register(mock_adapter)
    manager.unregister("mock")
    assert "mock" not in manager.adapters


@pytest.mark.asyncio
async def test_manager_search_all_sources(manager, mock_adapter):
    """Test searching across all registered adapters."""
    manager.register(mock_adapter)
    results = await manager.search({"query": "test"})
    assert len(results) > 0
    assert results[0]["siret"] == "12345678901234"
    assert results[0]["_source"] == "mock"


@pytest.mark.asyncio
async def test_manager_search_specific_sources(manager, mock_adapter):
    """Test searching specific sources only."""
    manager.register(mock_adapter)
    results = await manager.search({"query": "test"}, sources=["mock"])
    assert len(results) > 0
    assert results[0]["_source"] == "mock"


@pytest.mark.asyncio
async def test_manager_search_with_no_adapters(manager):
    """Test searching with no registered adapters."""
    results = await manager.search({"query": "test"})
    assert len(results) == 0


@pytest.mark.asyncio
async def test_manager_get_enterprise(manager, mock_adapter):
    """Test getting enterprise from any source."""
    manager.register(mock_adapter)
    result = await manager.get_enterprise("12345678901234")
    assert result is not None
    assert result["siret"] == "12345678901234"
    assert result["_source"] == "mock"


@pytest.mark.asyncio
async def test_manager_get_enterprise_not_found(manager, mock_adapter):
    """Test getting non-existent enterprise."""
    manager.register(mock_adapter)
    result = await manager.get_enterprise("99999999999999")
    assert result is None


@pytest.mark.asyncio
async def test_manager_get_merged_enterprise(manager, mock_adapter):
    """Test getting merged enterprise data from multiple sources."""
    manager.register(mock_adapter)
    result = await manager.get_merged_enterprise("12345678901234")
    assert result is not None
    assert result["siret"] == "12345678901234"
    assert "mock" in result["_sources"]


@pytest.mark.asyncio
async def test_manager_get_merged_enterprise_not_found(manager, mock_adapter):
    """Test getting merged enterprise data when not found."""
    manager.register(mock_adapter)
    result = await manager.get_merged_enterprise("99999999999999")
    assert result is None


@pytest.mark.asyncio
async def test_manager_status(manager, mock_adapter):
    """Test getting status of all adapters."""
    manager.register(mock_adapter)
    status = await manager.status()
    assert "mock" in status
    assert status["mock"]["healthy"] is True
    assert "config" in status["mock"]
    assert status["mock"]["config"]["rate_limit"] == 60


@pytest.mark.asyncio
async def test_manager_status_with_failing_adapter(manager):
    """Test status when adapter health check fails."""

    class FailingAdapter(BaseAdapter):
        async def search(self, query):
            return []

        async def get_by_id(self, id):
            return None

        async def health_check(self):
            raise Exception("Connection failed")

    config = AdapterConfig(name="failing", base_url="http://test")
    failing_adapter = FailingAdapter(config)
    manager.register(failing_adapter)

    status = await manager.status()
    assert "failing" in status
    assert status["failing"]["healthy"] is False
    assert "error" in status["failing"]


@pytest.mark.asyncio
async def test_manager_sync_all(manager, mock_adapter):
    """Test syncing all adapters."""
    manager.register(mock_adapter)
    statuses = await manager.sync_all()
    assert len(statuses) == 1
    assert statuses[0].adapter_name == "mock"
    # MockAdapter uses BaseAdapter.sync which returns "not_implemented"
    assert statuses[0].status == "not_implemented"
