"""Tests for mode detector."""

import pytest

from src.cli.v2.experience.mode_detector import InteractionMode, ModeDetector


class TestModeDetector:
    @pytest.fixture
    def detector(self):
        return ModeDetector()

    def test_quick_mode_for_status_queries(self, detector):
        """Simple status queries should use quick mode."""
        result = detector.detect("status")
        assert result.mode == InteractionMode.QUICK

    def test_quick_mode_for_simple_questions(self, detector):
        """Simple factual questions use quick mode."""
        result = detector.detect("what time is it")
        assert result.mode == InteractionMode.QUICK

    def test_autonomous_mode_for_analysis_tasks(self, detector):
        """Multi-step analysis tasks use autonomous mode."""
        result = detector.detect("analyze sales.csv and create a report")
        assert result.mode == InteractionMode.AUTONOMOUS

    def test_supervised_mode_for_code_changes(self, detector):
        """Code modification tasks use supervised mode."""
        result = detector.detect("refactor the auth module")
        assert result.mode == InteractionMode.SUPERVISED

    def test_conversational_mode_for_exploration(self, detector):
        """Exploratory/unclear tasks use conversational mode."""
        result = detector.detect("I'm not sure how to approach this")
        assert result.mode == InteractionMode.CONVERSATIONAL

    def test_detection_result_has_confidence(self, detector):
        """Detection result includes confidence score."""
        result = detector.detect("analyze data.csv")
        assert 0.0 <= result.confidence <= 1.0

    def test_detection_result_has_reasoning(self, detector):
        """Detection result includes reasoning."""
        result = detector.detect("fix the login bug")
        assert result.reasoning != ""

    def test_conversational_what_is_best(self, detector):
        """'What is the best' questions should be conversational."""
        result = detector.detect("what is the best way to structure this project")
        assert result.mode == InteractionMode.CONVERSATIONAL
