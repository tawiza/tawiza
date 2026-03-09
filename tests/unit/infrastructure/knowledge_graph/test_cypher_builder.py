"""Tests for CypherBuilder."""

import pytest

from src.infrastructure.knowledge_graph.sync.cypher_builder import CypherBuilder
from src.infrastructure.knowledge_graph.sync.queue import SyncItem


class TestCypherBuilder:
    """Test Cypher query generation."""

    def test_build_merge_company(self):
        """Build MERGE query for company."""
        item = SyncItem(
            operation="merge", node_type="Company", data={"siren": "123456789", "name": "Test Corp"}
        )
        query, params = CypherBuilder.build_single(item)
        assert "MERGE" in query
        assert "Company" in query
        assert params["siren"] == "123456789"

    def test_build_create_query(self):
        """Build CREATE query."""
        item = SyncItem(
            operation="create", node_type="Territory", data={"code": "34", "name": "Herault"}
        )
        query, params = CypherBuilder.build_single(item)
        assert "CREATE" in query
        assert "Territory" in query

    def test_build_delete_query(self):
        """Build DELETE query."""
        item = SyncItem(operation="delete", node_type="Company", data={"siren": "123456789"})
        query, params = CypherBuilder.build_single(item)
        assert "DELETE" in query
        assert "MATCH" in query

    def test_build_batch_query(self):
        """Build batch UNWIND query."""
        items = [
            SyncItem("merge", "Company", {"siren": "111", "name": "A"}),
            SyncItem("merge", "Company", {"siren": "222", "name": "B"}),
        ]
        query, params = CypherBuilder.build_batch(items)
        assert "UNWIND" in query
        assert len(params["items"]) == 2

    def test_build_batch_empty(self):
        """Empty batch returns empty query."""
        query, params = CypherBuilder.build_batch([])
        assert query == ""
        assert params == {}

    def test_build_with_relationship(self):
        """Build relationship query."""
        item = SyncItem(
            operation="merge",
            node_type="Establishment",
            data={"siret": "12345678901234"},
            relationship={
                "type": "LOCATED_IN",
                "target_type": "Territory",
                "target_key": "code",
                "target_value": "34",
            },
        )
        query, params = CypherBuilder.build_with_relationship(item)
        assert "LOCATED_IN" in query
        assert "Territory" in query
        assert params["target_value"] == "34"

    def test_unique_keys_mapping(self):
        """Correct unique keys for each node type."""
        assert CypherBuilder.UNIQUE_KEYS["Company"] == "siren"
        assert CypherBuilder.UNIQUE_KEYS["Establishment"] == "siret"
        assert CypherBuilder.UNIQUE_KEYS["Territory"] == "code"
        assert CypherBuilder.UNIQUE_KEYS["Sector"] == "naf_code"
