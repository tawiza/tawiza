"""Tests for SemanticCoherenceScorer."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.agents.tajine.core.types import RawData
from src.infrastructure.agents.tajine.evaluator.semantic_scorer import (
    SemanticCoherenceResult,
    SemanticCoherenceScorer,
)
from src.infrastructure.agents.tajine.semantic.protocol import SemanticResult


@pytest.fixture
def mock_semantic_service():
    """Create mock SemanticSearchService."""
    service = MagicMock()
    service.search = AsyncMock()
    return service


@pytest.fixture
def sample_raw_data():
    """Create sample RawData for testing."""
    return RawData(
        source="sirene",
        content={"text": "Entreprise BTP Toulouse spécialisée construction"},
        url="https://api.sirene.fr/123",
        fetched_at=datetime.now(),
        quality_hint=0.7,
    )


class TestSemanticCoherenceScorer:
    """Tests for SemanticCoherenceScorer."""

    @pytest.mark.asyncio
    async def test_no_service_returns_neutral(self, sample_raw_data):
        """Test scorer returns 0.5 when no service available."""
        scorer = SemanticCoherenceScorer(semantic_service=None)

        result = await scorer.check(sample_raw_data)

        assert result.score == 0.5
        assert result.details["reason"] == "no_semantic_service"

    @pytest.mark.asyncio
    async def test_insufficient_text(self, mock_semantic_service):
        """Test scorer handles empty/short content."""
        scorer = SemanticCoherenceScorer(semantic_service=mock_semantic_service)
        data = RawData(
            source="test",
            content={"text": "short"},
            url="http://x",
            fetched_at=datetime.now(),
            quality_hint=0.5,
        )

        result = await scorer.check(data)

        assert result.score == 0.5
        assert result.details["reason"] == "insufficient_text"

    @pytest.mark.asyncio
    async def test_no_indexed_docs_is_novel(self, mock_semantic_service, sample_raw_data):
        """Test scorer treats no matches as novel data."""
        mock_semantic_service.search.return_value = []
        scorer = SemanticCoherenceScorer(semantic_service=mock_semantic_service)

        result = await scorer.check(sample_raw_data)

        assert result.score == 0.6  # Slightly positive for fresh data
        assert result.is_novel is True
        assert result.similar_docs_count == 0

    @pytest.mark.asyncio
    async def test_high_similarity_is_coherent(self, mock_semantic_service, sample_raw_data):
        """Test high similarity yields high coherence score."""
        mock_semantic_service.search.return_value = [
            SemanticResult(id="1", content="Similar", score=0.85, source_store="pgvector"),
            SemanticResult(id="2", content="Related", score=0.75, source_store="pgvector"),
        ]
        scorer = SemanticCoherenceScorer(semantic_service=mock_semantic_service)

        result = await scorer.check(sample_raw_data)

        assert result.score >= 0.7
        assert result.is_outlier is False
        assert result.similarity_to_indexed == 0.85

    @pytest.mark.asyncio
    async def test_medium_similarity_is_novel(self, mock_semantic_service, sample_raw_data):
        """Test medium similarity indicates novel but plausible data."""
        mock_semantic_service.search.return_value = [
            SemanticResult(id="1", content="Somewhat related", score=0.55, source_store="pgvector"),
        ]
        scorer = SemanticCoherenceScorer(
            semantic_service=mock_semantic_service,
            high_similarity_threshold=0.7,
            low_similarity_threshold=0.4,
        )

        result = await scorer.check(sample_raw_data)

        assert 0.5 <= result.score <= 0.7
        assert result.is_novel is True
        assert result.is_outlier is False

    @pytest.mark.asyncio
    async def test_low_similarity_is_outlier(self, mock_semantic_service, sample_raw_data):
        """Test very low similarity marks as outlier."""
        mock_semantic_service.search.return_value = [
            SemanticResult(id="1", content="Unrelated", score=0.15, source_store="pgvector"),
        ]
        scorer = SemanticCoherenceScorer(
            semantic_service=mock_semantic_service,
            outlier_threshold=0.2,
        )

        result = await scorer.check(sample_raw_data)

        assert result.score < 0.4
        assert result.is_outlier is True

    @pytest.mark.asyncio
    async def test_multiple_coherent_docs_bonus(self, mock_semantic_service, sample_raw_data):
        """Test bonus for multiple coherent documents."""
        mock_semantic_service.search.return_value = [
            SemanticResult(id="1", content="A", score=0.65, source_store="pgvector"),
            SemanticResult(id="2", content="B", score=0.60, source_store="pgvector"),
            SemanticResult(id="3", content="C", score=0.55, source_store="pgvector"),
            SemanticResult(id="4", content="D", score=0.50, source_store="pgvector"),
        ]
        scorer = SemanticCoherenceScorer(
            semantic_service=mock_semantic_service,
            low_similarity_threshold=0.4,
        )

        result = await scorer.check(sample_raw_data)

        # Should get a bonus for having 4 coherent docs
        assert result.score >= 0.5
        assert result.details["coherent_docs"] >= 3

    @pytest.mark.asyncio
    async def test_score_shortcut(self, mock_semantic_service, sample_raw_data):
        """Test score() returns just the numeric score."""
        mock_semantic_service.search.return_value = [
            SemanticResult(id="1", content="Related", score=0.75, source_store="pgvector"),
        ]
        scorer = SemanticCoherenceScorer(semantic_service=mock_semantic_service)

        score = await scorer.score(sample_raw_data)

        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_search_failure_handled(self, mock_semantic_service, sample_raw_data):
        """Test graceful handling of search failures."""
        mock_semantic_service.search.side_effect = Exception("Network error")
        scorer = SemanticCoherenceScorer(semantic_service=mock_semantic_service)

        result = await scorer.check(sample_raw_data)

        assert result.score == 0.5  # Neutral on failure
        assert result.details["reason"] == "search_failed"

    def test_extract_text_from_string(self):
        """Test text extraction from string content."""
        scorer = SemanticCoherenceScorer()
        data = RawData(
            source="test",
            content="Plain text content",
            url="http://x",
            fetched_at=datetime.now(),
            quality_hint=0.5,
        )

        text = scorer._extract_text(data)
        assert text == "Plain text content"

    def test_extract_text_from_dict(self):
        """Test text extraction from dict content."""
        scorer = SemanticCoherenceScorer()
        data = RawData(
            source="test",
            content={
                "text": "Main text",
                "title": "Title",
                "items": ["a", "b"],
            },
            url="http://x",
            fetched_at=datetime.now(),
            quality_hint=0.5,
        )

        text = scorer._extract_text(data)
        assert text == "Main text"

    def test_extract_text_priority_text_field(self):
        """Test that 'text' field is prioritized."""
        scorer = SemanticCoherenceScorer()
        data = RawData(
            source="test",
            content={"text": "Priority", "other": "Ignored"},
            url="http://x",
            fetched_at=datetime.now(),
            quality_hint=0.5,
        )

        text = scorer._extract_text(data)
        assert text == "Priority"


class TestSemanticCoherenceResult:
    """Tests for SemanticCoherenceResult dataclass."""

    def test_result_creation(self):
        """Test creating SemanticCoherenceResult."""
        result = SemanticCoherenceResult(
            score=0.75,
            similarity_to_indexed=0.82,
            is_novel=False,
            is_outlier=False,
            similar_docs_count=3,
            details={"max_similarity": 0.82},
        )

        assert result.score == 0.75
        assert result.similarity_to_indexed == 0.82
        assert result.is_novel is False
        assert result.similar_docs_count == 3
