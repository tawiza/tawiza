"""Tests for graph algorithms."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.knowledge_graph.algorithms.centrality import (
    CentralityCalculator,
    CentralityScore,
)
from src.infrastructure.knowledge_graph.algorithms.communities import Community, CommunityDetector
from src.infrastructure.knowledge_graph.algorithms.similarity import (
    SimilarCompany,
    SimilarityFinder,
)


class TestCommunity:
    """Test Community dataclass."""

    def test_create_community(self):
        """Create community."""
        community = Community(id=0, members=["111", "222", "333"], size=3, dominant_sector="6201Z")
        assert community.id == 0
        assert len(community.members) == 3
        assert community.size == 3


class TestCommunityDetector:
    """Test community detection."""

    def test_create_detector(self):
        """Create detector with client."""
        client = MagicMock()
        detector = CommunityDetector(client)
        assert detector is not None

    @pytest.mark.asyncio
    async def test_detect_communities(self):
        """Detect communities in territory."""
        client = MagicMock()
        client.execute = AsyncMock(
            return_value=[
                {"siren": "111", "community": 0},
                {"siren": "222", "community": 0},
                {"siren": "333", "community": 1},
            ]
        )

        detector = CommunityDetector(client)
        communities = await detector.detect(territory_code="34", min_community_size=1)

        assert len(communities) == 2  # 2 communities
        # First community should be larger (sorted by size)
        assert communities[0].size == 2

    @pytest.mark.asyncio
    async def test_detect_filters_by_min_size(self):
        """Communities smaller than min_size are filtered."""
        client = MagicMock()
        client.execute = AsyncMock(
            return_value=[
                {"siren": "111", "community": 0},
                {"siren": "222", "community": 1},
            ]
        )

        detector = CommunityDetector(client)
        communities = await detector.detect(territory_code="34", min_community_size=2)

        # Both communities have size 1, so none should match
        assert len(communities) == 0

    @pytest.mark.asyncio
    async def test_detect_fallback_on_gds_error(self):
        """Falls back to simple detection when GDS fails."""
        client = MagicMock()
        # First call (GDS projection) fails
        client.execute = AsyncMock(
            side_effect=[
                Exception("GDS not available"),
                [
                    {"siren": "111", "sector": "6201Z"},
                    {"siren": "222", "sector": "6201Z"},
                ],
            ]
        )

        detector = CommunityDetector(client)
        communities = await detector.detect(territory_code="34")

        # Should have one community with 2 members
        assert len(communities) == 1
        assert communities[0].size == 2
        assert communities[0].dominant_sector == "6201Z"


class TestCentralityScore:
    """Test CentralityScore dataclass."""

    def test_create_score(self):
        """Create centrality score."""
        score = CentralityScore(siren="123456789", score=0.85, rank=1, name="Test Corp")
        assert score.siren == "123456789"
        assert score.score == 0.85
        assert score.rank == 1


class TestCentralityCalculator:
    """Test centrality calculation."""

    def test_create_calculator(self):
        """Create calculator."""
        client = MagicMock()
        calc = CentralityCalculator(client)
        assert calc is not None

    @pytest.mark.asyncio
    async def test_pagerank(self):
        """Calculate PageRank centrality."""
        client = MagicMock()
        client.execute = AsyncMock(
            return_value=[
                {"siren": "111", "name": "Company A", "score": 0.85},
                {"siren": "222", "name": "Company B", "score": 0.65},
            ]
        )

        calc = CentralityCalculator(client)
        scores = await calc.pagerank(territory_code="34", top_k=10)

        assert len(scores) == 2
        assert scores[0].siren == "111"
        assert scores[0].score == 0.85
        assert scores[0].rank == 1

    @pytest.mark.asyncio
    async def test_pagerank_fallback(self):
        """Falls back to simple degree centrality when GDS fails."""
        client = MagicMock()
        client.execute = AsyncMock(
            side_effect=[
                Exception("GDS not available"),
                [
                    {"siren": "111", "name": "A", "score": 5},
                    {"siren": "222", "name": "B", "score": 3},
                ],
            ]
        )

        calc = CentralityCalculator(client)
        scores = await calc.pagerank(territory_code="34")

        assert len(scores) == 2
        assert scores[0].rank == 1


class TestSimilarCompany:
    """Test SimilarCompany dataclass."""

    def test_create_similar(self):
        """Create similar company."""
        similar = SimilarCompany(
            siren="222", similarity=0.9, name="Similar Corp", shared_sectors=["6201Z", "6202A"]
        )
        assert similar.siren == "222"
        assert similar.similarity == 0.9
        assert len(similar.shared_sectors) == 2


class TestSimilarityFinder:
    """Test similarity finder."""

    def test_create_finder(self):
        """Create similarity finder."""
        client = MagicMock()
        finder = SimilarityFinder(client)
        assert finder is not None

    @pytest.mark.asyncio
    async def test_find_similar(self):
        """Find similar companies."""
        client = MagicMock()
        client.execute = AsyncMock(
            return_value=[
                {"siren": "222", "name": "B", "similarity": 0.9},
                {"siren": "333", "name": "C", "similarity": 0.7},
            ]
        )

        finder = SimilarityFinder(client)
        similar = await finder.find_similar(siren="111", top_k=5)

        assert len(similar) == 2
        assert similar[0].siren == "222"
        assert similar[0].similarity == 0.9

    @pytest.mark.asyncio
    async def test_find_similar_fallback(self):
        """Falls back to Jaccard similarity when GDS fails."""
        client = MagicMock()
        client.execute = AsyncMock(
            side_effect=[
                Exception("GDS not available"),
                [
                    {"siren": "222", "name": "B", "similarity": 0.75, "shared": ["6201Z"]},
                ],
            ]
        )

        finder = SimilarityFinder(client)
        similar = await finder.find_similar(siren="111")

        assert len(similar) == 1
        assert similar[0].shared_sectors == ["6201Z"]
