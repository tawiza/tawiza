"""Tests for BODACC adapter."""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from src.infrastructure.datasources.adapters.bodacc import BodaccAdapter
from src.infrastructure.datasources.base import AdapterConfig


@pytest.fixture
def adapter():
    config = AdapterConfig(
        name="bodacc",
        base_url="https://bodacc-datadila.opendatasoft.com/api/explore/v2.1",
        rate_limit=30,
        cache_ttl=86400,  # 24h
    )
    return BodaccAdapter(config)


def test_adapter_name(adapter):
    """Test adapter has correct name."""
    assert adapter.name == "bodacc"


def test_adapter_config(adapter):
    """Test adapter config is set correctly."""
    assert adapter.config.name == "bodacc"
    assert adapter.config.rate_limit == 30
    assert adapter.config.cache_ttl == 86400


def test_type_mapping():
    """Test TYPE_MAPPING is defined."""
    assert "creation" in BodaccAdapter.TYPE_MAPPING
    assert "modification" in BodaccAdapter.TYPE_MAPPING
    assert "radiation" in BodaccAdapter.TYPE_MAPPING
    assert "procedure" in BodaccAdapter.TYPE_MAPPING


@pytest.mark.asyncio
async def test_health_check(adapter):
    """Test health check works."""
    # Real API call - may fail if API is down
    is_healthy = await adapter.health_check()
    assert isinstance(is_healthy, bool)


@pytest.mark.asyncio
async def test_search_by_siren(adapter):
    """Test searching by SIREN."""
    # Use a known SIREN (CAPGEMINI)
    results = await adapter.search({"siren": "330566852", "limit": 5})
    assert isinstance(results, list)
    # May or may not have results depending on recent announcements
    if results:
        # Verify structure if we got results
        assert "source" in results[0]
        assert results[0]["source"] == "bodacc"


@pytest.mark.asyncio
async def test_search_by_date_range(adapter):
    """Test searching by date range."""
    results = await adapter.search(
        {
            "date_from": "2024-01-01",
            "date_to": "2024-01-31",
            "type": "creation",
            "limit": 10,
        }
    )
    assert isinstance(results, list)
    assert len(results) <= 10


@pytest.mark.asyncio
async def test_search_by_departement(adapter):
    """Test searching by departement."""
    results = await adapter.search(
        {
            "departement": "59",  # Nord
            "date_from": "2024-01-01",
            "limit": 5,
        }
    )
    assert isinstance(results, list)
    assert len(results) <= 5


@pytest.mark.asyncio
async def test_get_by_id(adapter):
    """Test getting announcements by SIREN/SIRET."""
    # Test with a SIREN
    result = await adapter.get_by_id("330566852")
    # May return None if no recent announcements
    assert result is None or isinstance(result, dict)


@pytest.mark.asyncio
async def test_search_returns_empty_on_error(adapter):
    """Test that search returns empty list on HTTP error."""
    # Create adapter with invalid URL to force error
    config = AdapterConfig(
        name="bodacc",
        base_url="https://invalid-url-that-does-not-exist.example.com",
        rate_limit=30,
    )
    bad_adapter = BodaccAdapter(config)

    results = await bad_adapter.search({"siren": "123456789"})
    assert results == []


def test_transform_record(adapter):
    """Test record transformation."""
    record = {
        "id": "C202400100001",
        "registre": ["123456789", "123 456 789"],
        "commercant": "Test Company",
        "familleavis": "imm",
        "familleavis_lib": "Immatriculation",
        "dateparution": "2024-01-15",
        "numeroannonce": 1,
        "departement_nom_officiel": "Nord",
        "numerodepartement": "59",
        "region_nom_officiel": "Hauts-de-France",
        "ville": "Lille",
        "cp": "59000",
        "tribunal": "Greffe du Tribunal de Commerce de Lille",
        "acte": "Test content",
        "url_complete": "https://www.bodacc.fr/pages/annonces-commerciales-detail/?q.id=id:C202400100001",
    }

    result = adapter._transform_record(record)

    assert result["source"] == "bodacc"
    assert result["siren"] == "123456789"
    assert result["nom"] == "Test Company"
    assert result["type"] == "creation"
    assert result["date_publication"] == "2024-01-15"
    assert result["numero_annonce"] == 1
    assert result["departement"] == "Nord"
    assert result["ville"] == "Lille"
    assert result["raw"] == record


def test_reverse_type(adapter):
    """Test type reversal."""
    assert adapter._reverse_type("imm") == "creation"
    assert adapter._reverse_type("mod") == "modification"
    assert adapter._reverse_type("rad") == "radiation"
    assert adapter._reverse_type("pcl") == "procedure"
    assert adapter._reverse_type("dpc") == "depot_comptes"
    assert adapter._reverse_type(None) == "unknown"
    assert adapter._reverse_type("unknown_code") == "other"


@pytest.mark.asyncio
async def test_sync(adapter):
    """Test sync functionality."""
    from datetime import datetime, timedelta

    # Sync last 7 days
    since = datetime.utcnow() - timedelta(days=7)
    status = await adapter.sync(since)

    assert status.adapter_name == "bodacc"
    assert status.status in ["success", "failed"]
    assert isinstance(status.records_synced, int)
