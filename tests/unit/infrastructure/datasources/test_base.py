"""Tests for datasource base classes."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.datasources.base import (
    AdapterConfig,
    BaseAdapter,
    DataSourceAdapter,
    SyncStatus,
)


class TestAdapterConfig:
    """Test AdapterConfig dataclass."""

    def test_defaults(self):
        cfg = AdapterConfig(name="test", base_url="http://example.com")
        assert cfg.rate_limit == 60
        assert cfg.cache_ttl == 3600
        assert cfg.timeout == 30.0
        assert cfg.enabled is True

    def test_custom(self):
        cfg = AdapterConfig(
            name="sirene",
            base_url="https://api.insee.fr",
            rate_limit=30,
            cache_ttl=7200,
            timeout=15.0,
            enabled=False,
        )
        assert cfg.rate_limit == 30
        assert cfg.enabled is False


class TestSyncStatus:
    """Test SyncStatus dataclass."""

    def test_success(self):
        status = SyncStatus(
            adapter_name="geo",
            last_sync=datetime.now(),
            records_synced=100,
            status="success",
        )
        assert status.error is None
        assert status.records_synced == 100

    def test_failed(self):
        status = SyncStatus(
            adapter_name="geo",
            last_sync=None,
            records_synced=0,
            status="failed",
            error="Connection timeout",
        )
        assert status.error == "Connection timeout"


class ConcreteAdapter(BaseAdapter):
    """Concrete adapter for testing base class."""

    async def search(self, query):
        return [{"id": "1", "name": "test"}]

    async def get_by_id(self, id):
        if id == "1":
            return {"id": "1", "name": "test"}
        return None


class TestBaseAdapter:
    """Test BaseAdapter abstract class."""

    @pytest.fixture
    def config(self):
        return AdapterConfig(name="test", base_url="http://example.com")

    @pytest.fixture
    def adapter(self, config):
        return ConcreteAdapter(config)

    def test_name(self, adapter):
        assert adapter.name == "test"

    def test_config(self, adapter, config):
        assert adapter.config is config

    def test_client_exists(self, adapter):
        assert adapter.client is not None

    @pytest.mark.asyncio
    async def test_search(self, adapter):
        results = await adapter.search({})
        assert len(results) == 1
        assert results[0]["name"] == "test"

    @pytest.mark.asyncio
    async def test_get_by_id_found(self, adapter):
        result = await adapter.get_by_id("1")
        assert result is not None
        assert result["id"] == "1"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, adapter):
        result = await adapter.get_by_id("999")
        assert result is None

    @pytest.mark.asyncio
    async def test_sync_default(self, adapter):
        status = await adapter.sync()
        assert status.status == "not_implemented"
        assert status.adapter_name == "test"

    @pytest.mark.asyncio
    async def test_close(self, adapter):
        await adapter.close()
        # Client should be closed

    def test_log_error(self, adapter):
        # Should not raise
        adapter._log_error("test_op", ValueError("boom"))

    def test_log_debug(self, adapter):
        # Should not raise
        adapter._log_debug("test message")


class TestDataSourceAdapterProtocol:
    """Test the DataSourceAdapter protocol."""

    def test_concrete_adapter_is_datasource(self):
        config = AdapterConfig(name="test", base_url="http://example.com")
        adapter = ConcreteAdapter(config)
        assert isinstance(adapter, DataSourceAdapter)
