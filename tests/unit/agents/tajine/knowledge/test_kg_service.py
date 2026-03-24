"""Tests for TAJINE Knowledge Graph service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestKnowledgeGraphService:
    """Test Knowledge Graph service."""

    @pytest.mark.asyncio
    async def test_store_enterprise(self):
        """Should store enterprise in KG."""
        with patch("src.infrastructure.agents.tajine.knowledge.service.Neo4jClient") as MockClient:
            mock_client = MagicMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.execute_write = AsyncMock(return_value=[{"e": {}}])
            MockClient.return_value = mock_client

            from src.infrastructure.agents.tajine.knowledge.service import KnowledgeGraphService

            service = KnowledgeGraphService()
            await service.connect()

            result = await service.store_enterprise(
                {"siret": "12345678901234", "nom": "Test Corp", "departement": "34"}
            )

            assert result is True
            mock_client.execute_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_enterprises_batch(self):
        """Should store multiple enterprises."""
        with patch("src.infrastructure.agents.tajine.knowledge.service.Neo4jClient") as MockClient:
            mock_client = MagicMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.execute_write = AsyncMock(return_value=[{"stored": 3}])
            MockClient.return_value = mock_client

            from src.infrastructure.agents.tajine.knowledge.service import KnowledgeGraphService

            service = KnowledgeGraphService()
            await service.connect()

            result = await service.store_enterprises_batch(
                [
                    {"siret": "111", "nom": "Corp1", "departement": "34"},
                    {"siret": "222", "nom": "Corp2", "departement": "34"},
                    {"siret": "333", "nom": "Corp3", "departement": "34"},
                ]
            )

            assert result == 3

    @pytest.mark.asyncio
    async def test_query_enterprises_by_territory(self):
        """Should query enterprises by territory."""
        with patch("src.infrastructure.agents.tajine.knowledge.service.Neo4jClient") as MockClient:
            mock_client = MagicMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.execute = AsyncMock(
                return_value=[{"e": {"siret": "123", "nom": "Test Corp", "departement": "34"}}]
            )
            MockClient.return_value = mock_client

            from src.infrastructure.agents.tajine.knowledge.service import KnowledgeGraphService

            service = KnowledgeGraphService()
            await service.connect()

            result = await service.get_enterprises_by_territory("34")

            assert len(result) == 1
            assert result[0]["siret"] == "123"

    @pytest.mark.asyncio
    async def test_query_enterprises_by_naf(self):
        """Should query enterprises by NAF code."""
        with patch("src.infrastructure.agents.tajine.knowledge.service.Neo4jClient") as MockClient:
            mock_client = MagicMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.execute = AsyncMock(
                return_value=[{"e": {"siret": "123", "naf_code": "6201Z"}}]
            )
            MockClient.return_value = mock_client

            from src.infrastructure.agents.tajine.knowledge.service import KnowledgeGraphService

            service = KnowledgeGraphService()
            await service.connect()

            result = await service.get_enterprises_by_naf("6201Z", department="34")

            assert len(result) == 1
            assert result[0]["naf_code"] == "6201Z"

    @pytest.mark.asyncio
    async def test_graceful_degradation_without_neo4j(self):
        """Should work without Neo4j (degraded mode)."""
        with patch("src.infrastructure.agents.tajine.knowledge.service.Neo4jClient") as MockClient:
            mock_client = MagicMock()
            mock_client.connect = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            from src.infrastructure.agents.tajine.knowledge.service import KnowledgeGraphService

            service = KnowledgeGraphService()
            await service.connect()

            # Should not raise, just return empty
            result = await service.get_enterprises_by_territory("34")

            assert result == []
            assert service.is_available is False

    @pytest.mark.asyncio
    async def test_store_analysis_result(self):
        """Should store analysis result linked to territory."""
        with patch("src.infrastructure.agents.tajine.knowledge.service.Neo4jClient") as MockClient:
            mock_client = MagicMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.execute_write = AsyncMock(return_value=[{"a": {}}])
            MockClient.return_value = mock_client

            from src.infrastructure.agents.tajine.knowledge.service import KnowledgeGraphService

            service = KnowledgeGraphService()
            await service.connect()

            result = await service.store_analysis_result(
                territory="34",
                analysis_type="tech_potential",
                result={"score": 0.85, "summary": "High potential"},
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_get_context_for_query(self):
        """Should get context for a query."""
        with patch("src.infrastructure.agents.tajine.knowledge.service.Neo4jClient") as MockClient:
            mock_client = MagicMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.execute = AsyncMock(return_value=[{"e": {"siret": "123", "nom": "Test"}}])
            MockClient.return_value = mock_client

            from src.infrastructure.agents.tajine.knowledge.service import KnowledgeGraphService

            service = KnowledgeGraphService()
            await service.connect()

            context = await service.get_context_for_query(query="tech potential", territory="34")

            assert context["available"] is True
            assert context["territory"] == "34"
            assert len(context["enterprises"]) >= 0

    @pytest.mark.asyncio
    async def test_get_territory_stats(self):
        """Should get aggregated territory statistics."""
        with patch("src.infrastructure.agents.tajine.knowledge.service.Neo4jClient") as MockClient:
            mock_client = MagicMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.execute = AsyncMock(
                return_value=[
                    {"total": 150, "sector_count": 25, "top_sectors": ["6201Z", "6202A", "7022Z"]}
                ]
            )
            MockClient.return_value = mock_client

            from src.infrastructure.agents.tajine.knowledge.service import KnowledgeGraphService

            service = KnowledgeGraphService()
            await service.connect()

            stats = await service.get_territory_stats("34")

            assert stats["available"] is True
            assert stats["total_enterprises"] == 150
            assert stats["sector_count"] == 25

    @pytest.mark.asyncio
    async def test_create_relationship(self):
        """Should create relationship between enterprises."""
        with patch("src.infrastructure.agents.tajine.knowledge.service.Neo4jClient") as MockClient:
            mock_client = MagicMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.execute_write = AsyncMock(return_value=[{"r": {}}])
            MockClient.return_value = mock_client

            from src.infrastructure.agents.tajine.knowledge.service import KnowledgeGraphService

            service = KnowledgeGraphService()
            await service.connect()

            result = await service.create_relationship(
                from_siret="111",
                to_siret="222",
                relationship_type="PARTNER",
                properties={"since": "2024"},
            )

            assert result is True
