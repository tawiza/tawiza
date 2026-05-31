"""Unit tests for the TrainingJob domain entity (issue #161, batch 3 coverage).

Covers:
- TrainingJobStatus / TrainingTrigger StrEnums
- TrainingConfig frozen dataclass (defaults, immutability)
- TrainingJob aggregate root: construction, properties, full state machine
  (valid transitions + invalid transitions raising ValueError), domain event
  emission for automatic retraining, metrics handling, duration calculation,
  and to_dict serialization.

The production code is the source of truth; these tests assert its real
behaviour. No production API is invented.
"""

from datetime import datetime
from uuid import UUID, uuid4

import pytest

from src.domain.entities.base import AggregateRoot, Entity
from src.domain.entities.training_job import (
    TrainingConfig,
    TrainingJob,
    TrainingJobStatus,
    TrainingTrigger,
)
from src.domain.events.ml_events import RetrainingTriggeredEvent


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class TestTrainingJobStatusEnum:
    """Tests for the TrainingJobStatus StrEnum."""

    def test_values(self):
        assert TrainingJobStatus.PENDING.value == "pending"
        assert TrainingJobStatus.PREPARING_DATA.value == "preparing_data"
        assert TrainingJobStatus.TRAINING.value == "training"
        assert TrainingJobStatus.EVALUATING.value == "evaluating"
        assert TrainingJobStatus.COMPLETED.value == "completed"
        assert TrainingJobStatus.FAILED.value == "failed"
        assert TrainingJobStatus.CANCELLED.value == "cancelled"

    def test_is_str_enum(self):
        # StrEnum members behave like strings.
        assert TrainingJobStatus.PENDING == "pending"
        assert str(TrainingJobStatus.TRAINING) == "training"

    def test_member_count(self):
        assert len(list(TrainingJobStatus)) == 7

    def test_lookup_by_value(self):
        assert TrainingJobStatus("completed") is TrainingJobStatus.COMPLETED


class TestTrainingTriggerEnum:
    """Tests for the TrainingTrigger StrEnum."""

    def test_values(self):
        assert TrainingTrigger.MANUAL.value == "manual"
        assert TrainingTrigger.SCHEDULED.value == "scheduled"
        assert TrainingTrigger.PERFORMANCE_DEGRADATION.value == "performance_degradation"
        assert TrainingTrigger.DATA_DRIFT.value == "data_drift"
        assert TrainingTrigger.NEW_DATA_THRESHOLD.value == "new_data_threshold"

    def test_is_str_enum(self):
        assert TrainingTrigger.MANUAL == "manual"

    def test_member_count(self):
        assert len(list(TrainingTrigger)) == 5

    def test_lookup_by_value(self):
        assert TrainingTrigger("data_drift") is TrainingTrigger.DATA_DRIFT


# ---------------------------------------------------------------------------
# TrainingConfig value object
# ---------------------------------------------------------------------------
class TestTrainingConfig:
    """Tests for the TrainingConfig frozen dataclass."""

    def test_creation_required_fields_and_defaults(self):
        dataset_id = uuid4()
        config = TrainingConfig(base_model="mistral-7b", dataset_id=dataset_id)

        assert config.base_model == "mistral-7b"
        assert config.dataset_id == dataset_id
        # Defaults
        assert config.batch_size == 4
        assert config.learning_rate == 2e-5
        assert config.num_epochs == 3
        assert config.max_seq_length == 2048
        assert config.lora_rank == 8
        assert config.lora_alpha == 16
        assert config.use_rlhf is False
        assert config.gradient_accumulation_steps == 4
        assert config.warmup_steps == 100
        assert config.eval_steps == 500
        assert config.save_steps == 1000
        assert config.fp16 is True
        assert config.bf16 is False

    def test_creation_with_all_fields(self):
        dataset_id = uuid4()
        config = TrainingConfig(
            base_model="llama-3",
            dataset_id=dataset_id,
            batch_size=8,
            learning_rate=1e-4,
            num_epochs=5,
            max_seq_length=4096,
            lora_rank=16,
            lora_alpha=32,
            use_rlhf=True,
            gradient_accumulation_steps=2,
            warmup_steps=200,
            eval_steps=250,
            save_steps=500,
            fp16=False,
            bf16=True,
        )

        assert config.batch_size == 8
        assert config.learning_rate == 1e-4
        assert config.num_epochs == 5
        assert config.use_rlhf is True
        assert config.bf16 is True
        assert config.fp16 is False

    def test_is_frozen(self):
        config = TrainingConfig(base_model="mistral-7b", dataset_id=uuid4())
        with pytest.raises((AttributeError, Exception)):
            config.batch_size = 99  # type: ignore[misc]

    def test_equality(self):
        dataset_id = uuid4()
        a = TrainingConfig(base_model="m", dataset_id=dataset_id)
        b = TrainingConfig(base_model="m", dataset_id=dataset_id)
        assert a == b


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_config() -> TrainingConfig:
    return TrainingConfig(base_model="mistral-7b", dataset_id=uuid4())


def _configured_job(
    trigger: TrainingTrigger = TrainingTrigger.MANUAL,
    current_model_id: UUID | None = None,
) -> TrainingJob:
    job = TrainingJob(name="job-1", trigger=trigger)
    job.configure(_make_config(), current_model_id=current_model_id)
    return job


def _started_job(
    trigger: TrainingTrigger = TrainingTrigger.MANUAL,
    current_model_id: UUID | None = None,
) -> TrainingJob:
    job = _configured_job(trigger=trigger, current_model_id=current_model_id)
    job.start(mlflow_run_id="run-123")
    return job


def _evaluating_job() -> TrainingJob:
    job = _started_job()
    job.start_training_phase()
    job.start_evaluation_phase()
    return job


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------
class TestTrainingJobConstruction:
    """Tests for TrainingJob construction and defaults."""

    def test_default_construction(self):
        job = TrainingJob()

        assert isinstance(job, TrainingJob)
        assert isinstance(job, AggregateRoot)
        assert isinstance(job, Entity)
        assert isinstance(job.id, UUID)
        assert job.name == ""
        assert job.trigger == TrainingTrigger.MANUAL
        assert job.status == TrainingJobStatus.PENDING
        assert job.config is None
        assert job.current_model_id is None
        assert job.output_model_id is None
        assert job.mlflow_run_id is None
        assert job.duration_seconds is None
        assert job.metrics == {}
        assert job.is_completed is False
        assert job.is_failed is False
        assert job.domain_events == []

    def test_construction_with_args(self):
        job_id = uuid4()
        job = TrainingJob(
            id=job_id,
            name="my-job",
            trigger=TrainingTrigger.SCHEDULED,
            status=TrainingJobStatus.PENDING,
        )

        assert job.id == job_id
        assert job.name == "my-job"
        assert job.trigger == TrainingTrigger.SCHEDULED

    def test_construction_generates_unique_ids(self):
        a = TrainingJob()
        b = TrainingJob()
        assert a.id != b.id

    def test_timestamps_set(self):
        job = TrainingJob()
        assert isinstance(job.created_at, datetime)
        assert isinstance(job.updated_at, datetime)

    def test_metrics_property_returns_copy(self):
        job = TrainingJob()
        metrics = job.metrics
        metrics["leaked"] = 1.0
        # External mutation must not affect internal state.
        assert job.metrics == {}


# ---------------------------------------------------------------------------
# configure()
# ---------------------------------------------------------------------------
class TestConfigure:
    """Tests for TrainingJob.configure()."""

    def test_configure_pending_job(self):
        job = TrainingJob()
        config = _make_config()
        job.configure(config)

        assert job.config is config
        assert job.current_model_id is None

    def test_configure_with_current_model_id(self):
        job = TrainingJob()
        model_id = uuid4()
        job.configure(_make_config(), current_model_id=model_id)

        assert job.current_model_id == model_id

    def test_configure_touches_updated_at(self):
        job = TrainingJob()
        before = job.updated_at
        job.configure(_make_config())
        assert job.updated_at >= before

    def test_configure_non_pending_raises(self):
        job = _started_job()  # now PREPARING_DATA
        with pytest.raises(ValueError, match="Can only configure pending jobs"):
            job.configure(_make_config())


# ---------------------------------------------------------------------------
# start()
# ---------------------------------------------------------------------------
class TestStart:
    """Tests for TrainingJob.start()."""

    def test_start_configured_job(self):
        job = _configured_job()
        job.start(mlflow_run_id="run-abc", prefect_flow_run_id="prefect-1")

        assert job.status == TrainingJobStatus.PREPARING_DATA
        assert job.mlflow_run_id == "run-abc"

    def test_start_without_config_raises(self):
        job = TrainingJob()  # pending but unconfigured
        with pytest.raises(ValueError, match="must be configured before starting"):
            job.start(mlflow_run_id="run-abc")

    def test_start_non_pending_raises(self):
        job = _started_job()  # PREPARING_DATA
        with pytest.raises(ValueError, match="Can only start pending jobs"):
            job.start(mlflow_run_id="run-xyz")

    def test_start_manual_trigger_emits_no_event(self):
        # MANUAL trigger never emits a RetrainingTriggeredEvent.
        job = _configured_job(
            trigger=TrainingTrigger.MANUAL, current_model_id=uuid4()
        )
        job.start(mlflow_run_id="run-abc")
        assert job.domain_events == []

    def test_start_automatic_trigger_without_current_model_emits_no_event(self):
        # Automatic trigger but no current_model_id -> no event.
        job = _configured_job(
            trigger=TrainingTrigger.DATA_DRIFT, current_model_id=None
        )
        job.start(mlflow_run_id="run-abc")
        assert job.domain_events == []

    def test_start_automatic_trigger_emits_retraining_event(self):
        current_model_id = uuid4()
        job = _configured_job(
            trigger=TrainingTrigger.PERFORMANCE_DEGRADATION,
            current_model_id=current_model_id,
        )
        job.update_metrics({"f1": 0.7})
        job.start(mlflow_run_id="run-abc")

        events = job.domain_events
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, RetrainingTriggeredEvent)
        assert event.aggregate_id == job.id
        assert event.trigger_reason == TrainingTrigger.PERFORMANCE_DEGRADATION.value
        assert event.current_model_id == current_model_id
        assert event.metrics == {"f1": 0.7}

    def test_start_scheduled_trigger_emits_event(self):
        job = _configured_job(
            trigger=TrainingTrigger.SCHEDULED, current_model_id=uuid4()
        )
        job.start(mlflow_run_id="run-abc")
        assert len(job.domain_events) == 1
        assert job.domain_events[0].trigger_reason == "scheduled"


# ---------------------------------------------------------------------------
# State machine — happy path transitions
# ---------------------------------------------------------------------------
class TestStateMachineHappyPath:
    """Tests for the valid phase transitions."""

    def test_start_training_phase(self):
        job = _started_job()  # PREPARING_DATA
        job.start_training_phase()
        assert job.status == TrainingJobStatus.TRAINING

    def test_start_evaluation_phase(self):
        job = _started_job()
        job.start_training_phase()
        job.start_evaluation_phase()
        assert job.status == TrainingJobStatus.EVALUATING

    def test_full_lifecycle_to_completed(self):
        job = _evaluating_job()
        output_model_id = uuid4()
        job.complete(output_model_id, {"accuracy": 0.95}, logs_path="/logs/x")

        assert job.status == TrainingJobStatus.COMPLETED
        assert job.is_completed is True
        assert job.is_failed is False
        assert job.output_model_id == output_model_id
        assert job.metrics["accuracy"] == 0.95


# ---------------------------------------------------------------------------
# State machine — invalid transitions raise ValueError
# ---------------------------------------------------------------------------
class TestStateMachineInvalidTransitions:
    """Tests that transitions from the wrong state raise ValueError."""

    def test_start_training_phase_from_pending_raises(self):
        job = TrainingJob()
        with pytest.raises(ValueError, match="must be in preparing_data status"):
            job.start_training_phase()

    def test_start_evaluation_phase_from_preparing_raises(self):
        job = _started_job()  # PREPARING_DATA, not TRAINING
        with pytest.raises(ValueError, match="must be in training status"):
            job.start_evaluation_phase()

    def test_complete_from_training_raises(self):
        job = _started_job()
        job.start_training_phase()  # TRAINING, not EVALUATING
        with pytest.raises(ValueError, match="must be in evaluating status"):
            job.complete(uuid4(), {"accuracy": 0.9})

    def test_complete_from_pending_raises(self):
        job = TrainingJob()
        with pytest.raises(ValueError, match="must be in evaluating status"):
            job.complete(uuid4(), {})


# ---------------------------------------------------------------------------
# complete()
# ---------------------------------------------------------------------------
class TestComplete:
    """Tests for TrainingJob.complete()."""

    def test_complete_merges_metrics(self):
        job = _evaluating_job()
        job.update_metrics({"loss": 0.3})
        job.complete(uuid4(), {"accuracy": 0.9})

        assert job.metrics["loss"] == 0.3
        assert job.metrics["accuracy"] == 0.9

    def test_complete_logs_path_optional(self):
        job = _evaluating_job()
        job.complete(uuid4(), {})
        # to_dict reflects None logs_path.
        assert job.to_dict()["logs_path"] is None

    def test_complete_calculates_duration(self):
        job = _evaluating_job()
        job.complete(uuid4(), {})
        assert job.duration_seconds is not None
        assert job.duration_seconds >= 0


# ---------------------------------------------------------------------------
# fail()
# ---------------------------------------------------------------------------
class TestFail:
    """Tests for TrainingJob.fail()."""

    def test_fail_from_pending(self):
        job = TrainingJob()
        job.fail("boom")

        assert job.status == TrainingJobStatus.FAILED
        assert job.is_failed is True
        assert job.to_dict()["error_message"] == "boom"

    def test_fail_from_training(self):
        job = _started_job()
        job.start_training_phase()
        job.fail("oom")
        assert job.status == TrainingJobStatus.FAILED

    def test_fail_calculates_duration_when_started(self):
        job = _started_job()
        job.fail("boom")
        assert job.duration_seconds is not None

    def test_fail_no_duration_when_not_started(self):
        job = TrainingJob()  # never started
        job.fail("boom")
        assert job.duration_seconds is None

    def test_fail_completed_job_raises(self):
        job = _evaluating_job()
        job.complete(uuid4(), {})
        with pytest.raises(ValueError, match="Cannot fail job with status"):
            job.fail("late")

    def test_fail_cancelled_job_raises(self):
        job = TrainingJob()
        job.cancel()
        with pytest.raises(ValueError, match="Cannot fail job with status"):
            job.fail("late")


# ---------------------------------------------------------------------------
# cancel()
# ---------------------------------------------------------------------------
class TestCancel:
    """Tests for TrainingJob.cancel()."""

    def test_cancel_from_pending(self):
        job = TrainingJob()
        job.cancel()
        assert job.status == TrainingJobStatus.CANCELLED

    def test_cancel_from_training(self):
        job = _started_job()
        job.start_training_phase()
        job.cancel()
        assert job.status == TrainingJobStatus.CANCELLED

    def test_cancel_calculates_duration_when_started(self):
        job = _started_job()
        job.cancel()
        assert job.duration_seconds is not None

    def test_cancel_no_duration_when_not_started(self):
        job = TrainingJob()
        job.cancel()
        assert job.duration_seconds is None

    def test_cancel_completed_job_raises(self):
        job = _evaluating_job()
        job.complete(uuid4(), {})
        with pytest.raises(ValueError, match="Cannot cancel job with status"):
            job.cancel()

    def test_cancel_failed_job_raises(self):
        job = TrainingJob()
        job.fail("boom")
        with pytest.raises(ValueError, match="Cannot cancel job with status"):
            job.cancel()


# ---------------------------------------------------------------------------
# update_metrics()
# ---------------------------------------------------------------------------
class TestUpdateMetrics:
    """Tests for TrainingJob.update_metrics()."""

    def test_update_metrics_merges(self):
        job = TrainingJob()
        job.update_metrics({"loss": 1.0})
        job.update_metrics({"accuracy": 0.5})
        assert job.metrics == {"loss": 1.0, "accuracy": 0.5}

    def test_update_metrics_overwrites_existing_key(self):
        job = TrainingJob()
        job.update_metrics({"loss": 1.0})
        job.update_metrics({"loss": 0.2})
        assert job.metrics == {"loss": 0.2}

    def test_update_metrics_touches_updated_at(self):
        job = TrainingJob()
        before = job.updated_at
        job.update_metrics({"loss": 0.1})
        assert job.updated_at >= before

    def test_update_metrics_allowed_in_any_status(self):
        # update_metrics has no status guard; it should work even after completion.
        job = _evaluating_job()
        job.complete(uuid4(), {})
        job.update_metrics({"post": 1.0})
        assert job.metrics["post"] == 1.0


# ---------------------------------------------------------------------------
# to_dict()
# ---------------------------------------------------------------------------
class TestToDict:
    """Tests for TrainingJob.to_dict() serialization."""

    def test_to_dict_minimal_job(self):
        job = TrainingJob(name="serialize-me", trigger=TrainingTrigger.MANUAL)
        d = job.to_dict()

        # Base fields from AggregateRoot/Entity.
        assert d["id"] == str(job.id)
        assert "created_at" in d
        assert "updated_at" in d
        # TrainingJob fields.
        assert d["name"] == "serialize-me"
        assert d["trigger"] == "manual"
        assert d["status"] == "pending"
        assert d["config"] is None
        assert d["current_model_id"] is None
        assert d["output_model_id"] is None
        assert d["mlflow_run_id"] is None
        assert d["prefect_flow_run_id"] is None
        assert d["started_at"] is None
        assert d["completed_at"] is None
        assert d["duration_seconds"] is None
        assert d["metrics"] == {}
        assert d["error_message"] is None
        assert d["logs_path"] is None

    def test_to_dict_config_serialized_as_dict(self):
        job = TrainingJob()
        config = _make_config()
        job.configure(config)
        d = job.to_dict()

        assert isinstance(d["config"], dict)
        assert d["config"]["base_model"] == "mistral-7b"
        # dataset_id stays a UUID inside the config __dict__ dump.
        assert d["config"]["dataset_id"] == config.dataset_id

    def test_to_dict_completed_job(self):
        job = _evaluating_job()
        output_model_id = uuid4()
        current_model_id = job.current_model_id
        job.complete(output_model_id, {"accuracy": 0.91}, logs_path="/logs/run")
        d = job.to_dict()

        assert d["status"] == "completed"
        assert d["output_model_id"] == str(output_model_id)
        assert d["mlflow_run_id"] == "run-123"
        assert d["started_at"] is not None
        assert d["completed_at"] is not None
        assert d["duration_seconds"] is not None
        assert d["metrics"] == {"accuracy": 0.91}
        assert d["logs_path"] == "/logs/run"

    def test_to_dict_current_model_id_stringified(self):
        model_id = uuid4()
        job = TrainingJob()
        job.configure(_make_config(), current_model_id=model_id)
        assert job.to_dict()["current_model_id"] == str(model_id)


# ---------------------------------------------------------------------------
# Domain event management (inherited from AggregateRoot)
# ---------------------------------------------------------------------------
class TestDomainEvents:
    """Tests for domain event accumulation and clearing."""

    def test_clear_domain_events(self):
        job = _configured_job(
            trigger=TrainingTrigger.DATA_DRIFT, current_model_id=uuid4()
        )
        job.start(mlflow_run_id="run-abc")
        assert len(job.domain_events) == 1

        job.clear_domain_events()
        assert job.domain_events == []

    def test_domain_events_returns_copy(self):
        job = TrainingJob()
        events = job.domain_events
        events.append("intruder")
        assert job.domain_events == []
