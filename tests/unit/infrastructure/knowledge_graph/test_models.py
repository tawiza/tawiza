"""Tests for Neo4j node models."""

import pytest

from src.infrastructure.knowledge_graph.models.nodes import (
    Company,
    Establishment,
    Sector,
    Territory,
)


class TestCompanyNode:
    """Test Company node model."""

    def test_create_company(self):
        """Create company with required fields."""
        company = Company(siren="123456789", name="Test Corp")
        assert company.siren == "123456789"
        assert company.name == "Test Corp"

    def test_to_cypher_properties(self):
        """Convert to Cypher properties dict."""
        company = Company(siren="123456789", name="Test Corp", naf_code="6201Z")
        props = company.to_properties()
        assert props["siren"] == "123456789"
        assert props["name"] == "Test Corp"
        assert props["naf_code"] == "6201Z"

    def test_properties_exclude_none(self):
        """None values excluded from properties."""
        company = Company(siren="123456789")
        props = company.to_properties()
        assert "name" not in props
        assert "naf_code" not in props

    def test_merge_cypher(self):
        """Generate MERGE Cypher query."""
        company = Company(siren="123456789", name="Test")
        query = company.merge_query()
        assert "MERGE (c:Company {siren: $siren})" in query


class TestEstablishmentNode:
    """Test Establishment node model."""

    def test_create_establishment(self):
        """Create establishment."""
        etab = Establishment(siret="12345678901234", siren="123456789", city="Paris")
        assert etab.siret == "12345678901234"
        assert etab.city == "Paris"

    def test_is_headquarters_default(self):
        """Default is_headquarters is False."""
        etab = Establishment(siret="12345678901234")
        assert etab.is_headquarters is False


class TestTerritoryNode:
    """Test Territory node model."""

    def test_create_territory(self):
        """Create territory."""
        territory = Territory(code="34", name="Herault", type="departement")
        assert territory.code == "34"
        assert territory.type == "departement"

    def test_default_type(self):
        """Default type is commune."""
        territory = Territory(code="34172")
        assert territory.type == "commune"


class TestSectorNode:
    """Test Sector node model."""

    def test_create_sector(self):
        """Create sector."""
        sector = Sector(naf_code="6201Z", label="Programmation informatique")
        assert sector.naf_code == "6201Z"
        assert sector.level == 5  # Default
