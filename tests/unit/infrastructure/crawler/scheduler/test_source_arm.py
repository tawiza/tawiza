"""Tests for SourceArm model."""

import pytest

from src.infrastructure.crawler.scheduler.source_arm import SourceArm, SourceType


class TestSourceArmCreation:
    """Test SourceArm model creation."""

    def test_create_api_source(self):
        """Create an API source arm."""
        arm = SourceArm(
            source_id="insee-sirene",
            url="https://api.insee.fr/entreprises/sirene/V3.11",
            source_type=SourceType.API,
        )
        assert arm.source_id == "insee-sirene"
        assert arm.source_type == SourceType.API
        assert arm.pulls == 0
        assert arm.successes == 0

    def test_create_web_source(self):
        """Create a web source arm."""
        arm = SourceArm(
            source_id="cci-lyon",
            url="https://www.lyon-metropole.cci.fr",
            source_type=SourceType.WEB,
        )
        assert arm.source_type == SourceType.WEB

    def test_default_scores(self):
        """Default MAB scores are 0.5."""
        arm = SourceArm(source_id="test", url="https://example.com", source_type=SourceType.WEB)
        assert arm.freshness_score == 0.5
        assert arm.quality_score == 0.5
        assert arm.relevance_score == 0.5


class TestSourceArmRewards:
    """Test SourceArm reward calculations."""

    def test_average_reward_initial(self):
        """Initial average reward is based on default scores."""
        arm = SourceArm(source_id="test", url="https://example.com", source_type=SourceType.API)
        assert arm.average_reward == 0.5

    def test_record_success(self):
        """Recording success updates pulls and successes."""
        arm = SourceArm(source_id="test", url="https://example.com", source_type=SourceType.API)
        arm.record_pull(success=True, freshness=0.8, quality=0.7)
        assert arm.pulls == 1
        assert arm.successes == 1
        assert arm.freshness_score == 0.8
        assert arm.quality_score == 0.7

    def test_record_failure(self):
        """Recording failure updates pulls but not successes."""
        arm = SourceArm(source_id="test", url="https://example.com", source_type=SourceType.API)
        arm.record_pull(success=False)
        assert arm.pulls == 1
        assert arm.successes == 0

    def test_update_relevance(self):
        """Update relevance based on TAJINE feedback."""
        arm = SourceArm(source_id="test", url="https://example.com", source_type=SourceType.API)
        arm.update_relevance(was_useful=True)
        assert arm.relevance_score > 0.5

        arm.update_relevance(was_useful=False)
        assert 0 < arm.relevance_score < 1.0


class TestSourceArmSerialization:
    """Test SourceArm serialization."""

    def test_to_dict(self):
        """Convert to dictionary."""
        arm = SourceArm(source_id="test", url="https://example.com", source_type=SourceType.API)
        d = arm.to_dict()
        assert d["source_id"] == "test"
        assert d["source_type"] == "api"

    def test_from_dict(self):
        """Create from dictionary."""
        data = {
            "source_id": "test",
            "url": "https://example.com",
            "source_type": "api",
            "pulls": 5,
            "freshness_score": 0.8,
        }
        arm = SourceArm.from_dict(data)
        assert arm.source_id == "test"
        assert arm.pulls == 5
        assert arm.freshness_score == 0.8
