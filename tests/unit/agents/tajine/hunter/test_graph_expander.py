"""Tests for Neo4j Graph Expander (gap detection)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.agents.tajine.hunter.graph_expander import (
    GapType,
    GraphExpander,
    KnowledgeGap,
)


class TestGraphExpander:
    """Test graph gap detection."""

    @pytest.fixture
    def mock_neo4j(self):
        """Create mock Neo4j client."""
        client = MagicMock()
        client.run_query = AsyncMock(return_value=[])
        return client

    @pytest.mark.asyncio
    async def test_find_missing_relationships(self, mock_neo4j):
        """Should detect missing relationships in KG."""
        mock_neo4j.run_query = AsyncMock(
            return_value=[
                {"siren": "123", "missing_type": "Dirigeant"},
                {"siren": "456", "missing_type": "Secteur"},
            ]
        )

        expander = GraphExpander(neo4j_client=mock_neo4j)
        gaps = await expander.find_gaps(territory="31")

        missing_rels = [g for g in gaps if g.gap_type == GapType.MISSING_RELATIONSHIP]
        assert len(missing_rels) >= 1

    @pytest.mark.asyncio
    async def test_find_stale_entities(self, mock_neo4j):
        """Should detect stale entities (not updated recently)."""
        from datetime import datetime, timedelta

        old_date = (datetime.now() - timedelta(days=100)).isoformat()

        mock_neo4j.run_query = AsyncMock(
            return_value=[
                {"siren": "123456789", "last_updated": old_date},
            ]
        )

        expander = GraphExpander(neo4j_client=mock_neo4j, stale_days=90)
        gaps = await expander.find_gaps(territory="31")

        stale = [g for g in gaps if g.gap_type == GapType.STALE_DATA]
        assert len(stale) >= 1

    @pytest.mark.asyncio
    async def test_find_missing_fields(self, mock_neo4j):
        """Should detect entities with missing important fields."""
        mock_neo4j.run_query = AsyncMock(
            return_value=[
                {"siren": "123456789", "missing": "chiffre_affaires,effectif"},
            ]
        )

        expander = GraphExpander(neo4j_client=mock_neo4j)
        gaps = await expander.find_gaps(territory="31")

        incomplete = [g for g in gaps if g.gap_type == GapType.INCOMPLETE_ENTITY]
        assert len(incomplete) >= 1

    def test_gap_to_search_query(self, mock_neo4j):
        """Should convert gap to actionable search query."""
        gap = KnowledgeGap(
            gap_type=GapType.MISSING_RELATIONSHIP,
            entity_id="SIREN:123456789",
            description="Missing dirigeant relationship",
            priority=1,
        )

        expander = GraphExpander(neo4j_client=mock_neo4j)
        queries = expander.gap_to_queries(gap)

        assert len(queries) >= 1
        assert "123456789" in queries[0]
