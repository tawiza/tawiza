"""Tests for Active Learning DTOs - Pydantic models validation."""

from datetime import datetime
from uuid import uuid4

import pytest

from src.application.dtos.active_learning_dtos import (
    DetectDriftRequest,
    DriftReportResponse,
    ModelHealthStatusResponse,
    RetrainingConditionsResponse,
    RetrainingJobResponse,
    SampleScoreResponse,
    SamplingResultResponse,
    SelectSamplesRequest,
    TriggerRetrainingRequest,
)


class TestSelectSamplesRequest:
    """Test sample selection request validation."""

    def test_valid_request(self):
        req = SelectSamplesRequest(
            model_name="my_model",
            model_version="1.0",
            strategy_type="uncertainty",
            sample_count=100,
        )
        assert req.model_name == "my_model"
        assert req.sample_count == 100
        assert req.threshold is None
        assert req.filters is None

    def test_all_strategies(self):
        for strategy in ["uncertainty", "margin", "entropy", "diversity", "random"]:
            req = SelectSamplesRequest(
                model_name="m",
                model_version="1",
                strategy_type=strategy,
                sample_count=10,
            )
            assert req.strategy_type == strategy

    def test_invalid_strategy(self):
        with pytest.raises(Exception):  # ValidationError
            SelectSamplesRequest(
                model_name="m",
                model_version="1",
                strategy_type="invalid",
                sample_count=10,
            )

    def test_sample_count_must_be_positive(self):
        with pytest.raises(Exception):
            SelectSamplesRequest(
                model_name="m",
                model_version="1",
                strategy_type="random",
                sample_count=0,
            )

    def test_sample_count_max(self):
        with pytest.raises(Exception):
            SelectSamplesRequest(
                model_name="m",
                model_version="1",
                strategy_type="random",
                sample_count=1001,
            )

    def test_threshold_range(self):
        req = SelectSamplesRequest(
            model_name="m",
            model_version="1",
            strategy_type="random",
            sample_count=10,
            threshold=0.5,
        )
        assert req.threshold == 0.5

    def test_threshold_out_of_range(self):
        with pytest.raises(Exception):
            SelectSamplesRequest(
                model_name="m",
                model_version="1",
                strategy_type="random",
                sample_count=10,
                threshold=1.5,
            )

    def test_with_filters(self):
        req = SelectSamplesRequest(
            model_name="m",
            model_version="1",
            strategy_type="random",
            sample_count=10,
            filters={"category": "A"},
        )
        assert req.filters == {"category": "A"}


class TestSampleScoreResponse:
    """Test sample score response."""

    def test_minimal(self):
        resp = SampleScoreResponse(sample_id="s1", score=0.85)
        assert resp.sample_id == "s1"
        assert resp.confidence is None

    def test_full(self):
        resp = SampleScoreResponse(
            sample_id="s1",
            score=0.85,
            confidence=0.9,
            entropy=0.3,
            margin=0.1,
            metadata={"key": "val"},
        )
        assert resp.entropy == 0.3


class TestSamplingResultResponse:
    """Test sampling result response."""

    def test_create(self):
        samples = [SampleScoreResponse(sample_id="s1", score=0.8)]
        resp = SamplingResultResponse(
            strategy_type="uncertainty",
            selected_samples=samples,
            total_candidates=1000,
            sample_count=1,
            average_score=0.8,
        )
        assert resp.total_candidates == 1000
        assert len(resp.selected_samples) == 1


class TestDetectDriftRequest:
    """Test drift detection request."""

    def test_valid_types(self):
        for dt in ["data_drift", "concept_drift", "prediction_drift", "performance_drift"]:
            req = DetectDriftRequest(model_name="m", model_version="1", drift_type=dt)
            assert req.drift_type == dt

    def test_invalid_type(self):
        with pytest.raises(Exception):
            DetectDriftRequest(model_name="m", model_version="1", drift_type="invalid")

    def test_with_window(self):
        req = DetectDriftRequest(
            model_name="m",
            model_version="1",
            drift_type="data_drift",
            window_start=datetime(2026, 1, 1),
            window_end=datetime(2026, 2, 1),
        )
        assert req.window_start is not None


class TestDriftReportResponse:
    """Test drift report response."""

    def test_create(self):
        report = DriftReportResponse(
            id=uuid4(),
            model_name="m",
            model_version="1",
            drift_type="data_drift",
            metric_name="ks_test",
            current_value=0.8,
            baseline_value=0.5,
            drift_score=0.6,
            is_drifted=True,
            severity="high",
            deviation_percentage=60.0,
            requires_action=True,
            created_at=datetime.now(),
        )
        assert report.is_drifted is True
        assert report.requires_action is True


class TestTriggerRetrainingRequest:
    """Test retraining trigger request."""

    def test_minimal(self):
        req = TriggerRetrainingRequest(
            model_name="m",
            model_version="1",
            trigger_reason="drift_detected",
        )
        assert req.config is None

    def test_with_config(self):
        req = TriggerRetrainingRequest(
            model_name="m",
            model_version="1",
            trigger_reason="manual",
            config={"epochs": 5},
        )
        assert req.config["epochs"] == 5


class TestRetrainingJobResponse:
    """Test retraining job response."""

    def test_create(self):
        resp = RetrainingJobResponse(
            id=uuid4(),
            trigger_reason="drift",
            model_name="m",
            base_model_version="1.0",
            new_samples_count=100,
            status="running",
            is_terminal=False,
            created_at=datetime.now(),
        )
        assert resp.status == "running"
        assert resp.is_terminal is False


class TestRetrainingConditionsResponse:
    """Test retraining conditions."""

    def test_create(self):
        resp = RetrainingConditionsResponse(
            model_name="m",
            model_version="1",
            conditions={"drift": True, "error_rate": 0.15},
            retraining_recommended=True,
            recommendation_reason="Drift detected",
        )
        assert resp.retraining_recommended is True


class TestModelHealthStatusResponse:
    """Test model health status."""

    def test_create(self):
        resp = ModelHealthStatusResponse(
            model_name="m",
            model_version="1",
            drift_detected=False,
            error_rate=0.02,
            new_samples_available=500,
            days_since_training=30,
            retraining_recommended=False,
            pending_labeling_samples=50,
            last_checked=datetime.now(),
        )
        assert resp.drift_detected is False
        assert resp.days_since_training == 30
