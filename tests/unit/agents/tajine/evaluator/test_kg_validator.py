"""Tests for KGValidator - Knowledge Graph coherence checker."""

from datetime import UTC, datetime, timezone

import pytest

from src.infrastructure.agents.tajine.core.types import RawData
from src.infrastructure.agents.tajine.evaluator.kg_validator import (
    CoherenceIssue,
    KGValidator,
)


@pytest.fixture
def validator():
    """Create a KGValidator without Neo4j."""
    return KGValidator()


@pytest.fixture
def sample_data():
    """Create sample RawData for testing."""
    return RawData(
        source="sirene",
        content={"text": "Entreprise SIREN 123456782 créée en 2020 à Paris 75001"},
        url="https://api.sirene.fr/test",
        fetched_at=datetime.now(UTC),
        quality_hint=0.8,
    )


class TestKGValidator:
    """Tests for KGValidator."""

    @pytest.mark.asyncio
    async def test_check_returns_float(self, validator, sample_data):
        """check() should return a float score."""
        score = await validator.check(sample_data)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_validate_returns_coherence_check(self, validator, sample_data):
        """validate() should return CoherenceCheck with details."""
        result = await validator.validate(sample_data)
        assert hasattr(result, "passed")
        assert hasattr(result, "score")
        assert hasattr(result, "issues")
        assert hasattr(result, "details")

    @pytest.mark.asyncio
    async def test_valid_siren_passes_pattern_check(self, validator):
        """Valid SIREN should pass pattern validation."""
        # 123456782 has valid Luhn checksum
        data = RawData(
            source="sirene",
            content={"siren": "SIREN 123456782"},
            url="https://api.sirene.fr/test",
            fetched_at=datetime.now(UTC),
            quality_hint=0.8,
        )
        result = await validator.validate(data)
        pattern_issues = [i for i in result.issues if i == CoherenceIssue.PATTERN_VIOLATION]
        assert len(pattern_issues) == 0

    @pytest.mark.asyncio
    async def test_invalid_siren_fails_pattern_check(self, validator):
        """Invalid SIREN should fail pattern validation."""
        # 123456789 does NOT have valid Luhn checksum
        data = RawData(
            source="sirene",
            content={"siren": "SIREN 123456789"},
            url="https://api.sirene.fr/test",
            fetched_at=datetime.now(UTC),
            quality_hint=0.8,
        )
        result = await validator.validate(data)
        pattern_issues = [i for i in result.issues if i == CoherenceIssue.PATTERN_VIOLATION]
        assert len(pattern_issues) > 0

    @pytest.mark.asyncio
    async def test_implausible_data_flagged(self, validator):
        """Implausible data should be flagged."""
        data = RawData(
            source="unknown",
            content={"text": "Entreprise créée en 2099 avec -50 salariés"},
            url="https://example.com",
            fetched_at=datetime.now(UTC),
            quality_hint=0.5,
        )
        result = await validator.validate(data)
        # Should have plausibility issues
        assert result.score < 1.0

    @pytest.mark.asyncio
    async def test_no_neo4j_uses_fallback(self, validator, sample_data):
        """Without Neo4j, should use fallback scoring."""
        result = await validator.validate(sample_data)
        # Should still produce valid score
        assert 0.0 <= result.score <= 1.0

    def test_luhn_validation_siren(self, validator):
        """Test SIREN Luhn validation."""
        # Valid SIRENs
        assert validator._is_valid_siren("123456782")
        assert validator._is_valid_siren("552032534")  # EDF's SIREN

        # Invalid SIRENs
        assert not validator._is_valid_siren("123456789")
        # Note: 000000000 passes Luhn (sum=0, 0%10=0) but is not a real SIREN

    def test_luhn_validation_siret(self, validator):
        """Test SIRET Luhn validation."""
        # Format check
        assert not validator._is_valid_siret("12345")  # Too short
        assert not validator._is_valid_siret("1234567890123456")  # Too long

    @pytest.mark.asyncio
    async def test_content_without_patterns_neutral_score(self, validator):
        """Content without patterns should get neutral score."""
        data = RawData(
            source="blog",
            content={"text": "This is just some text without any business identifiers."},
            url="https://blog.example.com",
            fetched_at=datetime.now(UTC),
            quality_hint=0.5,
        )
        result = await validator.validate(data)
        # Pattern score should be 0.5 (neutral)
        assert result.details.get("pattern") == 0.5
