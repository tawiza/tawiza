"""Tests for AlphaTester - Predictive power evaluation."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from src.infrastructure.agents.tajine.core.types import RawData
from src.infrastructure.agents.tajine.evaluator.alpha_tester import (
    AlphaResult,
    AlphaTester,
)


@pytest.fixture
def tester():
    """Create an AlphaTester instance."""
    return AlphaTester()


@pytest.fixture
def fresh_data():
    """Create fresh sample RawData."""
    return RawData(
        source="sirene",
        content={"text": "Nouvelle acquisition: SIREN 123456782 annoncée aujourd'hui"},
        url="https://api.sirene.fr/test",
        fetched_at=datetime.now(UTC),
        quality_hint=0.9,
    )


@pytest.fixture
def stale_data():
    """Create stale sample RawData."""
    return RawData(
        source="sirene",
        content={"text": "Information confirmée inchangée"},
        url="https://api.sirene.fr/old",
        fetched_at=datetime.now(UTC) - timedelta(days=180),
        quality_hint=0.5,
    )


class TestAlphaTester:
    """Tests for AlphaTester."""

    @pytest.mark.asyncio
    async def test_test_returns_float(self, tester, fresh_data):
        """test() should return a float score."""
        score = await tester.test(fresh_data)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_analyze_returns_alpha_result(self, tester, fresh_data):
        """analyze() should return AlphaResult with details."""
        result = await tester.analyze(fresh_data)
        assert isinstance(result, AlphaResult)
        assert hasattr(result, "score")
        assert hasattr(result, "novelty")
        assert hasattr(result, "relevance")
        assert hasattr(result, "timeliness")

    @pytest.mark.asyncio
    async def test_fresh_data_scores_high_timeliness(self, tester, fresh_data):
        """Fresh data should have high timeliness score."""
        result = await tester.analyze(fresh_data)
        assert result.timeliness >= 0.8

    @pytest.mark.asyncio
    async def test_stale_data_scores_low_timeliness(self, tester, stale_data):
        """Stale data should have lower timeliness score."""
        result = await tester.analyze(stale_data)
        assert result.timeliness < 0.6

    @pytest.mark.asyncio
    async def test_duplicate_detection(self, tester):
        """Duplicate content should score low on novelty."""
        data1 = RawData(
            source="sirene",
            content={"text": "Exactly the same content for testing"},
            url="https://api.sirene.fr/1",
            fetched_at=datetime.now(UTC),
            quality_hint=0.8,
        )
        data2 = RawData(
            source="bodacc",  # Different source
            content={"text": "Exactly the same content for testing"},  # Same content
            url="https://bodacc.fr/2",
            fetched_at=datetime.now(UTC),
            quality_hint=0.8,
        )

        result1 = await tester.analyze(data1)
        result2 = await tester.analyze(data2)

        # First occurrence is novel
        assert result1.novelty >= 0.5
        # Second occurrence is duplicate
        assert result2.novelty < 0.2

    @pytest.mark.asyncio
    async def test_high_alpha_signals_boost_novelty(self, tester):
        """Content with high-alpha keywords should score higher."""
        high_alpha = RawData(
            source="sirene",
            content={"text": "Acquisition majeure et levée de fonds de 50M EUR"},
            url="https://api.sirene.fr/alpha",
            fetched_at=datetime.now(UTC),
            quality_hint=0.9,
        )
        low_alpha = RawData(
            source="sirene",
            content={"text": "Confirmation des informations stable et maintien"},
            url="https://api.sirene.fr/low",
            fetched_at=datetime.now(UTC),
            quality_hint=0.5,
        )

        high_result = await tester.analyze(high_alpha)
        low_result = await tester.analyze(low_alpha)

        assert high_result.novelty > low_result.novelty

    @pytest.mark.asyncio
    async def test_relevance_with_business_entities(self, tester):
        """Content with SIREN/SIRET should score higher relevance."""
        with_entities = RawData(
            source="sirene",
            content={"text": "Entreprise SIREN 123456782 département 75 marché public"},
            url="https://api.sirene.fr/entities",
            fetched_at=datetime.now(UTC),
            quality_hint=0.8,
        )
        without_entities = RawData(
            source="blog",
            content={"text": "Generic article about economy without specifics"},
            url="https://blog.example.com",
            fetched_at=datetime.now(UTC),
            quality_hint=0.5,
        )

        with_result = await tester.analyze(with_entities)
        without_result = await tester.analyze(without_entities)

        assert with_result.relevance > without_result.relevance

    def test_freshness_decay(self, tester):
        """Test freshness score decay over time."""
        # Fresh (today)
        assert tester._freshness_score(0) == 1.0

        # Recent (this week)
        assert 0.8 < tester._freshness_score(3) < 1.0

        # Old (this quarter)
        assert 0.4 < tester._freshness_score(60) < 0.7

        # Very old (more than a year)
        assert tester._freshness_score(400) <= 0.3

    def test_hash_content_normalization(self, tester):
        """Content hashing should normalize text."""
        hash1 = tester._hash_content("Hello World")
        hash2 = tester._hash_content("hello world")
        hash3 = tester._hash_content("  hello   world  ")

        # All should produce same hash after normalization
        assert hash1 == hash2 == hash3

    def test_reset_seen_clears_duplicates(self, tester):
        """reset_seen() should clear duplicate detection."""
        content = "Unique content for reset test"
        hash_val = tester._hash_content(content)

        tester.seen_hashes.add(hash_val)
        assert hash_val in tester.seen_hashes

        tester.reset_seen()
        assert hash_val not in tester.seen_hashes

    def test_date_extraction_french_format(self, tester):
        """Should extract dates in French format."""
        content = "Publication du 15 janvier 2025"
        extracted = tester._extract_date(content)
        assert extracted is not None
        assert extracted.year == 2025
        assert extracted.month == 1
        assert extracted.day == 15
