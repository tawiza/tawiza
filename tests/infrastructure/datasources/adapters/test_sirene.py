"""Tests for INSEE Sirene adapter."""

import pytest

from src.infrastructure.datasources.adapters.sirene import SireneAdapter


@pytest.mark.asyncio
async def test_sirene_health_check():
    """Test Sirene API health check."""
    adapter = SireneAdapter()
    healthy = await adapter.health_check()
    assert healthy is True


@pytest.mark.asyncio
async def test_sirene_search_by_name():
    """Test searching enterprises by name."""
    adapter = SireneAdapter()
    results = await adapter.search({"nom": "Orange", "limit": 5})
    assert len(results) > 0
    assert "siret" in results[0]
    assert "nom" in results[0]


@pytest.mark.asyncio
async def test_sirene_get_by_siret():
    """Test getting enterprise by SIRET."""
    adapter = SireneAdapter()
    # Orange SA SIRET
    result = await adapter.get_by_id("38012986646239")
    assert result is not None
    assert result["siret"] == "38012986646239"
