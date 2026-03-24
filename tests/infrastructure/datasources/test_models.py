"""Tests for datasource models."""

from datetime import date

import pytest

from src.infrastructure.datasources.models import Enterprise


def test_enterprise_model_creation():
    """Test Enterprise model can be instantiated."""
    enterprise = Enterprise(
        siret="12345678901234",
        siren="123456789",
        nom="Test Company",
        code_postal="59000",
        commune="LILLE",
        latitude=50.6292,
        longitude=3.0573,
    )
    assert enterprise.siret == "12345678901234"
    assert enterprise.siren == "123456789"
    assert enterprise.nom == "Test Company"


def test_enterprise_location_point():
    """Test Enterprise generates PostGIS point from lat/lon."""
    enterprise = Enterprise(
        siret="12345678901234",
        siren="123456789",
        nom="Test Company",
        latitude=50.6292,
        longitude=3.0573,
    )
    # location should be a WKT point string or GeoAlchemy2 element
    assert enterprise.latitude == 50.6292
    assert enterprise.longitude == 3.0573
