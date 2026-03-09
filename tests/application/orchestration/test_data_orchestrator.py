"""Tests for DataOrchestrator."""

import pytest

from src.application.orchestration.data_orchestrator import DataOrchestrator


@pytest.mark.asyncio
async def test_orchestrator_search():
    """Test orchestrated search across sources."""
    orchestrator = DataOrchestrator()
    result = await orchestrator.search(
        "startup",
        sources=["google_news"],
        limit_per_source=3,
    )
    assert result.query == "startup"
    assert len(result.source_results) == 1
    assert result.total_duration_ms > 0


@pytest.mark.asyncio
async def test_orchestrator_to_dict():
    """Test result serialization."""
    orchestrator = DataOrchestrator()
    result = await orchestrator.search(
        "test",
        sources=["subventions"],
        limit_per_source=2,
    )
    data = result.to_dict()
    assert "query" in data
    assert "timestamp" in data
    assert "sources" in data
