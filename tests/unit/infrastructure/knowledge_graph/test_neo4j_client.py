"""Tests for Neo4jClient."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.knowledge_graph.neo4j_client import Neo4jClient, Neo4jConfig


class TestNeo4jConfig:
    """Test Neo4jConfig dataclass."""

    def test_default_config(self):
        """Default config values."""
        config = Neo4jConfig()
        assert config.uri == "bolt://localhost:7687"
        assert config.user == "neo4j"
        assert config.database == "neo4j"

    def test_custom_config(self):
        """Custom config values."""
        config = Neo4jConfig(uri="bolt://custom:7687", user="admin", password="secret")
        assert config.uri == "bolt://custom:7687"
        assert config.user == "admin"


class TestNeo4jClientCreation:
    """Test Neo4jClient initialization."""

    def test_create_client(self):
        """Create client with config."""
        config = Neo4jConfig(password="test")
        client = Neo4jClient(config)
        assert client is not None
        assert client.config == config

    def test_client_not_connected_initially(self):
        """Client not connected until connect() called."""
        config = Neo4jConfig(password="test")
        client = Neo4jClient(config)
        assert not client.is_connected


class TestNeo4jClientOperations:
    """Test Neo4jClient operations with mocks."""

    @pytest.mark.asyncio
    async def test_execute_query(self):
        """Execute Cypher query."""
        config = Neo4jConfig(password="test")
        client = Neo4jClient(config)

        # Mock driver
        mock_session = MagicMock()
        mock_session.run = MagicMock(return_value=MagicMock(data=lambda: [{"n": 1}]))
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)

        client._driver = MagicMock()
        client._driver.session = MagicMock(return_value=mock_session)

        result = await client.execute("RETURN 1 as n")
        assert result == [{"n": 1}]

    @pytest.mark.asyncio
    async def test_close(self):
        """Close cleans up driver."""
        config = Neo4jConfig(password="test")
        client = Neo4jClient(config)
        mock_driver = MagicMock()
        client._driver = mock_driver

        await client.close()
        mock_driver.close.assert_called_once()
        assert client._driver is None
