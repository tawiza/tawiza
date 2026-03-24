"""Tests for ExtendedKnowledgeGraph."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.knowledge_graph.extended_kg import ExtendedKnowledgeGraph
from src.infrastructure.knowledge_graph.neo4j_client import Neo4jConfig


class TestExtendedKGCreation:
    """Test ExtendedKnowledgeGraph creation."""

    def test_create_without_neo4j(self):
        """Create without Neo4j (in-memory only)."""
        kg = ExtendedKnowledgeGraph()
        assert kg is not None
        assert kg._neo4j_client is None

    def test_create_with_neo4j_config(self):
        """Create with Neo4j config."""
        config = Neo4jConfig(password="test")
        kg = ExtendedKnowledgeGraph(neo4j_config=config)
        assert kg._neo4j_client is not None

    def test_inherits_kg_functionality(self):
        """ExtendedKG has parent KG methods."""
        kg = ExtendedKnowledgeGraph()
        # Should have parent methods
        assert hasattr(kg, "add_triple")
        assert hasattr(kg, "query")
        assert hasattr(kg, "validate_claim")


class TestExtendedKGOperations:
    """Test ExtendedKnowledgeGraph operations."""

    def test_add_triple_works_in_memory(self):
        """Adding triple works without Neo4j."""
        kg = ExtendedKnowledgeGraph()
        kg.add_triple("company:123", "has_name", "Test Corp")

        triples = kg.query(subject="company:123")
        assert len(triples) == 1
        assert triples[0].obj == "Test Corp"

    def test_add_triple_queues_sync(self):
        """Adding triple queues for Neo4j sync when configured."""
        config = Neo4jConfig(password="test")
        kg = ExtendedKnowledgeGraph(neo4j_config=config)

        kg.add_triple("company:123", "has_name", "Test Corp")

        # Should have added to in-memory
        triples = kg.query(subject="company:123")
        assert len(triples) == 1

    @pytest.mark.asyncio
    async def test_get_communities(self):
        """Get communities delegates to algorithm."""
        config = Neo4jConfig(password="test")
        kg = ExtendedKnowledgeGraph(neo4j_config=config)
        kg._community_detector = MagicMock()
        kg._community_detector.detect = AsyncMock(return_value=[])

        await kg.get_communities("34")
        kg._community_detector.detect.assert_called_once_with("34", 2)

    @pytest.mark.asyncio
    async def test_get_top_companies(self):
        """Get top companies delegates to centrality."""
        config = Neo4jConfig(password="test")
        kg = ExtendedKnowledgeGraph(neo4j_config=config)
        kg._centrality_calc = MagicMock()
        kg._centrality_calc.pagerank = AsyncMock(return_value=[])

        await kg.get_top_companies("34", top_k=10)
        kg._centrality_calc.pagerank.assert_called_once_with("34", 10)

    @pytest.mark.asyncio
    async def test_find_similar_companies(self):
        """Find similar companies delegates to similarity."""
        config = Neo4jConfig(password="test")
        kg = ExtendedKnowledgeGraph(neo4j_config=config)
        kg._similarity_finder = MagicMock()
        kg._similarity_finder.find_similar = AsyncMock(return_value=[])

        await kg.find_similar_companies("123456789", top_k=5)
        kg._similarity_finder.find_similar.assert_called_once_with("123456789", 5)

    @pytest.mark.asyncio
    async def test_returns_empty_without_neo4j(self):
        """Algorithm methods return empty without Neo4j config."""
        kg = ExtendedKnowledgeGraph()

        communities = await kg.get_communities("34")
        assert communities == []

        top = await kg.get_top_companies("34")
        assert top == []

        similar = await kg.find_similar_companies("123")
        assert similar == []
