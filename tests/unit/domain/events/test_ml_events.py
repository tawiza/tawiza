"""Tests for Machine Learning domain events.

This module tests the ML domain events defined in
``src/domain/events/ml_events.py``:

- Construction with valid arguments and inherited base fields
- Default argument behaviour (``mlflow_run_id``, ``reason``)
- Immutability of frozen dataclasses
- ``to_dict()`` serialization (including base fields and type coercions)
- Edge cases (empty strings, ``None`` values, boundary numeric values)

The events are plain frozen dataclasses inheriting from
:class:`~src.domain.events.base.DomainEvent`. They carry no internal
validation/invariants and no enum or value-object ordering semantics, so the
tests focus on construction, inherited base behaviour, immutability and
serialization.
"""

from datetime import datetime
from uuid import UUID, uuid4

import pytest

from src.domain.events.base import DomainEvent
from src.domain.events.ml_events import (
    DatasetCreatedEvent,
    DriftDetectedEvent,
    FeedbackReceivedEvent,
    ModelDeployedEvent,
    ModelRetiredEvent,
    ModelTrainedEvent,
    PredictionRequestedEvent,
    RetrainingTriggeredEvent,
    SamplesSelectedForLabelingEvent,
)


def _assert_base_fields(event: DomainEvent, expected_aggregate_id: UUID) -> None:
    """Assert that the inherited DomainEvent base fields are populated."""
    assert isinstance(event, DomainEvent)
    assert isinstance(event.event_id, UUID)
    assert isinstance(event.occurred_at, datetime)
    # Base __init__ uses utc_now() which is timezone-aware.
    assert event.occurred_at.tzinfo is not None
    assert event.aggregate_id == expected_aggregate_id


class TestModelTrainedEvent:
    """Tests for ModelTrainedEvent."""

    def test_construction_valid(self):
        model_id = uuid4()
        event = ModelTrainedEvent(
            model_id=model_id,
            model_name="sentiment-classifier",
            version="1.0.0",
            accuracy=0.95,
            mlflow_run_id="run-123",
        )

        assert event.model_name == "sentiment-classifier"
        assert event.version == "1.0.0"
        assert event.accuracy == 0.95
        assert event.mlflow_run_id == "run-123"
        _assert_base_fields(event, model_id)

    def test_mlflow_run_id_defaults_to_none(self):
        event = ModelTrainedEvent(
            model_id=uuid4(),
            model_name="m",
            version="1.0.0",
            accuracy=0.5,
        )

        assert event.mlflow_run_id is None

    def test_aggregate_id_is_model_id(self):
        model_id = uuid4()
        event = ModelTrainedEvent(
            model_id=model_id,
            model_name="m",
            version="1.0.0",
            accuracy=0.5,
        )

        assert event.aggregate_id == model_id

    def test_event_ids_are_unique(self):
        model_id = uuid4()
        e1 = ModelTrainedEvent(model_id=model_id, model_name="m", version="1", accuracy=0.5)
        e2 = ModelTrainedEvent(model_id=model_id, model_name="m", version="1", accuracy=0.5)

        assert e1.event_id != e2.event_id

    def test_is_frozen(self):
        event = ModelTrainedEvent(
            model_id=uuid4(),
            model_name="m",
            version="1.0.0",
            accuracy=0.9,
        )

        with pytest.raises((AttributeError, TypeError)):
            event.accuracy = 0.99

    def test_to_dict(self):
        model_id = uuid4()
        event = ModelTrainedEvent(
            model_id=model_id,
            model_name="m",
            version="2.0.0",
            accuracy=0.88,
            mlflow_run_id="run-xyz",
        )

        data = event.to_dict()

        assert data["event_type"] == "ModelTrainedEvent"
        assert data["event_id"] == str(event.event_id)
        assert data["aggregate_id"] == str(model_id)
        assert data["occurred_at"] == event.occurred_at.isoformat()
        assert data["model_name"] == "m"
        assert data["version"] == "2.0.0"
        assert data["accuracy"] == 0.88
        assert data["mlflow_run_id"] == "run-xyz"

    def test_to_dict_with_none_mlflow_run_id(self):
        event = ModelTrainedEvent(
            model_id=uuid4(),
            model_name="m",
            version="1.0.0",
            accuracy=0.5,
        )

        data = event.to_dict()

        assert data["mlflow_run_id"] is None

    def test_edge_case_zero_accuracy_and_empty_strings(self):
        event = ModelTrainedEvent(
            model_id=uuid4(),
            model_name="",
            version="",
            accuracy=0.0,
        )

        assert event.model_name == ""
        assert event.version == ""
        assert event.accuracy == 0.0


class TestModelDeployedEvent:
    """Tests for ModelDeployedEvent."""

    def test_construction_valid(self):
        model_id = uuid4()
        event = ModelDeployedEvent(
            model_id=model_id,
            model_name="m",
            version="1.0.0",
            deployment_strategy="canary",
            traffic_percentage=10,
        )

        assert event.model_name == "m"
        assert event.version == "1.0.0"
        assert event.deployment_strategy == "canary"
        assert event.traffic_percentage == 10
        _assert_base_fields(event, model_id)

    def test_is_frozen(self):
        event = ModelDeployedEvent(
            model_id=uuid4(),
            model_name="m",
            version="1.0.0",
            deployment_strategy="direct",
            traffic_percentage=100,
        )

        with pytest.raises((AttributeError, TypeError)):
            event.traffic_percentage = 50

    def test_to_dict(self):
        model_id = uuid4()
        event = ModelDeployedEvent(
            model_id=model_id,
            model_name="m",
            version="3.1.0",
            deployment_strategy="blue_green",
            traffic_percentage=0,
        )

        data = event.to_dict()

        assert data["event_type"] == "ModelDeployedEvent"
        assert data["aggregate_id"] == str(model_id)
        assert data["model_name"] == "m"
        assert data["version"] == "3.1.0"
        assert data["deployment_strategy"] == "blue_green"
        assert data["traffic_percentage"] == 0

    def test_edge_case_full_traffic(self):
        event = ModelDeployedEvent(
            model_id=uuid4(),
            model_name="m",
            version="1.0.0",
            deployment_strategy="direct",
            traffic_percentage=100,
        )

        assert event.traffic_percentage == 100


class TestModelRetiredEvent:
    """Tests for ModelRetiredEvent."""

    def test_construction_valid(self):
        model_id = uuid4()
        event = ModelRetiredEvent(
            model_id=model_id,
            model_name="m",
            version="1.0.0",
            reason="Replaced by v2",
        )

        assert event.model_name == "m"
        assert event.version == "1.0.0"
        assert event.reason == "Replaced by v2"
        _assert_base_fields(event, model_id)

    def test_reason_defaults_to_empty_string(self):
        event = ModelRetiredEvent(
            model_id=uuid4(),
            model_name="m",
            version="1.0.0",
        )

        assert event.reason == ""

    def test_is_frozen(self):
        event = ModelRetiredEvent(
            model_id=uuid4(),
            model_name="m",
            version="1.0.0",
        )

        with pytest.raises((AttributeError, TypeError)):
            event.reason = "changed"

    def test_to_dict(self):
        model_id = uuid4()
        event = ModelRetiredEvent(
            model_id=model_id,
            model_name="m",
            version="1.0.0",
            reason="deprecated",
        )

        data = event.to_dict()

        assert data["event_type"] == "ModelRetiredEvent"
        assert data["aggregate_id"] == str(model_id)
        assert data["model_name"] == "m"
        assert data["version"] == "1.0.0"
        assert data["reason"] == "deprecated"


class TestPredictionRequestedEvent:
    """Tests for PredictionRequestedEvent."""

    def test_construction_valid(self):
        prediction_id = uuid4()
        model_id = uuid4()
        input_data = {"text": "hello", "lang": "en"}
        event = PredictionRequestedEvent(
            prediction_id=prediction_id,
            model_id=model_id,
            input_data=input_data,
        )

        assert event.model_id == model_id
        assert event.input_data == input_data
        # The aggregate_id is the prediction_id, not the model_id.
        _assert_base_fields(event, prediction_id)

    def test_aggregate_id_is_prediction_id(self):
        prediction_id = uuid4()
        model_id = uuid4()
        event = PredictionRequestedEvent(
            prediction_id=prediction_id,
            model_id=model_id,
            input_data={},
        )

        assert event.aggregate_id == prediction_id
        assert event.aggregate_id != model_id

    def test_is_frozen(self):
        event = PredictionRequestedEvent(
            prediction_id=uuid4(),
            model_id=uuid4(),
            input_data={},
        )

        with pytest.raises((AttributeError, TypeError)):
            event.model_id = uuid4()

    def test_to_dict_serializes_model_id_as_str(self):
        prediction_id = uuid4()
        model_id = uuid4()
        input_data = {"feature": 1}
        event = PredictionRequestedEvent(
            prediction_id=prediction_id,
            model_id=model_id,
            input_data=input_data,
        )

        data = event.to_dict()

        assert data["event_type"] == "PredictionRequestedEvent"
        assert data["aggregate_id"] == str(prediction_id)
        assert data["model_id"] == str(model_id)
        assert data["input_data"] == input_data

    def test_edge_case_empty_input_data(self):
        event = PredictionRequestedEvent(
            prediction_id=uuid4(),
            model_id=uuid4(),
            input_data={},
        )

        assert event.input_data == {}
        assert event.to_dict()["input_data"] == {}


class TestFeedbackReceivedEvent:
    """Tests for FeedbackReceivedEvent."""

    def test_construction_valid(self):
        feedback_id = uuid4()
        prediction_id = uuid4()
        event = FeedbackReceivedEvent(
            feedback_id=feedback_id,
            prediction_id=prediction_id,
            feedback_type="positive",
            feedback_value=5,
        )

        assert event.prediction_id == prediction_id
        assert event.feedback_type == "positive"
        assert event.feedback_value == 5
        _assert_base_fields(event, feedback_id)

    def test_aggregate_id_is_feedback_id(self):
        feedback_id = uuid4()
        prediction_id = uuid4()
        event = FeedbackReceivedEvent(
            feedback_id=feedback_id,
            prediction_id=prediction_id,
            feedback_type="negative",
            feedback_value=None,
        )

        assert event.aggregate_id == feedback_id
        assert event.aggregate_id != prediction_id

    def test_feedback_value_accepts_none(self):
        event = FeedbackReceivedEvent(
            feedback_id=uuid4(),
            prediction_id=uuid4(),
            feedback_type="implicit",
            feedback_value=None,
        )

        assert event.feedback_value is None

    def test_feedback_value_accepts_arbitrary_type(self):
        payload = {"corrected": "new label", "confidence": 0.9}
        event = FeedbackReceivedEvent(
            feedback_id=uuid4(),
            prediction_id=uuid4(),
            feedback_type="correction",
            feedback_value=payload,
        )

        assert event.feedback_value == payload

    def test_is_frozen(self):
        event = FeedbackReceivedEvent(
            feedback_id=uuid4(),
            prediction_id=uuid4(),
            feedback_type="positive",
            feedback_value=1,
        )

        with pytest.raises((AttributeError, TypeError)):
            event.feedback_type = "negative"

    def test_to_dict_serializes_prediction_id_as_str(self):
        feedback_id = uuid4()
        prediction_id = uuid4()
        event = FeedbackReceivedEvent(
            feedback_id=feedback_id,
            prediction_id=prediction_id,
            feedback_type="correction",
            feedback_value="fixed",
        )

        data = event.to_dict()

        assert data["event_type"] == "FeedbackReceivedEvent"
        assert data["aggregate_id"] == str(feedback_id)
        assert data["prediction_id"] == str(prediction_id)
        assert data["feedback_type"] == "correction"
        assert data["feedback_value"] == "fixed"

    def test_to_dict_with_none_feedback_value(self):
        event = FeedbackReceivedEvent(
            feedback_id=uuid4(),
            prediction_id=uuid4(),
            feedback_type="implicit",
            feedback_value=None,
        )

        assert event.to_dict()["feedback_value"] is None


class TestDatasetCreatedEvent:
    """Tests for DatasetCreatedEvent."""

    def test_construction_valid(self):
        dataset_id = uuid4()
        event = DatasetCreatedEvent(
            dataset_id=dataset_id,
            dataset_name="train-2026",
            size=1000,
            dataset_type="training",
        )

        assert event.dataset_name == "train-2026"
        assert event.size == 1000
        assert event.dataset_type == "training"
        _assert_base_fields(event, dataset_id)

    def test_is_frozen(self):
        event = DatasetCreatedEvent(
            dataset_id=uuid4(),
            dataset_name="d",
            size=10,
            dataset_type="test",
        )

        with pytest.raises((AttributeError, TypeError)):
            event.size = 20

    def test_to_dict(self):
        dataset_id = uuid4()
        event = DatasetCreatedEvent(
            dataset_id=dataset_id,
            dataset_name="d",
            size=42,
            dataset_type="validation",
        )

        data = event.to_dict()

        assert data["event_type"] == "DatasetCreatedEvent"
        assert data["aggregate_id"] == str(dataset_id)
        assert data["dataset_name"] == "d"
        assert data["size"] == 42
        assert data["dataset_type"] == "validation"

    def test_edge_case_zero_size_and_empty_name(self):
        event = DatasetCreatedEvent(
            dataset_id=uuid4(),
            dataset_name="",
            size=0,
            dataset_type="test",
        )

        assert event.size == 0
        assert event.dataset_name == ""


class TestRetrainingTriggeredEvent:
    """Tests for RetrainingTriggeredEvent."""

    def test_construction_valid(self):
        training_job_id = uuid4()
        current_model_id = uuid4()
        metrics = {"accuracy": 0.7, "drift": 0.3}
        event = RetrainingTriggeredEvent(
            training_job_id=training_job_id,
            trigger_reason="data_drift",
            current_model_id=current_model_id,
            metrics=metrics,
        )

        assert event.trigger_reason == "data_drift"
        assert event.current_model_id == current_model_id
        assert event.metrics == metrics
        _assert_base_fields(event, training_job_id)

    def test_aggregate_id_is_training_job_id(self):
        training_job_id = uuid4()
        current_model_id = uuid4()
        event = RetrainingTriggeredEvent(
            training_job_id=training_job_id,
            trigger_reason="scheduled",
            current_model_id=current_model_id,
            metrics={},
        )

        assert event.aggregate_id == training_job_id
        assert event.aggregate_id != current_model_id

    def test_is_frozen(self):
        event = RetrainingTriggeredEvent(
            training_job_id=uuid4(),
            trigger_reason="scheduled",
            current_model_id=uuid4(),
            metrics={},
        )

        with pytest.raises((AttributeError, TypeError)):
            event.trigger_reason = "manual"

    def test_to_dict_serializes_current_model_id_as_str(self):
        training_job_id = uuid4()
        current_model_id = uuid4()
        metrics = {"loss": 0.5}
        event = RetrainingTriggeredEvent(
            training_job_id=training_job_id,
            trigger_reason="performance_degradation",
            current_model_id=current_model_id,
            metrics=metrics,
        )

        data = event.to_dict()

        assert data["event_type"] == "RetrainingTriggeredEvent"
        assert data["aggregate_id"] == str(training_job_id)
        assert data["trigger_reason"] == "performance_degradation"
        assert data["current_model_id"] == str(current_model_id)
        assert data["metrics"] == metrics

    def test_edge_case_empty_metrics(self):
        event = RetrainingTriggeredEvent(
            training_job_id=uuid4(),
            trigger_reason="scheduled",
            current_model_id=uuid4(),
            metrics={},
        )

        assert event.metrics == {}
        assert event.to_dict()["metrics"] == {}


class TestDriftDetectedEvent:
    """Tests for DriftDetectedEvent."""

    def _make(self, **overrides):
        defaults = {
            "drift_report_id": uuid4(),
            "model_name": "m",
            "model_version": "1.0.0",
            "drift_type": "data_drift",
            "drift_score": 0.42,
            "severity": "medium",
            "metric_name": "psi",
            "current_value": 0.8,
            "baseline_value": 0.5,
        }
        defaults.update(overrides)
        return DriftDetectedEvent(**defaults)

    def test_construction_valid(self):
        drift_report_id = uuid4()
        event = self._make(drift_report_id=drift_report_id)

        assert event.model_name == "m"
        assert event.model_version == "1.0.0"
        assert event.drift_type == "data_drift"
        assert event.drift_score == 0.42
        assert event.severity == "medium"
        assert event.metric_name == "psi"
        assert event.current_value == 0.8
        assert event.baseline_value == 0.5
        _assert_base_fields(event, drift_report_id)

    def test_is_frozen(self):
        event = self._make()

        with pytest.raises((AttributeError, TypeError)):
            event.severity = "critical"

    def test_to_dict(self):
        drift_report_id = uuid4()
        event = self._make(
            drift_report_id=drift_report_id,
            drift_type="concept_drift",
            severity="critical",
            drift_score=0.99,
            current_value=1.0,
            baseline_value=0.0,
        )

        data = event.to_dict()

        assert data["event_type"] == "DriftDetectedEvent"
        assert data["aggregate_id"] == str(drift_report_id)
        assert data["model_name"] == "m"
        assert data["model_version"] == "1.0.0"
        assert data["drift_type"] == "concept_drift"
        assert data["drift_score"] == 0.99
        assert data["severity"] == "critical"
        assert data["metric_name"] == "psi"
        assert data["current_value"] == 1.0
        assert data["baseline_value"] == 0.0

    def test_edge_case_zero_values(self):
        event = self._make(drift_score=0.0, current_value=0.0, baseline_value=0.0)

        assert event.drift_score == 0.0
        assert event.current_value == 0.0
        assert event.baseline_value == 0.0


class TestSamplesSelectedForLabelingEvent:
    """Tests for SamplesSelectedForLabelingEvent."""

    def test_construction_valid(self):
        selection_id = uuid4()
        event = SamplesSelectedForLabelingEvent(
            selection_id=selection_id,
            strategy_type="uncertainty",
            sample_count=50,
            model_name="m",
            model_version="1.0.0",
            average_score=0.65,
        )

        assert event.strategy_type == "uncertainty"
        assert event.sample_count == 50
        assert event.model_name == "m"
        assert event.model_version == "1.0.0"
        assert event.average_score == 0.65
        _assert_base_fields(event, selection_id)

    def test_is_frozen(self):
        event = SamplesSelectedForLabelingEvent(
            selection_id=uuid4(),
            strategy_type="entropy",
            sample_count=10,
            model_name="m",
            model_version="1.0.0",
            average_score=0.5,
        )

        with pytest.raises((AttributeError, TypeError)):
            event.sample_count = 20

    def test_to_dict(self):
        selection_id = uuid4()
        event = SamplesSelectedForLabelingEvent(
            selection_id=selection_id,
            strategy_type="diversity",
            sample_count=100,
            model_name="m",
            model_version="2.0.0",
            average_score=0.33,
        )

        data = event.to_dict()

        assert data["event_type"] == "SamplesSelectedForLabelingEvent"
        assert data["aggregate_id"] == str(selection_id)
        assert data["strategy_type"] == "diversity"
        assert data["sample_count"] == 100
        assert data["model_name"] == "m"
        assert data["model_version"] == "2.0.0"
        assert data["average_score"] == 0.33

    def test_edge_case_zero_samples(self):
        event = SamplesSelectedForLabelingEvent(
            selection_id=uuid4(),
            strategy_type="margin",
            sample_count=0,
            model_name="",
            model_version="",
            average_score=0.0,
        )

        assert event.sample_count == 0
        assert event.average_score == 0.0


class TestEventsShareBaseContract:
    """Cross-cutting tests ensuring every event honours the DomainEvent base."""

    def _all_events(self):
        return [
            ModelTrainedEvent(
                model_id=uuid4(), model_name="m", version="1", accuracy=0.5
            ),
            ModelDeployedEvent(
                model_id=uuid4(),
                model_name="m",
                version="1",
                deployment_strategy="direct",
                traffic_percentage=100,
            ),
            ModelRetiredEvent(model_id=uuid4(), model_name="m", version="1"),
            PredictionRequestedEvent(
                prediction_id=uuid4(), model_id=uuid4(), input_data={}
            ),
            FeedbackReceivedEvent(
                feedback_id=uuid4(),
                prediction_id=uuid4(),
                feedback_type="positive",
                feedback_value=1,
            ),
            DatasetCreatedEvent(
                dataset_id=uuid4(), dataset_name="d", size=1, dataset_type="test"
            ),
            RetrainingTriggeredEvent(
                training_job_id=uuid4(),
                trigger_reason="scheduled",
                current_model_id=uuid4(),
                metrics={},
            ),
            DriftDetectedEvent(
                drift_report_id=uuid4(),
                model_name="m",
                model_version="1",
                drift_type="data_drift",
                drift_score=0.1,
                severity="low",
                metric_name="psi",
                current_value=0.1,
                baseline_value=0.1,
            ),
            SamplesSelectedForLabelingEvent(
                selection_id=uuid4(),
                strategy_type="uncertainty",
                sample_count=1,
                model_name="m",
                model_version="1",
                average_score=0.5,
            ),
        ]

    def test_all_events_are_domain_events(self):
        for event in self._all_events():
            assert isinstance(event, DomainEvent)

    def test_all_events_have_base_dict_keys(self):
        for event in self._all_events():
            data = event.to_dict()
            assert data["event_type"] == event.__class__.__name__
            assert data["event_id"] == str(event.event_id)
            assert data["aggregate_id"] == str(event.aggregate_id)
            assert data["occurred_at"] == event.occurred_at.isoformat()

    def test_all_events_generate_unique_event_ids(self):
        ids = [e.event_id for e in self._all_events()]
        assert len(ids) == len(set(ids))
