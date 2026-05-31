"""Unit tests for the DriftReport domain entity (issue #161, batch 3 coverage).

Covers:
- DriftType / DriftSeverity StrEnums (values, members, str behaviour).
- DriftReport entity: construction (required + optional fields),
  severity auto-derivation invariant from drift_score, deviation
  percentage calculation, action-required classification,
  details mutation/touch behaviour, and to_dict serialization.

The production code is the source of truth; these tests assert its real
behaviour. No production API is invented.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from src.domain.entities.base import Entity
from src.domain.entities.drift_report import (
    DriftReport,
    DriftSeverity,
    DriftType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def make_report(**overrides):
    """Build a DriftReport with sensible defaults, overridable per test."""
    params = {
        "model_name": "matcher",
        "model_version": "1.2.0",
        "drift_type": DriftType.DATA_DRIFT,
        "metric_name": "psi",
        "current_value": 0.42,
        "baseline_value": 0.30,
        "drift_score": 0.25,
        "is_drifted": False,
    }
    params.update(overrides)
    return DriftReport(**params)


# ---------------------------------------------------------------------------
# DriftType enum
# ---------------------------------------------------------------------------
class TestDriftTypeEnum:
    """Tests for the DriftType StrEnum."""

    def test_values(self):
        assert DriftType.DATA_DRIFT.value == "data_drift"
        assert DriftType.CONCEPT_DRIFT.value == "concept_drift"
        assert DriftType.PREDICTION_DRIFT.value == "prediction_drift"
        assert DriftType.PERFORMANCE_DRIFT.value == "performance_drift"

    def test_is_str_enum(self):
        assert DriftType.DATA_DRIFT == "data_drift"
        assert str(DriftType.PERFORMANCE_DRIFT) == "performance_drift"

    def test_member_count(self):
        assert len(list(DriftType)) == 4

    def test_lookup_by_value(self):
        assert DriftType("concept_drift") is DriftType.CONCEPT_DRIFT


# ---------------------------------------------------------------------------
# DriftSeverity enum
# ---------------------------------------------------------------------------
class TestDriftSeverityEnum:
    """Tests for the DriftSeverity StrEnum."""

    def test_values(self):
        assert DriftSeverity.LOW.value == "low"
        assert DriftSeverity.MEDIUM.value == "medium"
        assert DriftSeverity.HIGH.value == "high"
        assert DriftSeverity.CRITICAL.value == "critical"

    def test_is_str_enum(self):
        assert DriftSeverity.HIGH == "high"
        assert str(DriftSeverity.CRITICAL) == "critical"

    def test_member_count(self):
        assert len(list(DriftSeverity)) == 4

    def test_lookup_by_value(self):
        assert DriftSeverity("medium") is DriftSeverity.MEDIUM


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------
class TestDriftReportConstruction:
    """Tests for DriftReport construction and property accessors."""

    def test_construction_required_fields(self):
        report = make_report()

        assert report.model_name == "matcher"
        assert report.model_version == "1.2.0"
        assert report.drift_type is DriftType.DATA_DRIFT
        assert report.metric_name == "psi"
        assert report.current_value == 0.42
        assert report.baseline_value == 0.30
        assert report.drift_score == 0.25
        assert report.is_drifted is False

    def test_construction_defaults_for_optionals(self):
        report = make_report()

        # severity is auto-derived (not None) when not provided
        assert report.severity is DriftSeverity.LOW
        assert report.threshold is None
        assert report.window_start is None
        assert report.window_end is None
        assert report.sample_count is None
        # details defaults to an empty dict (not None)
        assert report.details == {}

    def test_construction_all_fields(self):
        eid = uuid4()
        start = datetime(2026, 1, 1, tzinfo=UTC)
        end = datetime(2026, 1, 31, tzinfo=UTC)
        report = DriftReport(
            model_name="ranker",
            model_version="2.0.0",
            drift_type=DriftType.CONCEPT_DRIFT,
            metric_name="accuracy",
            current_value=0.70,
            baseline_value=0.90,
            drift_score=0.85,
            is_drifted=True,
            id=eid,
            severity=DriftSeverity.MEDIUM,
            threshold=0.5,
            window_start=start,
            window_end=end,
            sample_count=5000,
            details={"note": "spike"},
        )

        assert report.id == eid
        assert report.drift_type is DriftType.CONCEPT_DRIFT
        assert report.metric_name == "accuracy"
        assert report.current_value == 0.70
        assert report.baseline_value == 0.90
        assert report.drift_score == 0.85
        assert report.is_drifted is True
        # explicit severity overrides the auto-derived one
        assert report.severity is DriftSeverity.MEDIUM
        assert report.threshold == 0.5
        assert report.window_start == start
        assert report.window_end == end
        assert report.sample_count == 5000
        assert report.details == {"note": "spike"}

    def test_is_entity_subclass(self):
        report = make_report()
        assert isinstance(report, Entity)

    def test_inherits_id_and_timestamps(self):
        report = make_report()
        assert isinstance(report.id, UUID)
        assert report.created_at is not None
        assert report.updated_at is not None

    def test_generates_unique_ids(self):
        a = make_report()
        b = make_report()
        assert a.id != b.id

    def test_provided_id_is_used(self):
        eid = uuid4()
        report = make_report(id=eid)
        assert report.id == eid


# ---------------------------------------------------------------------------
# Severity invariant (auto-derivation from drift_score)
# ---------------------------------------------------------------------------
class TestSeverityInvariant:
    """Severity is derived from the drift_score when not explicitly given."""

    @pytest.mark.parametrize(
        "score, expected",
        [
            (0.0, DriftSeverity.LOW),
            (0.29, DriftSeverity.LOW),
            (0.30, DriftSeverity.MEDIUM),
            (0.49, DriftSeverity.MEDIUM),
            (0.50, DriftSeverity.HIGH),
            (0.79, DriftSeverity.HIGH),
            (0.80, DriftSeverity.CRITICAL),
            (1.0, DriftSeverity.CRITICAL),
        ],
    )
    def test_auto_severity_thresholds(self, score, expected):
        report = make_report(drift_score=score)
        assert report.severity is expected

    def test_boundary_low_to_medium(self):
        assert make_report(drift_score=0.2999).severity is DriftSeverity.LOW
        assert make_report(drift_score=0.3).severity is DriftSeverity.MEDIUM

    def test_boundary_medium_to_high(self):
        assert make_report(drift_score=0.4999).severity is DriftSeverity.MEDIUM
        assert make_report(drift_score=0.5).severity is DriftSeverity.HIGH

    def test_boundary_high_to_critical(self):
        assert make_report(drift_score=0.7999).severity is DriftSeverity.HIGH
        assert make_report(drift_score=0.8).severity is DriftSeverity.CRITICAL

    def test_explicit_severity_not_overridden_even_if_inconsistent(self):
        # A low drift_score with an explicit CRITICAL severity keeps CRITICAL:
        # the constructor only auto-derives when severity is None.
        report = make_report(drift_score=0.01, severity=DriftSeverity.CRITICAL)
        assert report.severity is DriftSeverity.CRITICAL

    def test_negative_score_falls_through_to_low(self):
        # Production has no lower bound guard; negative scores map to LOW.
        report = make_report(drift_score=-0.5)
        assert report.severity is DriftSeverity.LOW

    def test_score_above_one_maps_to_critical(self):
        # No upper bound guard either; scores > 1 still map to CRITICAL.
        report = make_report(drift_score=1.5)
        assert report.severity is DriftSeverity.CRITICAL


# ---------------------------------------------------------------------------
# get_deviation_percentage
# ---------------------------------------------------------------------------
class TestDeviationPercentage:
    """Tests for get_deviation_percentage()."""

    def test_positive_deviation(self):
        report = make_report(current_value=1.2, baseline_value=1.0)
        assert report.get_deviation_percentage() == pytest.approx(20.0)

    def test_negative_deviation_is_absolute(self):
        report = make_report(current_value=0.8, baseline_value=1.0)
        # abs() makes the result positive regardless of direction.
        assert report.get_deviation_percentage() == pytest.approx(20.0)

    def test_no_deviation(self):
        report = make_report(current_value=1.0, baseline_value=1.0)
        assert report.get_deviation_percentage() == 0.0

    def test_zero_baseline_returns_zero(self):
        # Guard against division by zero: returns 0.0 instead of raising.
        report = make_report(current_value=5.0, baseline_value=0.0)
        assert report.get_deviation_percentage() == 0.0

    def test_large_deviation(self):
        report = make_report(current_value=3.0, baseline_value=1.0)
        assert report.get_deviation_percentage() == pytest.approx(200.0)

    def test_negative_baseline(self):
        # baseline -2.0, current -1.0 -> abs((-1 - -2) / -2) * 100 = 50.0
        report = make_report(current_value=-1.0, baseline_value=-2.0)
        assert report.get_deviation_percentage() == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# requires_action classification
# ---------------------------------------------------------------------------
class TestRequiresAction:
    """Tests for requires_action()."""

    def test_drifted_and_high_requires_action(self):
        report = make_report(is_drifted=True, drift_score=0.6)  # HIGH
        assert report.severity is DriftSeverity.HIGH
        assert report.requires_action() is True

    def test_drifted_and_critical_requires_action(self):
        report = make_report(is_drifted=True, drift_score=0.9)  # CRITICAL
        assert report.severity is DriftSeverity.CRITICAL
        assert report.requires_action() is True

    def test_drifted_but_low_does_not_require_action(self):
        report = make_report(is_drifted=True, drift_score=0.1)  # LOW
        assert report.requires_action() is False

    def test_drifted_but_medium_does_not_require_action(self):
        report = make_report(is_drifted=True, drift_score=0.35)  # MEDIUM
        assert report.requires_action() is False

    def test_high_severity_but_not_drifted_does_not_require_action(self):
        report = make_report(is_drifted=False, drift_score=0.6)  # HIGH
        assert report.severity is DriftSeverity.HIGH
        assert report.requires_action() is False

    def test_critical_severity_but_not_drifted_does_not_require_action(self):
        report = make_report(is_drifted=False, drift_score=0.95)  # CRITICAL
        assert report.requires_action() is False


# ---------------------------------------------------------------------------
# details immutability & update_details
# ---------------------------------------------------------------------------
class TestDetails:
    """Tests for the details property and update_details()."""

    def test_details_property_returns_copy(self):
        report = make_report(details={"a": 1})
        snapshot = report.details
        snapshot["a"] = 999
        snapshot["b"] = 2
        # Mutating the returned copy does not affect internal state.
        assert report.details == {"a": 1}

    def test_update_details_merges(self):
        report = make_report(details={"a": 1})
        report.update_details({"b": 2})
        assert report.details == {"a": 1, "b": 2}

    def test_update_details_overwrites_existing_key(self):
        report = make_report(details={"a": 1})
        report.update_details({"a": 42})
        assert report.details == {"a": 42}

    def test_update_details_touches_updated_at(self):
        report = make_report()
        before = report.updated_at
        report.update_details({"x": 1})
        assert report.updated_at >= before

    def test_update_details_empty_dict_is_noop_on_content(self):
        report = make_report(details={"a": 1})
        report.update_details({})
        assert report.details == {"a": 1}


# ---------------------------------------------------------------------------
# Entity identity semantics (inherited)
# ---------------------------------------------------------------------------
class TestEntityIdentity:
    """Equality and hashing are based on the entity id."""

    def test_equality_by_id(self):
        eid = uuid4()
        a = make_report(id=eid, model_name="a")
        b = make_report(id=eid, model_name="b")
        assert a == b

    def test_inequality_different_id(self):
        a = make_report()
        b = make_report()
        assert a != b

    def test_not_equal_to_non_entity(self):
        report = make_report()
        assert report != "not-an-entity"

    def test_hash_uses_id(self):
        eid = uuid4()
        a = make_report(id=eid)
        b = make_report(id=eid)
        assert hash(a) == hash(b)
        assert len({a, b}) == 1


# ---------------------------------------------------------------------------
# to_dict serialization
# ---------------------------------------------------------------------------
class TestToDict:
    """Tests for to_dict()."""

    def test_includes_base_fields(self):
        report = make_report()
        data = report.to_dict()
        assert data["id"] == str(report.id)
        assert "created_at" in data
        assert "updated_at" in data

    def test_includes_entity_fields(self):
        eid = uuid4()
        start = datetime(2026, 1, 1, tzinfo=UTC)
        end = datetime(2026, 2, 1, tzinfo=UTC)
        report = DriftReport(
            model_name="ranker",
            model_version="2.0.0",
            drift_type=DriftType.PREDICTION_DRIFT,
            metric_name="ks_stat",
            current_value=0.6,
            baseline_value=0.5,
            drift_score=0.85,
            is_drifted=True,
            id=eid,
            threshold=0.7,
            window_start=start,
            window_end=end,
            sample_count=1000,
            details={"k": "v"},
        )
        data = report.to_dict()

        assert data["model_name"] == "ranker"
        assert data["model_version"] == "2.0.0"
        # enums serialized to their string values
        assert data["drift_type"] == "prediction_drift"
        assert data["severity"] == "critical"
        assert data["metric_name"] == "ks_stat"
        assert data["current_value"] == 0.6
        assert data["baseline_value"] == 0.5
        assert data["drift_score"] == 0.85
        assert data["is_drifted"] is True
        assert data["threshold"] == 0.7
        assert data["window_start"] == start.isoformat()
        assert data["window_end"] == end.isoformat()
        assert data["sample_count"] == 1000
        assert data["details"] == {"k": "v"}

    def test_computed_fields(self):
        report = make_report(
            current_value=1.2,
            baseline_value=1.0,
            drift_score=0.9,
            is_drifted=True,
        )
        data = report.to_dict()
        assert data["deviation_percentage"] == pytest.approx(20.0)
        assert data["requires_action"] is True

    def test_none_windows_serialize_to_none(self):
        report = make_report()
        data = report.to_dict()
        assert data["window_start"] is None
        assert data["window_end"] is None
        assert data["threshold"] is None
        assert data["sample_count"] is None

    def test_to_dict_is_json_friendly_types(self):
        report = make_report(details={"x": 1})
        data = report.to_dict()
        # enum fields must be plain strings, not enum members
        assert isinstance(data["drift_type"], str)
        assert isinstance(data["severity"], str)
        assert isinstance(data["details"], dict)
