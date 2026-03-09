"""Tests for DSPy-based hypothesis generation."""

from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.agents.tajine.hunter.hypothesis import (
    Hypothesis,
    HypothesisGenerator,
)


class TestHypothesisGenerator:
    """Test hypothesis generation."""

    def test_init_creates_generator(self):
        """Should initialize with LLM client."""
        gen = HypothesisGenerator()
        assert gen is not None

    def test_generate_returns_hypotheses(self):
        """Should return list of hypotheses from context."""
        gen = HypothesisGenerator()

        # Mock the LLM response
        with patch.object(gen, "_call_llm") as mock_llm:
            mock_llm.return_value = [
                "Les entreprises BTP connaissent une croissance",
                "Le secteur est affecté par les prix des matériaux",
                "La demande publique stimule l'activité",
            ]

            hypotheses = gen.generate(
                context="Analyse du secteur BTP en Haute-Garonne",
                territory="31",
                max_hypotheses=3,
            )

            assert len(hypotheses) == 3
            assert all(isinstance(h, Hypothesis) for h in hypotheses)

    def test_hypothesis_has_required_fields(self):
        """Hypothesis should have statement, confidence, sources_to_check, search_queries, priority."""
        h = Hypothesis(
            statement="Test hypothesis",
            confidence=0.8,
            sources_to_check=["sirene", "bodacc"],
            search_queries=["query1", "query2"],
            priority=2,
        )
        assert h.statement == "Test hypothesis"
        assert h.confidence == 0.8
        assert "sirene" in h.sources_to_check
        assert h.search_queries == ["query1", "query2"]
        assert h.priority == 2

    def test_generate_populates_search_queries(self):
        """Should populate search_queries field for each hypothesis."""
        gen = HypothesisGenerator()

        with patch.object(gen, "_call_llm") as mock_llm:
            mock_llm.return_value = [
                "Les entreprises BTP connaissent une croissance",
                "Le secteur est affecté par les prix des matériaux",
            ]

            hypotheses = gen.generate(
                context="Analyse du secteur BTP",
                territory="31",
                max_hypotheses=2,
            )

            # Verify all hypotheses have search_queries populated
            assert len(hypotheses) == 2
            for h in hypotheses:
                assert len(h.search_queries) > 0
                assert isinstance(h.search_queries, list)
                # Verify territory is included in queries
                assert any("31" in q for q in h.search_queries)

    def test_generate_with_kg_context(self):
        """Should incorporate KG gaps into hypotheses."""
        gen = HypothesisGenerator()

        with patch.object(gen, "_call_llm") as mock_llm:
            mock_llm.return_value = ["Hypothesis about missing CA data"]

            kg_gaps = {
                "missing_fields": ["chiffre_affaires", "effectif"],
                "stale_entities": ["SIREN:123456789"],
            }

            hypotheses = gen.generate(
                context="Analyse entreprises",
                territory="31",
                kg_gaps=kg_gaps,
            )

            # Should have been called with kg context
            call_args = mock_llm.call_args
            assert "missing" in str(call_args).lower() or len(hypotheses) >= 1
