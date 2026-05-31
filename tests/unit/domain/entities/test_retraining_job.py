"""Unit tests for the RetrainingJob domain entity (issue #161, batch 3 coverage).

Covers:
- RetrainingStatus / RetrainingTriggerReason StrEnums
- RetrainingJob entity: construction & defaults, invariants, property accessors
  (with defensive copies on dict properties), lifecycle transitions
  (start/complete/fail/cancel), config/metadata mutation, duration computation,
  terminal-state detection, and to_dict serialization.

The production code is the source of truth; these tests assert its real
behaviour. Notably:
- Lifecycle methods (start/complete/fail/cancel) stamp NAIVE datetimes via
  datetime.utcnow(), whereas the base Entity uses timezone-aware utc_now().
- get_duration_seconds() subtracts whatever datetimes are present, so mixing a
  timezone-aware started_at (passed via the constructor) with the naive
  utcnow() fallback raises a TypeError. This is documented as a regression test.
"""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest

from src.domain.entities.base import Entity
from src.domain.entities.retraining_job import (
    RetrainingJob,
    RetrainingStatus,
    RetrainingTriggerReason,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class TestRetrainingStatusEnum:
    """Tests for the RetrainingStatus StrEnum."""

    def test_values(self):
        assert RetrainingStatus.PENDING.value == "pending"
        assert RetrainingStatus.RUNNING.value == "running"
        assert RetrainingStatus.COMPLETED.value == "completed"
        assert RetrainingStatus.FAILED.value == "failed"
        assert RetrainingStatus.CANCELLED.value == "cancelled"

    def test_is_str_enum(self):
        assert RetrainingStatus.RUNNING == "running"
        assert str(RetrainingStatus.COMPLETED) == "completed"

    def test_member_count(self):
        assert len(list(RetrainingStatus)) == 5

    def test_lookup_by_value(self):
        assert RetrainingStatus("failed") is RetrainingStatus.FAILED


class TestRetrainingTriggerReasonEnum:
    """Tests for the RetrainingTriggerReason StrEnum."""

    def test_values(self):
        assert RetrainingTriggerReason.DRIFT_DETECTED.value == "drift_detected"
        assert RetrainingTriggerReason.ERROR_THRESHOLD.value == "error_threshold"
        assert RetrainingTriggerReason.SUFFICIENT_DATA.value == "sufficient_data"
        assert RetrainingTriggerReason.MANUAL.value == "manual"
        assert RetrainingTriggerReason.SCHEDULED.value == "scheduled"
        assert RetrainingTriggerReason.FEEDBACK_VOLUME.value == "feedback_volume"

    def test_is_str_enum(self):
        assert RetrainingTriggerReason.MANUAL == "manual"

    def test_member_count(self):
        assert len(list(RetrainingTriggerReason)) == 6

    def test_lookup_by_value(self):
        assert (
            RetrainingTriggerReason("scheduled") is RetrainingTriggerReason.SCHEDULED
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def make_job(**overrides) -> RetrainingJob:
    """Build a RetrainingJob with sensible defaults, overridable per test."""
    params = {
        "trigger_reason": RetrainingTriggerReason.DRIFT_DETECTED,
        "model_name": "classifier-v1",
        "base_model_version": "1.0.0",
        "new_samples_count": 500,
    }
    params.update(overrides)
    return RetrainingJob(**params)


# ---------------------------------------------------------------------------
# Construction & defaults
# ---------------------------------------------------------------------------
class TestRetrainingJobConstruction:
    """Construction, defaults, and inheritance."""

    def test_minimal_construction_required_fields(self):
        job = make_job()

        assert job.trigger_reason == RetrainingTriggerReason.DRIFT_DETECTED
        assert job.model_name == "classifier-v1"
        assert job.base_model_version == "1.0.0"
        assert job.new_samples_count == 500

    def test_defaults(self):
        job = make_job()

        # Status defaults to PENDING.
        assert job.status == RetrainingStatus.PENDING
        # Optional fields default to None.
        assert job.fine_tuning_job_id is None
        assert job.new_model_version is None
        assert job.drift_report_id is None
        assert job.started_at is None
        assert job.completed_at is None
        assert job.error_message is None
        # dict fields default to empty dicts.
        assert job.config == {}
        assert job.metrics == {}
        assert job.metadata == {}

    def test_is_entity_subclass(self):
        job = make_job()
        assert isinstance(job, Entity)

    def test_auto_generated_id_is_uuid(self):
        job = make_job()
        assert isinstance(job.id, UUID)

    def test_explicit_id_preserved(self):
        explicit = uuid4()
        job = make_job(id=explicit)
        assert job.id == explicit

    def test_base_timestamps_set(self):
        job = make_job()
        assert isinstance(job.created_at, datetime)
        assert isinstance(job.updated_at, datetime)

    def test_construction_with_all_fields(self):
        job_id = uuid4()
        drift_id = uuid4()
        started = datetime(2026, 1, 1, 10, 0, 0)
        completed = datetime(2026, 1, 1, 11, 0, 0)
        job = RetrainingJob(
            trigger_reason=RetrainingTriggerReason.MANUAL,
            model_name="m",
            base_model_version="2.0",
            new_samples_count=10,
            id=job_id,
            status=RetrainingStatus.RUNNING,
            fine_tuning_job_id="ft-123",
            new_model_version="2.1",
            drift_report_id=drift_id,
            started_at=started,
            completed_at=completed,
            error_message="boom",
            config={"epochs": 3},
            metrics={"loss": 0.1},
            metadata={"owner": "ops"},
        )

        assert job.id == job_id
        assert job.status == RetrainingStatus.RUNNING
        assert job.fine_tuning_job_id == "ft-123"
        assert job.new_model_version == "2.1"
        assert job.drift_report_id == drift_id
        assert job.started_at == started
        assert job.completed_at == completed
        assert job.error_message == "boom"
        assert job.config == {"epochs": 3}
        assert job.metrics == {"loss": 0.1}
        assert job.metadata == {"owner": "ops"}

    def test_explicit_status_none_falls_back_to_pending(self):
        job = make_job(status=None)
        assert job.status == RetrainingStatus.PENDING

    def test_zero_samples_allowed(self):
        # No validation on new_samples_count; the entity accepts any int.
        job = make_job(new_samples_count=0)
        assert job.new_samples_count == 0


# ---------------------------------------------------------------------------
# Property defensive copies
# ---------------------------------------------------------------------------
class TestPropertyCopies:
    """config/metrics/metadata properties must return copies, not references."""

    def test_config_property_returns_copy(self):
        original = {"epochs": 5}
        job = make_job(config=original)
        returned = job.config
        returned["epochs"] = 999
        # Mutating the returned dict must not affect the entity.
        assert job.config == {"epochs": 5}
        # And the original passed-in dict is preserved by the entity reference.
        assert original == {"epochs": 5}

    def test_metrics_property_returns_copy(self):
        job = make_job(metrics={"loss": 0.2})
        returned = job.metrics
        returned["loss"] = 99.9
        assert job.metrics == {"loss": 0.2}

    def test_metadata_property_returns_copy(self):
        job = make_job(metadata={"k": "v"})
        returned = job.metadata
        returned["k"] = "changed"
        assert job.metadata == {"k": "v"}


# ---------------------------------------------------------------------------
# start()
# ---------------------------------------------------------------------------
class TestStart:
    """Tests for the start() transition."""

    def test_start_sets_running_and_fine_tuning_id(self):
        job = make_job()
        job.start("ft-abc")

        assert job.status == RetrainingStatus.RUNNING
        assert job.fine_tuning_job_id == "ft-abc"
        assert job.started_at is not None
        assert isinstance(job.started_at, datetime)

    def test_start_touches_updated_at(self):
        job = make_job()
        before = job.updated_at
        job.start("ft-abc")
        assert job.updated_at >= before

    def test_start_does_not_set_completed_at(self):
        job = make_job()
        job.start("ft-abc")
        assert job.completed_at is None


# ---------------------------------------------------------------------------
# complete()
# ---------------------------------------------------------------------------
class TestComplete:
    """Tests for the complete() transition."""

    def test_complete_sets_completed_and_version(self):
        job = make_job()
        job.start("ft-abc")
        job.complete("2.0.0")

        assert job.status == RetrainingStatus.COMPLETED
        assert job.new_model_version == "2.0.0"
        assert job.completed_at is not None

    def test_complete_with_metrics(self):
        job = make_job()
        job.complete("2.0.0", metrics={"accuracy": 0.95})
        assert job.metrics == {"accuracy": 0.95}

    def test_complete_without_metrics_keeps_existing(self):
        job = make_job(metrics={"accuracy": 0.5})
        job.complete("2.0.0")
        # metrics is only replaced when a truthy metrics arg is passed.
        assert job.metrics == {"accuracy": 0.5}

    def test_complete_empty_metrics_keeps_existing(self):
        # Empty dict is falsy, so it does NOT overwrite existing metrics.
        job = make_job(metrics={"accuracy": 0.5})
        job.complete("2.0.0", metrics={})
        assert job.metrics == {"accuracy": 0.5}

    def test_complete_replaces_metrics_entirely(self):
        # complete() reassigns (does not merge) metrics.
        job = make_job(metrics={"old": 1})
        job.complete("2.0.0", metrics={"new": 2})
        assert job.metrics == {"new": 2}
        assert "old" not in job.metrics

    def test_complete_touches_updated_at(self):
        job = make_job()
        before = job.updated_at
        job.complete("2.0.0")
        assert job.updated_at >= before


# ---------------------------------------------------------------------------
# fail()
# ---------------------------------------------------------------------------
class TestFail:
    """Tests for the fail() transition."""

    def test_fail_sets_failed_and_error(self):
        job = make_job()
        job.fail("training crashed")

        assert job.status == RetrainingStatus.FAILED
        assert job.error_message == "training crashed"
        assert job.completed_at is not None

    def test_fail_touches_updated_at(self):
        job = make_job()
        before = job.updated_at
        job.fail("oops")
        assert job.updated_at >= before


# ---------------------------------------------------------------------------
# cancel()
# ---------------------------------------------------------------------------
class TestCancel:
    """Tests for the cancel() transition (only valid from PENDING/RUNNING)."""

    def test_cancel_from_pending(self):
        job = make_job()
        job.cancel()

        assert job.status == RetrainingStatus.CANCELLED
        assert job.completed_at is not None

    def test_cancel_from_running(self):
        job = make_job()
        job.start("ft-abc")
        job.cancel()
        assert job.status == RetrainingStatus.CANCELLED

    def test_cancel_from_completed_is_noop(self):
        job = make_job()
        job.complete("2.0.0")
        completed_at_before = job.completed_at
        job.cancel()
        # Already terminal: status stays COMPLETED, completed_at unchanged.
        assert job.status == RetrainingStatus.COMPLETED
        assert job.completed_at == completed_at_before

    def test_cancel_from_failed_is_noop(self):
        job = make_job()
        job.fail("err")
        job.cancel()
        assert job.status == RetrainingStatus.FAILED

    def test_cancel_twice_is_noop(self):
        job = make_job()
        job.cancel()
        first_completed = job.completed_at
        job.cancel()
        assert job.status == RetrainingStatus.CANCELLED
        assert job.completed_at == first_completed


# ---------------------------------------------------------------------------
# update_config / update_metadata
# ---------------------------------------------------------------------------
class TestUpdateConfigAndMetadata:
    """Mutation helpers merge (not replace) and touch updated_at."""

    def test_update_config_merges(self):
        job = make_job(config={"epochs": 3})
        job.update_config({"lr": 0.01})
        assert job.config == {"epochs": 3, "lr": 0.01}

    def test_update_config_overwrites_existing_key(self):
        job = make_job(config={"epochs": 3})
        job.update_config({"epochs": 10})
        assert job.config == {"epochs": 10}

    def test_update_config_touches_updated_at(self):
        job = make_job()
        before = job.updated_at
        job.update_config({"a": 1})
        assert job.updated_at >= before

    def test_update_metadata_merges(self):
        job = make_job(metadata={"owner": "ops"})
        job.update_metadata({"priority": "high"})
        assert job.metadata == {"owner": "ops", "priority": "high"}

    def test_update_metadata_overwrites_existing_key(self):
        job = make_job(metadata={"owner": "ops"})
        job.update_metadata({"owner": "ml"})
        assert job.metadata == {"owner": "ml"}

    def test_update_metadata_touches_updated_at(self):
        job = make_job()
        before = job.updated_at
        job.update_metadata({"k": "v"})
        assert job.updated_at >= before


# ---------------------------------------------------------------------------
# get_duration_seconds()
# ---------------------------------------------------------------------------
class TestGetDurationSeconds:
    """Tests for duration computation."""

    def test_returns_none_when_not_started(self):
        job = make_job()
        assert job.get_duration_seconds() is None

    def test_duration_with_explicit_naive_timestamps(self):
        started = datetime(2026, 1, 1, 10, 0, 0)
        completed = started + timedelta(seconds=120)
        job = make_job(started_at=started, completed_at=completed)
        assert job.get_duration_seconds() == 120.0

    def test_duration_after_start_complete_lifecycle(self):
        job = make_job()
        job.start("ft-abc")
        job.complete("2.0.0")
        duration = job.get_duration_seconds()
        assert duration is not None
        assert duration >= 0.0

    def test_duration_running_uses_now_fallback(self):
        # started_at set via start() is naive (utcnow); fallback now is also
        # naive, so subtraction works and yields a non-negative duration.
        job = make_job()
        job.start("ft-abc")
        duration = job.get_duration_seconds()
        assert duration is not None
        assert duration >= 0.0

    def test_duration_mixed_tz_raises_typeerror_regression(self):
        # REGRESSION: a timezone-aware started_at (constructor) combined with
        # the naive datetime.utcnow() fallback (no completed_at) raises a
        # TypeError ("can't subtract offset-naive and offset-aware datetimes").
        # This documents the real production behaviour.
        from datetime import UTC

        aware_started = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
        job = make_job(started_at=aware_started)
        with pytest.raises(TypeError):
            job.get_duration_seconds()


# ---------------------------------------------------------------------------
# is_terminal_state()
# ---------------------------------------------------------------------------
class TestIsTerminalState:
    """Terminal state detection."""

    def test_pending_not_terminal(self):
        assert make_job().is_terminal_state() is False

    def test_running_not_terminal(self):
        job = make_job()
        job.start("ft-abc")
        assert job.is_terminal_state() is False

    def test_completed_is_terminal(self):
        job = make_job()
        job.complete("2.0.0")
        assert job.is_terminal_state() is True

    def test_failed_is_terminal(self):
        job = make_job()
        job.fail("err")
        assert job.is_terminal_state() is True

    def test_cancelled_is_terminal(self):
        job = make_job()
        job.cancel()
        assert job.is_terminal_state() is True


# ---------------------------------------------------------------------------
# to_dict()
# ---------------------------------------------------------------------------
class TestToDict:
    """Serialization to a dictionary."""

    def test_includes_base_fields(self):
        job = make_job()
        d = job.to_dict()
        assert d["id"] == str(job.id)
        assert "created_at" in d
        assert "updated_at" in d

    def test_includes_entity_fields(self):
        job = make_job()
        d = job.to_dict()
        assert d["trigger_reason"] == "drift_detected"
        assert d["model_name"] == "classifier-v1"
        assert d["base_model_version"] == "1.0.0"
        assert d["new_samples_count"] == 500
        assert d["status"] == "pending"

    def test_none_optionals_serialized_as_none(self):
        job = make_job()
        d = job.to_dict()
        assert d["fine_tuning_job_id"] is None
        assert d["new_model_version"] is None
        assert d["drift_report_id"] is None
        assert d["started_at"] is None
        assert d["completed_at"] is None
        assert d["error_message"] is None
        assert d["duration_seconds"] is None
        assert d["is_terminal"] is False

    def test_drift_report_id_stringified(self):
        drift_id = uuid4()
        job = make_job(drift_report_id=drift_id)
        d = job.to_dict()
        assert d["drift_report_id"] == str(drift_id)

    def test_timestamps_isoformat_when_present(self):
        started = datetime(2026, 1, 1, 10, 0, 0)
        completed = datetime(2026, 1, 1, 10, 30, 0)
        job = make_job(started_at=started, completed_at=completed)
        d = job.to_dict()
        assert d["started_at"] == started.isoformat()
        assert d["completed_at"] == completed.isoformat()

    def test_dict_fields_included(self):
        job = make_job(
            config={"epochs": 3}, metrics={"loss": 0.1}, metadata={"owner": "ops"}
        )
        d = job.to_dict()
        assert d["config"] == {"epochs": 3}
        assert d["metrics"] == {"loss": 0.1}
        assert d["metadata"] == {"owner": "ops"}

    def test_terminal_and_duration_after_completion(self):
        started = datetime(2026, 1, 1, 10, 0, 0)
        completed = datetime(2026, 1, 1, 10, 0, 30)
        job = make_job(
            status=RetrainingStatus.COMPLETED,
            started_at=started,
            completed_at=completed,
        )
        d = job.to_dict()
        assert d["is_terminal"] is True
        assert d["duration_seconds"] == 30.0


# ---------------------------------------------------------------------------
# Entity identity semantics (inherited)
# ---------------------------------------------------------------------------
class TestIdentitySemantics:
    """Equality and hashing inherited from Entity are by ID."""

    def test_equality_by_id(self):
        shared = uuid4()
        a = make_job(id=shared)
        b = make_job(id=shared, model_name="other", new_samples_count=1)
        assert a == b

    def test_inequality_different_id(self):
        assert make_job() != make_job()

    def test_not_equal_to_non_entity(self):
        assert make_job() != "not-an-entity"

    def test_hashable_by_id(self):
        shared = uuid4()
        a = make_job(id=shared)
        b = make_job(id=shared)
        assert hash(a) == hash(b)
        assert len({a, b}) == 1
