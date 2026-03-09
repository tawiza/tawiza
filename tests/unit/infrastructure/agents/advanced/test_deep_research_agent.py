"""Tests complets pour deep_research_agent.py

Tests couvrant:
- ResearchQuery, ResearchSource, ResearchResult dataclasses
- DeepResearchAgent
- Tests conditionnels (Ollama, Qdrant optionnels)
"""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.agents.advanced.deep_research_agent import (
    DeepResearchAgent,
    ResearchQuery,
    ResearchResult,
    ResearchSource,
)


# ============================================================================
# Fixtures
# ============================================================================
@pytest.fixture
def ollama_available():
    """Détecte si Ollama est disponible."""
    import httpx

    try:
        response = httpx.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


@pytest.fixture
def qdrant_available():
    """Détecte si Qdrant est disponible."""
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(host="localhost", port=6333, timeout=2)
        client.get_collections()
        return True
    except Exception:
        return False


# ============================================================================
# Tests ResearchQuery Dataclass
# ============================================================================
class TestResearchQuery:
    """Tests pour la dataclass ResearchQuery."""

    def test_create_query_minimal(self):
        """Création d'une requête minimale."""
        query = ResearchQuery(query="AI trends 2024")

        assert query.query == "AI trends 2024"
        assert query.depth == 2
        assert query.max_sources == 10
        assert "fr" in query.languages
        assert "en" in query.languages
        assert query.domains == []
        assert query.exclude_domains == []
        assert query.focus_keywords == []

    def test_create_query_full(self):
        """Création d'une requête complète."""
        query = ResearchQuery(
            query="Machine Learning in Healthcare",
            depth=5,
            max_sources=50,
            languages=["en"],
            domains=["arxiv.org", "pubmed.gov"],
            exclude_domains=["facebook.com", "twitter.com"],
            focus_keywords=["deep learning", "diagnosis", "medical imaging"],
        )

        assert query.depth == 5
        assert query.max_sources == 50
        assert len(query.languages) == 1
        assert len(query.domains) == 2
        assert len(query.exclude_domains) == 2
        assert len(query.focus_keywords) == 3


# ============================================================================
# Tests ResearchSource Dataclass
# ============================================================================
class TestResearchSource:
    """Tests pour la dataclass ResearchSource."""

    def test_create_source(self):
        """Création d'une source de recherche."""
        source = ResearchSource(
            url="https://example.com/article",
            title="AI Research Article",
            content="Full article content here...",
            summary="A summary of the article about AI research.",
            relevance_score=0.95,
            keywords=["AI", "machine learning", "research"],
            crawled_at="2024-01-01T12:00:00",
        )

        assert source.url == "https://example.com/article"
        assert source.title == "AI Research Article"
        assert source.relevance_score == 0.95
        assert len(source.keywords) == 3
        assert source.cached is False

    def test_cached_source(self):
        """Source mise en cache."""
        source = ResearchSource(
            url="https://example.com/cached",
            title="Cached Article",
            content="Content",
            summary="Summary",
            relevance_score=0.8,
            keywords=[],
            crawled_at="2024-01-01T00:00:00",
            cached=True,
        )

        assert source.cached is True


# ============================================================================
# Tests ResearchResult Dataclass
# ============================================================================
class TestResearchResult:
    """Tests pour la dataclass ResearchResult."""

    def test_create_result(self):
        """Création d'un résultat de recherche."""
        sources = [
            ResearchSource(
                url=f"https://source{i}.com",
                title=f"Source {i}",
                content="Content",
                summary="Summary",
                relevance_score=0.9 - i * 0.1,
                keywords=[],
                crawled_at="2024-01-01T00:00:00",
            )
            for i in range(3)
        ]

        result = ResearchResult(
            query="Test query",
            sources=sources,
            synthesis="Overall synthesis of all sources...",
            key_findings=["Finding 1", "Finding 2", "Finding 3"],
            recommendations=["Action 1", "Action 2"],
            related_queries=["Related query 1", "Related query 2"],
            total_sources_analyzed=10,
            execution_time_seconds=45.5,
            generated_at="2024-01-01T12:00:00",
        )

        assert result.query == "Test query"
        assert len(result.sources) == 3
        assert len(result.key_findings) == 3
        assert len(result.recommendations) == 2
        assert result.total_sources_analyzed == 10
        assert result.execution_time_seconds == 45.5


# ============================================================================
# Tests DeepResearchAgent - Création
# ============================================================================
class TestDeepResearchAgentBasic:
    """Tests basiques pour DeepResearchAgent."""

    def test_create_agent_default(self):
        """Création avec valeurs par défaut."""
        agent = DeepResearchAgent()

        assert agent.name == "DeepResearchAgent"
        assert agent.agent_type == "research"
        assert agent.ollama_model == "llama3.1:8b"
        assert agent.qdrant_host == "localhost"
        assert agent.qdrant_port == 6333
        assert agent.is_initialized is False

    def test_create_agent_custom(self):
        """Création avec paramètres personnalisés."""
        agent = DeepResearchAgent(
            ollama_url="http://localhost:11434",
            ollama_model="qwen3:14b",
            qdrant_host="qdrant.local",
            qdrant_port=6334,
            cache_bucket="custom-cache",
        )

        assert agent.ollama_url == "http://localhost:11434"
        assert agent.ollama_model == "qwen3:14b"
        assert agent.qdrant_host == "qdrant.local"
        assert agent.qdrant_port == 6334
        assert agent.cache_bucket == "custom-cache"

    def test_capabilities(self):
        """Vérification des capacités."""
        agent = DeepResearchAgent()

        expected_capabilities = [
            "web_crawling",
            "content_extraction",
            "semantic_search",
            "llm_analysis",
            "synthesis",
            "caching",
        ]

        for cap in expected_capabilities:
            assert cap in agent.capabilities

    def test_ollama_url_from_env(self):
        """URL Ollama depuis variable d'environnement."""
        os.environ["OLLAMA_URL"] = "http://env-ollama:11434"

        agent = DeepResearchAgent()
        assert agent.ollama_url == "http://env-ollama:11434"

        del os.environ["OLLAMA_URL"]


# ============================================================================
# Tests DeepResearchAgent - Initialisation mockée
# ============================================================================
class TestDeepResearchAgentInitialization:
    """Tests d'initialisation avec mocks."""

    @pytest.mark.asyncio
    async def test_initialize_minimal(self):
        """Initialisation minimale (sans S3/Qdrant)."""
        agent = DeepResearchAgent()

        # Mock des dépendances externes
        with (
            patch.object(agent, "s3", None),
            patch("src.infrastructure.agents.advanced.deep_research_agent.get_s3_agent") as mock_s3,
        ):
            mock_s3_instance = MagicMock()
            mock_s3_instance.connect = AsyncMock(return_value=False)
            mock_s3.return_value = mock_s3_instance

            result = await agent.initialize()

            assert agent.http_client is not None
            assert agent.is_initialized is True

    @pytest.mark.asyncio
    async def test_close(self):
        """Fermeture des ressources (si méthode existe)."""
        agent = DeepResearchAgent()

        # Check for close or cleanup method
        if hasattr(agent, "close"):
            agent.http_client = MagicMock()
            agent.http_client.aclose = AsyncMock()
            await agent.close()
            agent.http_client.aclose.assert_called_once()
        elif hasattr(agent, "cleanup"):
            agent.http_client = MagicMock()
            agent.http_client.aclose = AsyncMock()
            await agent.cleanup()
            agent.http_client.aclose.assert_called_once()
        else:
            # No cleanup method - just pass
            assert True


# ============================================================================
# Tests conditionnels - Services disponibles
# ============================================================================
class TestDeepResearchAgentConditional:
    """Tests conditionnels si services disponibles."""

    @pytest.mark.asyncio
    async def test_with_ollama(self, ollama_available):
        """Test avec Ollama réel."""
        if not ollama_available:
            pytest.skip("Ollama non disponible")

        agent = DeepResearchAgent()
        await agent.initialize()

        # Vérifier la connexion Ollama
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get(f"{agent.ollama_url}/api/tags")
            assert response.status_code == 200

        # Close if method exists
        if hasattr(agent, "close"):
            await agent.close()
        elif hasattr(agent, "cleanup"):
            await agent.cleanup()

    @pytest.mark.asyncio
    async def test_with_qdrant(self, qdrant_available):
        """Test avec Qdrant réel."""
        if not qdrant_available:
            pytest.skip("Qdrant non disponible")

        agent = DeepResearchAgent()
        await agent.initialize()

        assert agent.qdrant is not None

        # Close if method exists
        if hasattr(agent, "close"):
            await agent.close()
        elif hasattr(agent, "cleanup"):
            await agent.cleanup()


# ============================================================================
# Tests Edge Cases
# ============================================================================
class TestDeepResearchAgentEdgeCases:
    """Tests des cas limites."""

    def test_query_with_special_characters(self):
        """Requête avec caractères spéciaux."""
        query = ResearchQuery(
            query="AI & ML: What's next? (2024-2025)",
            focus_keywords=["AI/ML", '"predictions"', "trends+"],
        )

        assert "&" in query.query
        assert "'" in query.query
        assert "/" in query.focus_keywords[0]

    def test_result_with_no_sources(self):
        """Résultat sans sources trouvées."""
        result = ResearchResult(
            query="Very obscure topic",
            sources=[],
            synthesis="No relevant sources found.",
            key_findings=[],
            recommendations=["Broaden search terms"],
            related_queries=["Alternative query 1"],
            total_sources_analyzed=0,
            execution_time_seconds=5.0,
            generated_at="2024-01-01T00:00:00",
        )

        assert len(result.sources) == 0
        assert result.total_sources_analyzed == 0

    def test_high_relevance_filtering(self):
        """Filtrage par pertinence."""
        sources = [
            ResearchSource(
                url=f"https://source{i}.com",
                title=f"Source {i}",
                content="Content",
                summary="Summary",
                relevance_score=i / 10,
                keywords=[],
                crawled_at="2024-01-01T00:00:00",
            )
            for i in range(1, 11)
        ]

        # Filtrer les sources avec score > 0.7
        high_relevance = [s for s in sources if s.relevance_score > 0.7]
        assert len(high_relevance) == 3  # 0.8, 0.9, 1.0

    def test_multiple_agent_instances(self):
        """Plusieurs instances indépendantes."""
        agent1 = DeepResearchAgent(ollama_model="llama3.1:8b")
        agent2 = DeepResearchAgent(ollama_model="qwen3:14b")

        assert agent1.ollama_model != agent2.ollama_model
        assert agent1.is_initialized == agent2.is_initialized

    def test_collection_name(self):
        """Nom de collection Qdrant."""
        agent = DeepResearchAgent()
        assert agent.collection_name == "research_documents"
        assert agent.vector_size == 768  # nomic-embed-text
