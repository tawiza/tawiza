"""Tests for the SignalDetector module."""

from datetime import datetime

import pytest

from src.infrastructure.agents.tajine.territorial.signal_detector import (
    DetectedSignal,
    SignalCategory,
    SignalDetector,
    SignalIndicator,
    SignalPattern,
    SignalSeverity,
    create_signal_detector,
)


class TestSignalIndicator:
    """Tests for SignalIndicator dataclass."""

    def test_indicator_triggered_up(self):
        """Test indicator triggered when value exceeds threshold (up direction)."""
        indicator = SignalIndicator(
            name="test",
            source="test_source",
            value=0.20,
            threshold=0.15,
            direction="up",
        )
        assert indicator.is_triggered is True

    def test_indicator_not_triggered_up(self):
        """Test indicator not triggered when value below threshold (up direction)."""
        indicator = SignalIndicator(
            name="test",
            source="test_source",
            value=0.10,
            threshold=0.15,
            direction="up",
        )
        assert indicator.is_triggered is False

    def test_indicator_triggered_down(self):
        """Test indicator triggered when value below threshold (down direction)."""
        indicator = SignalIndicator(
            name="test",
            source="test_source",
            value=-0.20,
            threshold=-0.15,
            direction="down",
        )
        assert indicator.is_triggered is True

    def test_indicator_not_triggered_down(self):
        """Test indicator not triggered when value above threshold (down direction)."""
        indicator = SignalIndicator(
            name="test",
            source="test_source",
            value=-0.10,
            threshold=-0.15,
            direction="down",
        )
        assert indicator.is_triggered is False


class TestSignalPattern:
    """Tests for SignalPattern dataclass."""

    def test_evaluate_severity_critical(self):
        """Test severity evaluation returns critical."""
        pattern = SignalPattern(
            id="test",
            name="Test Pattern",
            category=SignalCategory.CRISIS,
            description="Test",
            indicators_config=[],
            min_indicators_triggered=2,
            severity_rules={3: SignalSeverity.CRITICAL, 2: SignalSeverity.WARNING},
            recommendation_template="Test",
        )
        assert pattern.evaluate_severity(3) == SignalSeverity.CRITICAL
        assert pattern.evaluate_severity(4) == SignalSeverity.CRITICAL

    def test_evaluate_severity_warning(self):
        """Test severity evaluation returns warning."""
        pattern = SignalPattern(
            id="test",
            name="Test Pattern",
            category=SignalCategory.CRISIS,
            description="Test",
            indicators_config=[],
            min_indicators_triggered=2,
            severity_rules={3: SignalSeverity.CRITICAL, 2: SignalSeverity.WARNING},
            recommendation_template="Test",
        )
        assert pattern.evaluate_severity(2) == SignalSeverity.WARNING

    def test_evaluate_severity_default(self):
        """Test severity evaluation returns INFO as default."""
        pattern = SignalPattern(
            id="test",
            name="Test Pattern",
            category=SignalCategory.CRISIS,
            description="Test",
            indicators_config=[],
            min_indicators_triggered=2,
            severity_rules={3: SignalSeverity.CRITICAL},
            recommendation_template="Test",
        )
        assert pattern.evaluate_severity(1) == SignalSeverity.INFO


class TestDetectedSignal:
    """Tests for DetectedSignal dataclass."""

    def test_to_dict(self):
        """Test signal serialization to dict."""
        indicator = SignalIndicator(
            name="test_ind",
            source="sirene",
            value=0.20,
            threshold=0.15,
            direction="up",
        )
        signal = DetectedSignal(
            pattern_id="test_pattern",
            pattern_name="Test Pattern",
            category=SignalCategory.CRISIS,
            severity=SignalSeverity.WARNING,
            territory_code="75056",
            territory_name="Paris",
            confidence=0.85,
            indicators=[indicator],
            description="Test description",
            recommendation="Test recommendation",
        )

        result = signal.to_dict()

        assert result["pattern_id"] == "test_pattern"
        assert result["category"] == "crisis"
        assert result["severity"] == "warning"
        assert result["territory_code"] == "75056"
        assert result["confidence"] == 0.85
        assert len(result["indicators"]) == 1
        assert result["indicators"][0]["triggered"] is True


class TestSignalDetector:
    """Tests for SignalDetector class."""

    def test_init_loads_default_patterns(self):
        """Test that default patterns are loaded on init."""
        detector = SignalDetector()
        patterns = detector.get_patterns()

        assert len(patterns) >= 8  # We defined 8 default patterns
        pattern_ids = [p.id for p in patterns]
        assert "crisis_sectoral" in pattern_ids
        assert "growth_takeoff" in pattern_ids
        assert "commercial_desert" in pattern_ids

    def test_register_custom_pattern(self):
        """Test registering a custom pattern."""
        detector = SignalDetector()
        initial_count = len(detector.get_patterns())

        custom_pattern = SignalPattern(
            id="custom_test",
            name="Custom Test Pattern",
            category=SignalCategory.INNOVATION,
            description="A custom pattern for testing",
            indicators_config=[
                {
                    "name": "test",
                    "source": "test",
                    "metric": "test",
                    "direction": "up",
                    "threshold": 0.5,
                }
            ],
            min_indicators_triggered=1,
            severity_rules={1: SignalSeverity.INFO},
            recommendation_template="Test",
        )

        detector.register_pattern(custom_pattern)

        assert len(detector.get_patterns()) == initial_count + 1

    def test_create_signal_detector_factory(self):
        """Test factory function creates detector properly."""
        detector = create_signal_detector()
        assert isinstance(detector, SignalDetector)
        assert len(detector.get_patterns()) >= 8

    def test_create_signal_detector_with_additional_patterns(self):
        """Test factory with additional patterns."""
        custom_pattern = SignalPattern(
            id="factory_test",
            name="Factory Test",
            category=SignalCategory.GROWTH,
            description="Test",
            indicators_config=[],
            min_indicators_triggered=1,
            severity_rules={1: SignalSeverity.INFO},
            recommendation_template="Test",
        )

        detector = create_signal_detector(additional_patterns=[custom_pattern])
        pattern_ids = [p.id for p in detector.get_patterns()]

        assert "factory_test" in pattern_ids

    def test_compute_metric_value_variation(self):
        """Test metric computation for variation metrics."""
        detector = SignalDetector()

        results = [
            {"count": 100},
            {"count": 120},
        ]
        value = detector._compute_metric_value(results, "job_offers_variation")

        assert value == pytest.approx(0.2, rel=0.01)  # 20% increase

    def test_compute_metric_value_empty(self):
        """Test metric computation with empty results."""
        detector = SignalDetector()

        value = detector._compute_metric_value([], "any_metric")
        assert value == 0.0

    def test_generate_description(self):
        """Test description generation."""
        detector = SignalDetector()
        pattern = SignalPattern(
            id="test",
            name="Test Crisis",
            category=SignalCategory.CRISIS,
            description="Test",
            indicators_config=[],
            min_indicators_triggered=1,
            severity_rules={1: SignalSeverity.WARNING},
            recommendation_template="Test",
        )
        indicators = [
            SignalIndicator(
                name="job_decline",
                source="france_travail",
                value=-0.20,
                threshold=-0.15,
                direction="down",
            )
        ]

        description = detector._generate_description(pattern, indicators, "Lyon")

        assert "Test Crisis" in description
        assert "Lyon" in description
        assert "job_decline" in description


class TestSignalCategories:
    """Tests for signal category enumeration."""

    def test_all_categories_exist(self):
        """Test all expected categories are defined."""
        expected = ["crisis", "growth", "mutation", "employment", "public_market", "innovation"]
        for cat in expected:
            assert hasattr(SignalCategory, cat.upper())

    def test_severity_levels(self):
        """Test all severity levels are defined."""
        assert SignalSeverity.CRITICAL.value == "critical"
        assert SignalSeverity.WARNING.value == "warning"
        assert SignalSeverity.INFO.value == "info"
        assert SignalSeverity.OPPORTUNITY.value == "opportunity"
