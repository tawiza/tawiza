"""End-to-end tests for multi-source analysis feature.

Tests the complete pipeline:
1. DataOrchestrator parallel queries
2. EntityMatcher deduplication
3. DebateSystem validation
4. OrchestratedReportGenerator output
"""

import asyncio
import json
import tempfile
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_full_pipeline_integration():
    """Test complete multi-source analysis pipeline."""
    from src.application.orchestration.data_orchestrator import DataOrchestrator
    from src.application.reporting.orchestrated_report import generate_orchestrated_report
    from src.domain.debate.debate_system import DebateSystem

    # Step 1: Run orchestrated search
    orchestrator = DataOrchestrator()
    orch_result = await orchestrator.search(
        query="startup",
        sources=["google_news", "subventions"],
        limit_per_source=3,
    )

    assert orch_result.query == "startup"
    assert len(orch_result.source_results) == 2
    assert orch_result.total_duration_ms > 0

    # Step 2: Run debate validation
    debate = DebateSystem()
    debate_result = await debate.validate(
        query="startup",
        data={
            "results": [item for sr in orch_result.source_results for item in sr.results],
            "sources": [sr.source for sr in orch_result.source_results],
        },
    )

    assert len(debate_result.messages) == 3  # Chercheur, Critique, Vérificateur
    assert 0 <= debate_result.final_confidence <= 100
    assert debate_result.verdict  # Non-empty verdict

    # Step 3: Generate reports
    with tempfile.TemporaryDirectory() as tmpdir:
        outputs = await generate_orchestrated_report(
            query="startup",
            output_dir=tmpdir,
            orch_result=orch_result,
            debate_result=debate_result,
        )

        # Verify HTML report
        html_path = Path(outputs["html"])
        assert html_path.exists()
        html_content = html_path.read_text()
        assert "Rapport Multi-Source" in html_content
        assert "startup" in html_content
        assert "Score de Confiance" in html_content

        # Verify JSON export
        json_path = Path(outputs["json"])
        assert json_path.exists()
        json_data = json.loads(json_path.read_text())
        assert "confidence" in json_data
        assert "sources" in json_data
        assert "debate" in json_data


@pytest.mark.asyncio
async def test_orchestrator_with_all_sources():
    """Test DataOrchestrator queries all registered sources."""
    from src.application.orchestration.data_orchestrator import DataOrchestrator

    orchestrator = DataOrchestrator()
    result = await orchestrator.search(
        query="test",
        limit_per_source=2,
    )

    # Should have results from 8 sources
    assert len(result.source_results) == 8

    # Each source should have a result (even if empty/error)
    source_names = {sr.source for sr in result.source_results}
    expected_sources = {
        "sirene",
        "ban",
        "bodacc",
        "boamp",
        "rss",
        "gdelt",
        "google_news",
        "subventions",
    }
    assert source_names == expected_sources


@pytest.mark.asyncio
async def test_debate_validation_confidence_progression():
    """Test that debate agents properly adjust confidence."""
    from src.domain.debate.debate_system import DebateSystem

    debate = DebateSystem()

    # Test with good data (multiple sources, SIRET present)
    good_data = {
        "results": [
            {
                "source": "sirene",
                "siret": "12345678901234",
                "name": "Test Corp",
                "date": "2024-01-01",
            },
            {
                "source": "bodacc",
                "siret": "12345678901234",
                "name": "Test Corp",
                "date": "2024-01-01",
            },
            {
                "source": "google_news",
                "siret": "12345678901234",
                "name": "Test Corp",
                "published_dt": "2024-01-01",
            },
        ],
        "sources": ["sirene", "bodacc", "google_news"],
    }

    result = await debate.validate("good_test", good_data)

    # Should have reasonable confidence with good data
    assert result.final_confidence >= 40
    assert result.is_valid

    # Test with poor data (no SIRET, no dates)
    poor_data = {
        "results": [
            {"source": "unknown", "name": "Bad Data"},
        ],
        "sources": ["unknown"],
    }

    poor_result = await debate.validate("poor_test", poor_data)

    # Should have lower confidence with poor data
    assert poor_result.final_confidence < result.final_confidence


@pytest.mark.asyncio
async def test_entity_matcher_deduplication():
    """Test EntityMatcher properly groups related entities."""
    from src.domain.matching.entity_matcher import EntityMatcher

    matcher = EntityMatcher()

    entities = [
        {"siret": "12345678901234", "name": "ACME Corp", "source": "sirene"},
        {"siret": "12345678901234", "name": "ACME Corporation", "source": "bodacc"},
        {"name": "Different Company", "source": "news"},
    ]

    groups = matcher.deduplicate(entities)

    # SIRET-matched entities should be grouped
    assert len(groups) == 2  # One group for ACME, one for Different Company


@pytest.mark.asyncio
async def test_report_includes_all_sections():
    """Test generated HTML report has all required sections."""
    import tempfile

    from src.application.orchestration.data_orchestrator import DataOrchestrator
    from src.application.reporting.orchestrated_report import (
        OrchestratedReportGenerator,
        ReportConfig,
    )
    from src.domain.debate.debate_system import DebateSystem

    # Create minimal test data
    orchestrator = DataOrchestrator()
    orch_result = await orchestrator.search(
        query="test",
        sources=["subventions"],
        limit_per_source=2,
    )

    debate = DebateSystem()
    debate_result = await debate.validate(
        "test",
        {"results": [], "sources": ["test"]},
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        config = ReportConfig(output_dir=tmpdir, query="test")
        generator = OrchestratedReportGenerator(config)

        html_path = generator.generate_html_report(orch_result, debate_result)

        content = Path(html_path).read_text()

        # Check all required sections exist
        assert "Score de Confiance" in content
        assert "Sources de Données" in content
        assert "Validation Multi-Agent" in content
        assert "Points d'Attention" in content


if __name__ == "__main__":
    asyncio.run(test_full_pipeline_integration())
    print("✓ All E2E tests passed!")
