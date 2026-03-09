"""Tests for TAJINE TerritorialExpertRouter."""

import pytest

from src.infrastructure.agents.tajine.learning.expert_router import (
    ExpertDomain,
    MixLoRAConfig,
    RoutingResult,
    TerritorialExpertRouter,
    get_expert_router,
)


class TestExpertDomain:
    """Tests for ExpertDomain enum."""

    def test_all_domains_exist(self):
        """Test all expected domains exist."""
        expected = [
            "immobilier",
            "emploi",
            "entreprises",
            "finances_locales",
            "demographie",
            "infrastructure",
        ]
        for domain in expected:
            assert ExpertDomain(domain) is not None

    def test_domain_values(self):
        """Test domain string values."""
        assert ExpertDomain.IMMOBILIER.value == "immobilier"
        assert ExpertDomain.EMPLOI.value == "emploi"
        assert ExpertDomain.ENTREPRISES.value == "entreprises"


class TestMixLoRAConfig:
    """Tests for MixLoRAConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = MixLoRAConfig()
        assert config.num_experts == 6
        assert config.top_k == 2
        assert config.lora_rank == 8
        assert config.router_type == "top_k"

    def test_custom_config(self):
        """Test custom configuration."""
        config = MixLoRAConfig(
            num_experts=8,
            top_k=3,
            lora_rank=16,
        )
        assert config.num_experts == 8
        assert config.top_k == 3
        assert config.lora_rank == 16

    def test_to_dict(self):
        """Test config serialization."""
        config = MixLoRAConfig()
        data = config.to_dict()
        assert "num_experts" in data
        assert "top_k" in data
        assert "lora_rank" in data
        assert "auxiliary_loss_weight" in data


class TestRoutingResult:
    """Tests for RoutingResult."""

    def test_routing_result_creation(self):
        """Test creating routing result."""
        result = RoutingResult(
            activated_experts=[ExpertDomain.ENTREPRISES, ExpertDomain.EMPLOI],
            expert_weights={
                ExpertDomain.ENTREPRISES: 0.8,
                ExpertDomain.EMPLOI: 0.5,
            },
            detected_keywords=["société", "emploi"],
            confidence=0.75,
            routing_reason="Keywords detected",
        )
        assert len(result.activated_experts) == 2
        assert result.confidence == 0.75

    def test_routing_result_to_dict(self):
        """Test result serialization."""
        result = RoutingResult(
            activated_experts=[ExpertDomain.IMMOBILIER],
            expert_weights={ExpertDomain.IMMOBILIER: 0.9},
            detected_keywords=["maison"],
            confidence=0.85,
            routing_reason="Real estate query",
        )
        data = result.to_dict()
        assert data["activated_experts"] == ["immobilier"]
        assert data["confidence"] == 0.85
        assert "maison" in data["detected_keywords"]


class TestTerritorialExpertRouter:
    """Tests for TerritorialExpertRouter."""

    @pytest.fixture
    def router(self):
        """Create router instance."""
        return TerritorialExpertRouter()

    def test_initialization(self, router):
        """Test router initialization."""
        assert len(router.domain_to_index) == 6
        assert len(router.stats) == 6
        assert all(s.activation_count == 0 for s in router.stats.values())

    def test_keyword_index_built(self, router):
        """Test keyword index is built."""
        assert len(router.keyword_to_domains) > 0
        # Check some expected mappings
        assert ExpertDomain.IMMOBILIER in router.keyword_to_domains.get("maison", [])
        assert ExpertDomain.EMPLOI in router.keyword_to_domains.get("travail", [])

    def test_detect_immobilier(self, router):
        """Test detecting real estate domain."""
        domains, scores, keywords = router.detect_domains(
            "Analyse du prix des appartements à Paris"
        )
        assert ExpertDomain.IMMOBILIER in domains
        assert any(kw in keywords for kw in ["prix", "appartements"])

    def test_detect_emploi(self, router):
        """Test detecting employment domain."""
        domains, scores, keywords = router.detect_domains("Évolution du chômage et offres d'emploi")
        assert ExpertDomain.EMPLOI in domains
        assert any(kw in keywords for kw in ["chômage", "emploi"])

    def test_detect_entreprises(self, router):
        """Test detecting business domain."""
        domains, scores, keywords = router.detect_domains("Création d'entreprises et SIRET actifs")
        assert ExpertDomain.ENTREPRISES in domains

    def test_detect_finances(self, router):
        """Test detecting local finances domain."""
        domains, scores, keywords = router.detect_domains("Budget de la commune et impôts locaux")
        assert ExpertDomain.FINANCES_LOCALES in domains

    def test_detect_demographie(self, router):
        """Test detecting demographics domain."""
        domains, scores, keywords = router.detect_domains(
            "Population et vieillissement de la région"
        )
        assert ExpertDomain.DEMOGRAPHIE in domains

    def test_detect_infrastructure(self, router):
        """Test detecting infrastructure domain."""
        domains, scores, keywords = router.detect_domains("État des écoles et hôpitaux")
        assert ExpertDomain.INFRASTRUCTURE in domains

    def test_detect_multiple_domains(self, router):
        """Test detecting multiple domains."""
        domains, scores, keywords = router.detect_domains(
            "Impact de la création d'entreprises sur l'emploi local"
        )
        # Should detect both entreprises and emploi
        assert len(domains) >= 2

    def test_default_domain(self, router):
        """Test default domain when no keywords match."""
        domains, scores, keywords = router.detect_domains(
            "Question générique sans mots-clés spécifiques xyz123"
        )
        # Should default to entreprises
        assert ExpertDomain.ENTREPRISES in domains

    def test_context_boost_sector(self, router):
        """Test context boost from sector."""
        domains, scores, _ = router.detect_domains(
            "Analyse du marché",
            context={"sector": "6820B"},  # Real estate NAF code
        )
        # Should boost immobilier due to sector
        assert ExpertDomain.IMMOBILIER in domains

    def test_context_boost_source(self, router):
        """Test context boost from data source."""
        domains, scores, _ = router.detect_domains(
            "Données disponibles",
            context={"data_source": "DVF"},
        )
        # DVF is a real estate source
        assert ExpertDomain.IMMOBILIER in domains

    def test_route_returns_result(self, router):
        """Test routing returns proper result."""
        result = router.route("Prix de l'immobilier")
        assert isinstance(result, RoutingResult)
        assert len(result.activated_experts) >= 1
        assert 0.0 <= result.confidence <= 1.0

    def test_route_updates_stats(self, router):
        """Test routing updates statistics."""
        initial_count = router.stats[ExpertDomain.IMMOBILIER].activation_count
        router.route("Prix des maisons")
        assert router.stats[ExpertDomain.IMMOBILIER].activation_count > initial_count

    def test_get_expert_indices(self, router):
        """Test converting domains to indices."""
        domains = [ExpertDomain.IMMOBILIER, ExpertDomain.EMPLOI]
        indices = router.get_expert_indices(domains)
        assert len(indices) == 2
        assert all(isinstance(i, int) for i in indices)

    def test_add_training_example(self, router):
        """Test adding training examples."""
        initial_count = router.stats[ExpertDomain.IMMOBILIER].training_examples
        router.add_training_example(
            ExpertDomain.IMMOBILIER,
            {"query": "Test", "response": "Answer"},
        )
        assert router.stats[ExpertDomain.IMMOBILIER].training_examples == initial_count + 1
        assert len(router.training_queues[ExpertDomain.IMMOBILIER]) == 1

    def test_get_training_ready_domains(self, router):
        """Test getting domains ready for training."""
        # Add examples to one domain
        for i in range(60):
            router.add_training_example(
                ExpertDomain.EMPLOI,
                {"query": f"Query {i}"},
            )

        ready = router.get_training_ready_domains(min_examples=50)
        assert ExpertDomain.EMPLOI in ready
        assert ExpertDomain.IMMOBILIER not in ready

    def test_get_training_data(self, router):
        """Test getting training data."""
        router.add_training_example(ExpertDomain.ENTREPRISES, {"data": 1})
        router.add_training_example(ExpertDomain.ENTREPRISES, {"data": 2})

        data = router.get_training_data(ExpertDomain.ENTREPRISES)
        assert len(data) == 2

    def test_clear_training_queue(self, router):
        """Test clearing training queue."""
        router.add_training_example(ExpertDomain.DEMOGRAPHIE, {"test": True})
        router.add_training_example(ExpertDomain.DEMOGRAPHIE, {"test": True})

        cleared = router.clear_training_queue(ExpertDomain.DEMOGRAPHIE)
        assert cleared == 2
        assert len(router.training_queues[ExpertDomain.DEMOGRAPHIE]) == 0

    def test_get_stats(self, router):
        """Test getting router statistics."""
        router.route("Test immobilier maison")
        router.route("Test emploi travail")

        stats = router.get_stats()
        assert stats["total_activations"] >= 2
        assert "experts" in stats
        assert "config" in stats

    def test_get_expert_info(self, router):
        """Test getting expert information."""
        info = router.get_expert_info(ExpertDomain.IMMOBILIER)
        assert info["domain"] == "immobilier"
        assert "description" in info
        assert "keywords" in info
        assert "data_sources" in info

    def test_top_k_limiting(self, router):
        """Test that routing respects top_k."""
        router.config.top_k = 2
        result = router.route(
            "Analyse complète: immobilier, emploi, entreprises, budget, population, écoles"
        )
        # Should activate at most top_k experts
        assert len(result.activated_experts) <= 2


class TestGetExpertRouter:
    """Tests for singleton getter."""

    def test_singleton_pattern(self):
        """Test singleton returns same instance."""
        router1 = get_expert_router()
        router2 = get_expert_router()
        assert router1 is router2
