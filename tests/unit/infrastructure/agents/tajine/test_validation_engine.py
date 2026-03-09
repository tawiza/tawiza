"""Tests for ValidationEngine - Anti-hallucination system."""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestValidationEngineImports:
    """Test imports."""

    def test_import_validation_engine(self):
        """Test ValidationEngine can be imported."""
        from src.infrastructure.agents.tajine.validation import ValidationEngine

        assert ValidationEngine is not None

    def test_import_validation_result(self):
        """Test ValidationResult can be imported."""
        from src.infrastructure.agents.tajine.validation.engine import ValidationResult

        assert ValidationResult is not None


class TestValidationEngineStructure:
    """Test ValidationEngine structure."""

    def test_has_source_reliability_mapping(self):
        """Test engine has source reliability scores."""
        from src.infrastructure.agents.tajine.validation import ValidationEngine

        engine = ValidationEngine()
        assert hasattr(engine, "SOURCE_RELIABILITY") or hasattr(
            ValidationEngine, "SOURCE_RELIABILITY"
        )

    def test_has_validate_method(self):
        """Test engine has validate method."""
        from src.infrastructure.agents.tajine.validation import ValidationEngine

        engine = ValidationEngine()
        assert hasattr(engine, "validate")
        assert callable(engine.validate)


class TestValidationEngine:
    """Test ValidationEngine functionality."""

    @pytest.mark.asyncio
    async def test_validate_with_sources(self):
        """Test validation against known sources."""
        from src.infrastructure.agents.tajine.validation import ValidationEngine

        engine = ValidationEngine()

        result = await engine.validate(
            {
                "claim": "There are 847 tech companies in Hérault",
                "source": "sirene_api",
                "data": {"count": 847},
            }
        )

        assert "is_valid" in result
        assert "confidence" in result
        assert "sources_checked" in result

    @pytest.mark.asyncio
    async def test_detect_hallucination(self):
        """Test detection of hallucinated data."""
        from src.infrastructure.agents.tajine.validation import ValidationEngine

        engine = ValidationEngine()

        # Claim without supporting data
        result = await engine.validate({"claim": "Growth rate is 500%", "source": None, "data": {}})

        assert result["is_valid"] == False
        assert "hallucination" in result.get("flags", [])

    @pytest.mark.asyncio
    async def test_confidence_calibration(self):
        """Test confidence is properly calibrated."""
        from src.infrastructure.agents.tajine.validation import ValidationEngine

        engine = ValidationEngine()

        # High-confidence claim (official source with matching data)
        high_conf = await engine.validate(
            {"claim": "Count is 100", "source": "official_api", "data": {"count": 100}}
        )

        # Low-confidence claim (estimated source)
        low_conf = await engine.validate(
            {"claim": "Count is approximately 100", "source": "estimated", "data": {"count": 95}}
        )

        assert high_conf["confidence"] > low_conf["confidence"]

    @pytest.mark.asyncio
    async def test_validate_returns_flags(self):
        """Test validation returns appropriate flags."""
        from src.infrastructure.agents.tajine.validation import ValidationEngine

        engine = ValidationEngine()

        result = await engine.validate(
            {"claim": "Valid claim", "source": "insee", "data": {"value": 42}}
        )

        assert "flags" in result
        assert isinstance(result["flags"], list)

    @pytest.mark.asyncio
    async def test_validate_returns_details(self):
        """Test validation returns details dict."""
        from src.infrastructure.agents.tajine.validation import ValidationEngine

        engine = ValidationEngine()

        result = await engine.validate({"claim": "Some claim", "source": "bodacc", "data": {}})

        assert "details" in result
        assert isinstance(result["details"], dict)


class TestSourceReliability:
    """Test source reliability scoring."""

    @pytest.mark.asyncio
    async def test_official_sources_high_reliability(self):
        """Test official sources get high reliability."""
        from src.infrastructure.agents.tajine.validation import ValidationEngine

        engine = ValidationEngine()

        # sirene_api should be highly reliable
        result = await engine.validate(
            {"claim": "Data from SIRENE", "source": "sirene_api", "data": {"companies": 100}}
        )

        assert result["confidence"] >= 0.7

    @pytest.mark.asyncio
    async def test_unknown_source_low_reliability(self):
        """Test unknown sources get lower reliability."""
        from src.infrastructure.agents.tajine.validation import ValidationEngine

        engine = ValidationEngine()

        result = await engine.validate({"claim": "Unverified claim", "source": None, "data": {}})

        assert result["confidence"] < 0.5


class TestKnowledgeGraph:
    """Test KnowledgeGraph functionality."""

    def test_import_knowledge_graph(self):
        """Test KnowledgeGraph can be imported."""
        from src.infrastructure.agents.tajine.validation import KnowledgeGraph

        assert KnowledgeGraph is not None

    def test_add_triple(self):
        """Test adding a triple to the graph."""
        from src.infrastructure.agents.tajine.validation import KnowledgeGraph

        kg = KnowledgeGraph()
        triple = kg.add_triple(
            subject="company:123456789",
            predicate="has_name",
            obj="Test Corp",
            source="sirene_api",
            confidence=0.95,
        )

        assert triple.subject == "company:123456789"
        assert triple.predicate == "has_name"
        assert triple.obj == "Test Corp"
        assert triple.source == "sirene_api"
        assert triple.confidence == 0.95

    def test_add_entity(self):
        """Test adding an entity with properties."""
        from src.infrastructure.agents.tajine.validation import KnowledgeGraph

        kg = KnowledgeGraph()
        triples = kg.add_entity(
            entity_type="company",
            entity_id="123456789",
            properties={"name": "Test Corp", "siren": "123456789", "city": "Paris"},
            source="sirene_api",
        )

        assert len(triples) == 3
        stats = kg.get_stats()
        assert stats["total_triples"] == 3
        assert stats["unique_subjects"] == 1

    def test_query_by_subject(self):
        """Test querying triples by subject."""
        from src.infrastructure.agents.tajine.validation import KnowledgeGraph

        kg = KnowledgeGraph()
        kg.add_entity("company", "123", {"name": "A", "city": "Paris"})
        kg.add_entity("company", "456", {"name": "B", "city": "Lyon"})

        results = kg.query(subject="company:123")
        assert len(results) == 2

    def test_query_by_predicate(self):
        """Test querying triples by predicate."""
        from src.infrastructure.agents.tajine.validation import KnowledgeGraph

        kg = KnowledgeGraph()
        kg.add_entity("company", "123", {"name": "A", "city": "Paris"})
        kg.add_entity("company", "456", {"name": "B", "city": "Lyon"})

        # 'city' normalizes to 'has_city'
        results = kg.query(predicate="has_city")
        assert len(results) == 2

    def test_get_entity(self):
        """Test getting all properties of an entity."""
        from src.infrastructure.agents.tajine.validation import KnowledgeGraph

        kg = KnowledgeGraph()
        kg.add_entity("company", "123", {"name": "Test Corp", "city": "Paris", "siren": "123"})

        entity = kg.get_entity("company", "123")
        assert entity.get("has_name") == "Test Corp"
        assert entity.get("has_city") == "Paris"
        assert entity.get("has_siren") == "123"

    def test_validate_claim_match(self):
        """Test validating a claim that matches known facts."""
        from src.infrastructure.agents.tajine.validation import KnowledgeGraph

        kg = KnowledgeGraph()
        kg.add_entity("company", "123", {"name": "Test Corp"}, source="sirene_api", confidence=0.95)

        result = kg.validate_claim(
            subject="company:123", predicate="name", claimed_value="Test Corp"
        )

        assert result.found is True
        assert len(result.matching_triples) == 1
        assert result.confidence == 0.95
        assert len(result.conflicts) == 0

    def test_validate_claim_conflict(self):
        """Test validating a claim that conflicts with known facts."""
        from src.infrastructure.agents.tajine.validation import KnowledgeGraph

        kg = KnowledgeGraph()
        kg.add_entity("company", "123", {"name": "Real Corp"}, source="sirene_api")

        result = kg.validate_claim(
            subject="company:123", predicate="name", claimed_value="Fake Corp"
        )

        assert result.found is True
        assert len(result.matching_triples) == 0
        assert len(result.conflicts) == 1
        assert result.confidence == 0.0

    def test_validate_claim_unknown(self):
        """Test validating a claim with no known facts."""
        from src.infrastructure.agents.tajine.validation import KnowledgeGraph

        kg = KnowledgeGraph()

        result = kg.validate_claim(
            subject="company:unknown", predicate="name", claimed_value="Some Corp"
        )

        assert result.found is False
        assert len(result.matching_triples) == 0
        assert result.confidence == 0.0

    def test_cross_reference(self):
        """Test cross-referencing multiple claims."""
        from src.infrastructure.agents.tajine.validation import KnowledgeGraph

        kg = KnowledgeGraph()
        kg.add_entity(
            "company",
            "123",
            {"name": "Test Corp", "city": "Paris", "siren": "123"},
            source="sirene_api",
            confidence=0.95,
        )

        results = kg.cross_reference(
            claims={"name": "Test Corp", "city": "Lyon"},  # city is wrong
            entity_type="company",
            entity_id="123",
        )

        assert "name" in results
        assert "city" in results
        assert results["name"].found is True
        assert len(results["name"].matching_triples) == 1
        assert len(results["city"].conflicts) == 1

    def test_populate_from_sirene(self):
        """Test populating graph from SIRENE API response."""
        from src.infrastructure.agents.tajine.validation import KnowledgeGraph

        kg = KnowledgeGraph()
        sirene_data = {
            "unite_legale": {
                "siren": "123456789",
                "denomination": "Test Company SAS",
                "categorie_juridique": "5710",
                "activite_principale": "62.01Z",
            }
        }

        triples = kg.populate_from_sirene(sirene_data)

        assert len(triples) >= 3
        entity = kg.get_entity("company", "123456789")
        assert entity.get("has_name") == "Test Company SAS"
        assert entity.get("has_siren") == "123456789"


class TestValidationEngineWithKnowledgeGraph:
    """Test ValidationEngine with Knowledge Graph integration."""

    @pytest.mark.asyncio
    async def test_validate_with_kg_verification(self):
        """Test validation uses KG for cross-reference."""
        from src.infrastructure.agents.tajine.validation import KnowledgeGraph, ValidationEngine

        kg = KnowledgeGraph()
        kg.add_entity(
            "company",
            "123456789",
            {"name": "Real Corp", "city": "Paris"},
            source="sirene_api",
            confidence=0.95,
        )

        engine = ValidationEngine(knowledge_graph=kg)

        result = await engine.validate(
            {
                "claim": "Company name is Real Corp",
                "source": "sirene_api",
                "data": {"name": "Real Corp"},
                "entity_type": "company",
                "entity_id": "123456789",
            }
        )

        assert result["is_valid"] is True
        assert "knowledge_graph" in result["sources_checked"]
        assert result["details"].get("kg_score", 0) > 0

    @pytest.mark.asyncio
    async def test_validate_detects_kg_conflict(self):
        """Test validation detects conflicts with KG."""
        from src.infrastructure.agents.tajine.validation import KnowledgeGraph, ValidationEngine

        kg = KnowledgeGraph()
        kg.add_entity(
            "company", "123456789", {"name": "Real Corp"}, source="sirene_api", confidence=0.95
        )

        engine = ValidationEngine(knowledge_graph=kg)

        result = await engine.validate(
            {
                "claim": "Company name is Fake Corp",
                "source": "web_scrape",
                "data": {"name": "Fake Corp"},
                "entity_type": "company",
                "entity_id": "123456789",
            }
        )

        assert result["is_valid"] is False
        assert "kg_conflict" in result["flags"]
        assert "hallucination" in result["flags"]
        assert len(result["details"].get("kg_conflicts", [])) > 0

    @pytest.mark.asyncio
    async def test_kg_boosts_confidence(self):
        """Test KG verification boosts confidence."""
        from src.infrastructure.agents.tajine.validation import KnowledgeGraph, ValidationEngine

        kg = KnowledgeGraph()
        kg.add_entity("company", "123", {"name": "Test"}, source="sirene_api", confidence=0.95)

        engine_with_kg = ValidationEngine(knowledge_graph=kg)
        engine_without_kg = ValidationEngine()

        # Same claim, with KG verification
        result_with_kg = await engine_with_kg.validate(
            {
                "claim": "Company is Test",
                "source": "web_scrape",
                "data": {"name": "Test"},
                "entity_type": "company",
                "entity_id": "123",
            }
        )

        # Same claim, without KG verification
        result_without_kg = await engine_without_kg.validate(
            {"claim": "Company is Test", "source": "web_scrape", "data": {"name": "Test"}}
        )

        # KG verification should boost confidence
        assert result_with_kg["confidence"] > result_without_kg["confidence"]

    @pytest.mark.asyncio
    async def test_shared_knowledge_graph(self):
        """Test multiple engines can share a KG."""
        from src.infrastructure.agents.tajine.validation import KnowledgeGraph, ValidationEngine

        shared_kg = KnowledgeGraph()
        shared_kg.add_entity("company", "123", {"name": "Shared Corp"})

        engine1 = ValidationEngine(knowledge_graph=shared_kg)
        engine2 = ValidationEngine(knowledge_graph=shared_kg)

        # Both engines should see the same data
        assert engine1.knowledge_graph is engine2.knowledge_graph

        result1 = await engine1.validate(
            {
                "claim": "Test",
                "source": "test",
                "data": {"name": "Shared Corp"},
                "entity_type": "company",
                "entity_id": "123",
            }
        )

        result2 = await engine2.validate(
            {
                "claim": "Test",
                "source": "test",
                "data": {"name": "Shared Corp"},
                "entity_type": "company",
                "entity_id": "123",
            }
        )

        assert result1["details"]["kg_score"] == result2["details"]["kg_score"]
