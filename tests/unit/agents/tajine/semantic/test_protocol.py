"""Tests for VectorStoreProtocol and SemanticResult."""

from datetime import datetime

import pytest

from src.infrastructure.agents.tajine.semantic.protocol import (
    SemanticResult,
    VectorStoreProtocol,
)


class TestSemanticResult:
    """Tests for SemanticResult dataclass."""

    def test_basic_creation(self):
        """Test creating a SemanticResult with required fields."""
        result = SemanticResult(
            id="doc1",
            content="Test content",
            score=0.85,
        )
        assert result.id == "doc1"
        assert result.content == "Test content"
        assert result.score == 0.85
        assert result.source_store == "unknown"
        assert result.metadata == {}

    def test_with_metadata(self):
        """Test creating SemanticResult with metadata."""
        result = SemanticResult(
            id="doc2",
            content="Company info",
            score=0.72,
            metadata={"territory": "31", "source": "sirene"},
            source_store="pgvector",
        )
        assert result.metadata["territory"] == "31"
        assert result.source_store == "pgvector"

    def test_to_raw_data_dict(self):
        """Test conversion to RawData-compatible dict."""
        result = SemanticResult(
            id="doc3",
            content="BTP Toulouse data",
            score=0.9,
            metadata={"source": "bodacc"},
            source_store="qdrant",
        )
        raw_dict = result.to_raw_data_dict()

        assert raw_dict["source"] == "bodacc"
        assert raw_dict["content"]["text"] == "BTP Toulouse data"
        assert raw_dict["content"]["semantic_score"] == 0.9
        assert raw_dict["quality_hint"] == 0.9
        assert "semantic://qdrant/doc3" in raw_dict["url"]

    def test_fetched_at_default(self):
        """Test that fetched_at defaults to now."""
        before = datetime.now()
        result = SemanticResult(id="x", content="y", score=0.5)
        after = datetime.now()

        assert before <= result.fetched_at <= after


class TestVectorStoreProtocol:
    """Tests for VectorStoreProtocol abstract interface."""

    def test_is_abstract(self):
        """Test that VectorStoreProtocol cannot be instantiated."""
        with pytest.raises(TypeError):
            VectorStoreProtocol()  # type: ignore

    def test_subclass_must_implement_methods(self):
        """Test that subclass must implement all abstract methods."""
        # This just verifies the protocol exists with correct methods
        assert hasattr(VectorStoreProtocol, "name")
        assert hasattr(VectorStoreProtocol, "connect")
        assert hasattr(VectorStoreProtocol, "close")
        assert hasattr(VectorStoreProtocol, "health_check")
        assert hasattr(VectorStoreProtocol, "index")
        assert hasattr(VectorStoreProtocol, "search")
        assert hasattr(VectorStoreProtocol, "delete")
        assert hasattr(VectorStoreProtocol, "count")
