"""End-to-end tests for the tawiza analyze command.

Tests the full analysis pipeline including:
- Query parsing
- Sirene API search
- Web enrichment
- Output generation
"""

import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest


class TestQueryParser:
    """Tests for the intelligent query parser."""

    @pytest.fixture
    def parser(self):
        from src.infrastructure.agents.camel.services.query_parser import QueryParser

        return QueryParser(use_llm_fallback=False)

    @pytest.mark.asyncio
    async def test_parse_tech_query(self, parser):
        """Test parsing a tech-related query."""
        result = await parser.parse("startups IA Lille")

        assert result.original == "startups IA Lille"
        assert len(result.keywords) > 0
        assert len(result.naf_codes) > 0
        assert result.region == "32"  # Hauts-de-France
        assert len(result.search_strategies) > 0

    @pytest.mark.asyncio
    async def test_parse_consulting_query(self, parser):
        """Test parsing a consulting-related query."""
        result = await parser.parse("conseil informatique Paris")

        assert "conseil" in result.keywords or "informatique" in result.keywords
        assert result.region == "11"  # Île-de-France

    @pytest.mark.asyncio
    async def test_parse_with_region_mapping(self, parser):
        """Test region extraction from query."""
        queries_regions = [
            ("entreprises Lyon", "84"),  # Auvergne-Rhône-Alpes
            ("startups Marseille", "93"),  # PACA
            ("conseil Bordeaux", "75"),  # Nouvelle-Aquitaine
            ("tech Toulouse", "76"),  # Occitanie
        ]

        for query, expected_region in queries_regions:
            result = await parser.parse(query)
            assert result.region == expected_region, f"Failed for {query}"

    @pytest.mark.asyncio
    async def test_naf_code_extraction(self, parser):
        """Test NAF code extraction from domain keywords."""
        result = await parser.parse("cybersécurité")

        # Cybersecurity maps to NAF codes like 62.02A (SSII) etc.
        assert len(result.naf_codes) > 0
        assert any("62" in code for code in result.naf_codes)  # IT services


class TestEnrichmentService:
    """Tests for the web enrichment service."""

    @pytest.fixture
    def service(self):
        from src.infrastructure.agents.camel.services.skyvern_enrichment import (
            SkyvernEnrichmentService,
        )

        return SkyvernEnrichmentService(max_concurrent=1, use_playwright=False)

    @pytest.mark.asyncio
    async def test_url_guessing(self, service):
        """Test URL guessing from company name."""
        # Test with a well-known company
        url = await service._guess_url("Capgemini")
        assert url is not None
        assert "capgemini" in url.lower()

    @pytest.mark.asyncio
    async def test_url_guessing_with_suffix(self, service):
        """Test URL guessing removes company suffixes."""
        url = await service._guess_url("Example SAS France")
        # Should try example.fr, example.com etc.

    @pytest.mark.asyncio
    async def test_extract_from_real_site(self, service):
        """Test data extraction from a real website."""
        # Use a site known to have good structured data
        url = "https://www.ovhcloud.com/fr/"
        data = await service._extract_with_http(url, "OVH")

        assert data.get("description") is not None
        assert len(data.get("description", "")) > 20

    @pytest.mark.asyncio
    async def test_extract_technologies(self, service):
        """Test technology detection from website."""
        data = await service._extract_with_http("https://www.wordpress.org", "WordPress")

        # Should detect wordpress in technologies
        assert "wordpress" in data.get("technologies", [])

    @pytest.mark.asyncio
    async def test_quality_score_calculation(self, service):
        """Test enrichment quality score is calculated correctly."""
        enterprise = {
            "siret": "12345678901234",
            "nom": "Test Company",
            "adresse": {"commune": "PARIS"},
        }

        result = await service.enrich_company(enterprise)

        # Score should be 0-1
        assert 0 <= result.enrichment_quality <= 1


class TestOutputPipeline:
    """Tests for the output generation pipeline."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test outputs."""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture
    def sample_enterprises(self):
        return [
            {
                "siret": "12345678901234",
                "nom": "Test Enterprise 1",
                "activite": "Conseil informatique",
                "effectif": "10",
                "adresse": {
                    "rue": "1 rue Test",
                    "code_postal": "75001",
                    "commune": "PARIS",
                },
                "geo": {"lat": 48.8566, "lon": 2.3522},
            },
            {
                "siret": "98765432109876",
                "nom": "Test Enterprise 2",
                "activite": "Développement logiciel",
                "effectif": "50",
                "adresse": {
                    "rue": "2 avenue Example",
                    "code_postal": "69001",
                    "commune": "LYON",
                },
                "geo": {"lat": 45.7640, "lon": 4.8357},
            },
        ]

    @pytest.mark.asyncio
    async def test_generate_all_outputs(self, temp_dir, sample_enterprises):
        """Test all output generation."""
        from src.infrastructure.agents.camel.services.output_pipeline import generate_all_outputs

        outputs = await generate_all_outputs(
            enterprises=sample_enterprises,
            query="test query",
            output_dir=temp_dir,
            formats=["csv", "md"],
        )

        # Should have csv and md outputs
        assert "csv" in outputs or "md" in outputs

        # At least one file should exist
        for fmt, path in outputs.items():
            if path:
                assert Path(path).exists(), f"{fmt} file should exist"

    @pytest.mark.asyncio
    async def test_generate_with_enrichments(self, temp_dir, sample_enterprises):
        """Test output generation with enrichment data."""
        from src.infrastructure.agents.camel.services.enrichment_service import EnrichmentResult
        from src.infrastructure.agents.camel.services.output_pipeline import generate_all_outputs

        # Mock enrichments using proper EnrichmentResult objects
        enrichments = [
            EnrichmentResult(
                siret="12345678901234",
                nom="Test Enterprise 1",
                url_found="https://example.com",
                description="Test description",
                enrichment_quality=0.5,
            )
        ]

        outputs = await generate_all_outputs(
            enterprises=sample_enterprises,
            query="test query",
            output_dir=temp_dir,
            enrichments=enrichments,
            formats=["csv", "jsonl", "md"],
        )

        # Should have outputs
        assert len(outputs) > 0


class TestAnalyzeCommandE2E:
    """End-to-end tests for the full analyze command."""

    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary output directory."""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_quick_analysis(self, temp_output_dir):
        """Test quick analysis mode (no enrichment)."""
        from src.infrastructure.agents.camel.cli.analyze_command import _quick_analysis

        result = await _quick_analysis(
            query="conseil informatique",
            output_dir=temp_output_dir,
            limit=5,
            verbose=False,
        )

        assert result.get("success") is True
        assert result.get("enterprises_count", 0) >= 0

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_standard_analysis(self, temp_output_dir):
        """Test standard analysis mode (with map)."""
        from src.infrastructure.agents.camel.cli.analyze_command import _standard_analysis

        result = await _standard_analysis(
            query="logiciel Lyon",
            output_dir=temp_output_dir,
            limit=3,
            verbose=False,
        )

        assert result.get("success") is True
        # Map should be generated if enterprises have geo data
        outputs = result.get("outputs", {})
        if result.get("enterprises_count", 0) > 0:
            # Outputs should include at least CSV
            assert "csv" in outputs or "md" in outputs

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_full_analysis_with_enrichment(self, temp_output_dir):
        """Test full analysis mode with web enrichment."""
        from src.infrastructure.agents.camel.cli.analyze_command import _full_analysis

        result = await _full_analysis(
            query="développement web Nantes",
            output_dir=temp_output_dir,
            limit=2,
            verbose=False,
        )

        assert result.get("success") is True
        # Should have enrichments list (even if empty)
        assert "enrichments" in result
        # Should have parsed query info
        assert "parsed_query" in result


class TestTerritorialWorkforce:
    """Tests for the Camel AI multi-agent workforce."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_workforce_initialization(self):
        """Test TerritorialWorkforce can be initialized."""
        from src.infrastructure.agents.camel.workforce.territorial_workforce import (
            TerritorialWorkforce,
        )

        workforce = TerritorialWorkforce(
            model_id="qwen3:14b",
            enable_web_enrichment=False,
        )

        assert workforce.data_agent is not None
        assert workforce.geo_agent is not None
        assert workforce.analyst_agent is not None

    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.skip(reason="Multi-agent analysis is slow (>60s)")
    async def test_workforce_analyze_market(self):
        """Test multi-agent market analysis (slow)."""
        import tempfile

        from src.infrastructure.agents.camel.workforce.territorial_workforce import (
            TerritorialWorkforce,
        )

        workforce = TerritorialWorkforce(
            model_id="qwen3:14b",
            enable_web_enrichment=False,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            result = await workforce.analyze_market(
                query="test conseil Lille",
                output_dir=temp_dir,
            )

            assert result.get("success") is True


# Pytest configuration
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "not slow"])
