"""Tests for Data.gouv Subventions adapter."""

import pytest

from src.infrastructure.datasources.adapters.subventions import SubventionsAdapter


@pytest.mark.asyncio
async def test_subventions_health_check():
    """Test Data.gouv API health check."""
    adapter = SubventionsAdapter()
    healthy = await adapter.health_check()
    assert healthy is True


@pytest.mark.asyncio
async def test_subventions_search_by_beneficiary():
    """Test searching subventions by beneficiary name."""
    adapter = SubventionsAdapter()
    results = await adapter.search(
        {
            "beneficiary": "commune",
            "limit": 5,
        }
    )
    # May return 0 results depending on data availability
    assert isinstance(results, list)
