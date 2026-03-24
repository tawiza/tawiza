"""Tests for EntityMatcher."""

import pytest

from src.domain.matching.entity_matcher import EntityMatcher, MatchResult


def test_exact_siret_match():
    """Test exact SIRET matching."""
    matcher = EntityMatcher()

    entity1 = {"siret": "12345678901234", "name": "ACME Corp"}
    entity2 = {"siret": "12345678901234", "name": "Acme Corporation"}

    result = matcher.match(entity1, entity2)
    assert result.is_match is True
    assert result.confidence >= 95  # High confidence for SIRET match
    assert "siret" in result.match_reasons


def test_fuzzy_name_match():
    """Test fuzzy name matching."""
    matcher = EntityMatcher()

    entity1 = {"name": "Société ACME France"}
    entity2 = {"name": "ACME France SARL"}

    result = matcher.match(entity1, entity2)
    assert result.confidence > 70  # Good confidence for similar names


def test_no_match():
    """Test entities that don't match."""
    matcher = EntityMatcher()

    entity1 = {"siret": "11111111111111", "name": "Company A"}
    entity2 = {"siret": "22222222222222", "name": "Company B"}

    result = matcher.match(entity1, entity2)
    assert result.is_match is False
    assert result.confidence < 50


def test_find_matches_in_collection():
    """Test finding matches in a collection."""
    matcher = EntityMatcher()

    target = {"siret": "12345678901234", "name": "ACME Corp"}
    candidates = [
        {"siret": "12345678901234", "name": "Acme Corporation"},
        {"siret": "99999999999999", "name": "Other Company"},
        {"name": "ACME France"},  # Similar name, no SIRET
    ]

    matches = matcher.find_matches(target, candidates)
    assert len(matches) >= 1
    assert matches[0].confidence >= 90  # Best match should be high confidence
