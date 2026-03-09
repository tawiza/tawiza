"""Tests for BAN geocoding adapter."""

import pytest

from src.infrastructure.datasources.adapters.ban import BanAdapter


@pytest.mark.asyncio
async def test_ban_geocode_address():
    """Test geocoding an address."""
    adapter = BanAdapter()
    results = await adapter.search({"address": "165 Avenue de Bretagne, 59000 Lille"})
    assert len(results) > 0
    assert "lat" in results[0]
    assert "lon" in results[0]
    assert "code_insee" in results[0]


@pytest.mark.asyncio
async def test_ban_reverse_geocode():
    """Test reverse geocoding coordinates."""
    adapter = BanAdapter()
    result = await adapter.get_by_id("50.6292,3.0573")  # Lille center
    assert result is not None
    assert "commune" in result
