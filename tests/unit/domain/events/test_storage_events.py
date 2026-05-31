"""Tests for model storage / versioning domain events.

This module tests the storage domain events defined in
``src/domain/events/storage_events.py``:

- ``ModelVersionCreatedEvent``
- ``ModelVersionDeletedEvent``
- ``ModelRolledBackEvent``
- ``ModelVersionActivatedEvent``
- ``ModelVersionArchivedEvent``
- ``ModelStorageFailedEvent``

Unlike the events in ``ml_events.py``, the storage events do NOT declare a
custom ``__init__``. They are plain frozen dataclasses inheriting from
:class:`~src.domain.events.base.DomainEvent`. Because the ``@dataclass``
decorator regenerates ``__init__`` from the declared fields (including the
three inherited base fields ``event_id``, ``occurred_at``, ``aggregate_id``),
these events are constructed by passing those base fields explicitly rather
than via the base ``DomainEvent.__init__(aggregate_id=...)`` helper.

The tests focus on:

- Construction with valid arguments (base fields + event-specific fields)
- Default argument behaviour (optional ``*_by`` / ``reason`` fields)
- Immutability of frozen dataclasses
- ``to_dict()`` serialization (base fields + event-specific fields)
- Edge cases (empty strings, ``None`` values, boundary numeric values)
- Dataclass-derived semantics (equality, hashability)

The events carry no internal validation/invariants, so no validation
behaviour is asserted.
"""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from src.domain.events.base import DomainEvent
from src.domain.events.storage_events import (
    ModelRolledBackEvent,
    ModelStorageFailedEvent,
    ModelVersionActivatedEvent,
    ModelVersionArchivedEvent,
    ModelVersionCreatedEvent,
    ModelVersionDeletedEvent,
)

# Base fields shared by all events (the dataclass-generated __init__ requires
# them to be supplied explicitly for the storage events).
EVENT_ID = uuid4()
AGGREGATE_ID = uuid4()
OCCURRED_AT = datetime(2026, 5, 31, 12, 0, 0, tzinfo=UTC)


def _base_kwargs(
    event_id: UUID | None = None,
    aggregate_id: UUID | None = None,
    occurred_at: datetime | None = None,
) -> dict:
    """Build the inherited base-field kwargs for storage events."""
    return {
        "event_id": event_id or uuid4(),
        "occurred_at": occurred_at or OCCURRED_AT,
        "aggregate_id": aggregate_id or uuid4(),
    }


def _assert_base_fields(
    event: DomainEvent,
    *,
    event_id: UUID,
    aggregate_id: UUID,
    occurred_at: datetime,
) -> None:
    """Assert the inherited DomainEvent base fields are populated as given."""
    assert isinstance(event, DomainEvent)
    assert isinstance(event.event_id, UUID)
    assert isinstance(event.occurred_at, datetime)
    assert event.event_id == event_id
    assert event.aggregate_id == aggregate_id
    assert event.occurred_at == occurred_at


def _assert_base_dict(data: dict, event: DomainEvent) -> None:
    """Assert the base fields serialized by to_dict are correct."""
    assert data["event_type"] == event.__class__.__name__
    assert data["event_id"] == str(event.event_id)
    assert data["aggregate_id"] == str(event.aggregate_id)
    assert data["occurred_at"] == event.occurred_at.isoformat()


class TestModelVersionCreatedEvent:
    """Tests for ModelVersionCreatedEvent."""

    def _make(self, **overrides) -> ModelVersionCreatedEvent:
        kwargs = {
            **_base_kwargs(event_id=EVENT_ID, aggregate_id=AGGREGATE_ID),
            "model_name": "sentiment-classifier",
            "version": "1.0.0",
            "base_model": "bert-base",
            "mlflow_run_id": "run-123",
            "storage_path": "/models/sentiment/1.0.0",
            "accuracy": 0.95,
            "training_examples": 1000,
        }
        kwargs.update(overrides)
        return ModelVersionCreatedEvent(**kwargs)

    def test_construction_valid(self):
        event = self._make()

        assert event.model_name == "sentiment-classifier"
        assert event.version == "1.0.0"
        assert event.base_model == "bert-base"
        assert event.mlflow_run_id == "run-123"
        assert event.storage_path == "/models/sentiment/1.0.0"
        assert event.accuracy == 0.95
        assert event.training_examples == 1000
        _assert_base_fields(
            event,
            event_id=EVENT_ID,
            aggregate_id=AGGREGATE_ID,
            occurred_at=OCCURRED_AT,
        )

    def test_optional_fields_accept_none(self):
        event = self._make(mlflow_run_id=None, accuracy=None)

        assert event.mlflow_run_id is None
        assert event.accuracy is None

    def test_is_frozen(self):
        event = self._make()

        with pytest.raises(FrozenInstanceError):
            event.model_name = "other"

    def test_to_dict(self):
        event = self._make()

        data = event.to_dict()

        _assert_base_dict(data, event)
        assert data["model_name"] == "sentiment-classifier"
        assert data["version"] == "1.0.0"
        assert data["base_model"] == "bert-base"
        assert data["mlflow_run_id"] == "run-123"
        assert data["storage_path"] == "/models/sentiment/1.0.0"
        assert data["accuracy"] == 0.95
        assert data["training_examples"] == 1000

    def test_to_dict_keys(self):
        data = self._make().to_dict()

        assert set(data.keys()) == {
            "event_id",
            "event_type",
            "occurred_at",
            "aggregate_id",
            "model_name",
            "version",
            "base_model",
            "mlflow_run_id",
            "storage_path",
            "accuracy",
            "training_examples",
        }

    def test_to_dict_with_none_optionals(self):
        data = self._make(mlflow_run_id=None, accuracy=None).to_dict()

        assert data["mlflow_run_id"] is None
        assert data["accuracy"] is None

    def test_edge_case_empty_strings_and_zero(self):
        event = self._make(
            model_name="",
            version="",
            base_model="",
            storage_path="",
            accuracy=0.0,
            training_examples=0,
        )

        assert event.model_name == ""
        assert event.version == ""
        assert event.base_model == ""
        assert event.storage_path == ""
        assert event.accuracy == 0.0
        assert event.training_examples == 0


class TestModelVersionDeletedEvent:
    """Tests for ModelVersionDeletedEvent."""

    def _make(self, **overrides) -> ModelVersionDeletedEvent:
        kwargs = {
            **_base_kwargs(event_id=EVENT_ID, aggregate_id=AGGREGATE_ID),
            "model_name": "classifier",
            "version": "2.0.0",
        }
        kwargs.update(overrides)
        return ModelVersionDeletedEvent(**kwargs)

    def test_construction_valid(self):
        event = self._make(deleted_by="admin", reason="obsolete")

        assert event.model_name == "classifier"
        assert event.version == "2.0.0"
        assert event.deleted_by == "admin"
        assert event.reason == "obsolete"
        _assert_base_fields(
            event,
            event_id=EVENT_ID,
            aggregate_id=AGGREGATE_ID,
            occurred_at=OCCURRED_AT,
        )

    def test_optional_fields_default_to_none(self):
        event = self._make()

        assert event.deleted_by is None
        assert event.reason is None

    def test_is_frozen(self):
        event = self._make()

        with pytest.raises(FrozenInstanceError):
            event.reason = "changed"

    def test_to_dict(self):
        event = self._make(deleted_by="ops", reason="cleanup")

        data = event.to_dict()

        _assert_base_dict(data, event)
        assert data["model_name"] == "classifier"
        assert data["version"] == "2.0.0"
        assert data["deleted_by"] == "ops"
        assert data["reason"] == "cleanup"

    def test_to_dict_with_default_none(self):
        data = self._make().to_dict()

        assert data["deleted_by"] is None
        assert data["reason"] is None

    def test_to_dict_keys(self):
        data = self._make().to_dict()

        assert set(data.keys()) == {
            "event_id",
            "event_type",
            "occurred_at",
            "aggregate_id",
            "model_name",
            "version",
            "deleted_by",
            "reason",
        }


class TestModelRolledBackEvent:
    """Tests for ModelRolledBackEvent."""

    def _make(self, **overrides) -> ModelRolledBackEvent:
        kwargs = {
            **_base_kwargs(event_id=EVENT_ID, aggregate_id=AGGREGATE_ID),
            "model_name": "ranker",
            "from_version": "3.0.0",
            "to_version": "2.0.0",
            "reason": "regression in production",
        }
        kwargs.update(overrides)
        return ModelRolledBackEvent(**kwargs)

    def test_construction_valid(self):
        event = self._make(rolled_back_by="sre")

        assert event.model_name == "ranker"
        assert event.from_version == "3.0.0"
        assert event.to_version == "2.0.0"
        assert event.reason == "regression in production"
        assert event.rolled_back_by == "sre"
        _assert_base_fields(
            event,
            event_id=EVENT_ID,
            aggregate_id=AGGREGATE_ID,
            occurred_at=OCCURRED_AT,
        )

    def test_rolled_back_by_defaults_to_none(self):
        event = self._make()

        assert event.rolled_back_by is None

    def test_is_frozen(self):
        event = self._make()

        with pytest.raises(FrozenInstanceError):
            event.to_version = "1.0.0"

    def test_to_dict(self):
        event = self._make(rolled_back_by="oncall")

        data = event.to_dict()

        _assert_base_dict(data, event)
        assert data["model_name"] == "ranker"
        assert data["from_version"] == "3.0.0"
        assert data["to_version"] == "2.0.0"
        assert data["reason"] == "regression in production"
        assert data["rolled_back_by"] == "oncall"

    def test_to_dict_with_default_none(self):
        data = self._make().to_dict()

        assert data["rolled_back_by"] is None

    def test_to_dict_keys(self):
        data = self._make().to_dict()

        assert set(data.keys()) == {
            "event_id",
            "event_type",
            "occurred_at",
            "aggregate_id",
            "model_name",
            "from_version",
            "to_version",
            "reason",
            "rolled_back_by",
        }


class TestModelVersionActivatedEvent:
    """Tests for ModelVersionActivatedEvent."""

    def _make(self, **overrides) -> ModelVersionActivatedEvent:
        kwargs = {
            **_base_kwargs(event_id=EVENT_ID, aggregate_id=AGGREGATE_ID),
            "model_name": "detector",
            "version": "4.1.0",
        }
        kwargs.update(overrides)
        return ModelVersionActivatedEvent(**kwargs)

    def test_construction_valid(self):
        event = self._make(previous_active_version="4.0.0")

        assert event.model_name == "detector"
        assert event.version == "4.1.0"
        assert event.previous_active_version == "4.0.0"
        _assert_base_fields(
            event,
            event_id=EVENT_ID,
            aggregate_id=AGGREGATE_ID,
            occurred_at=OCCURRED_AT,
        )

    def test_previous_active_version_defaults_to_none(self):
        event = self._make()

        assert event.previous_active_version is None

    def test_is_frozen(self):
        event = self._make()

        with pytest.raises(FrozenInstanceError):
            event.version = "5.0.0"

    def test_to_dict(self):
        event = self._make(previous_active_version="4.0.0")

        data = event.to_dict()

        _assert_base_dict(data, event)
        assert data["model_name"] == "detector"
        assert data["version"] == "4.1.0"
        assert data["previous_active_version"] == "4.0.0"

    def test_to_dict_with_default_none(self):
        data = self._make().to_dict()

        assert data["previous_active_version"] is None

    def test_to_dict_keys(self):
        data = self._make().to_dict()

        assert set(data.keys()) == {
            "event_id",
            "event_type",
            "occurred_at",
            "aggregate_id",
            "model_name",
            "version",
            "previous_active_version",
        }


class TestModelVersionArchivedEvent:
    """Tests for ModelVersionArchivedEvent."""

    def _make(self, **overrides) -> ModelVersionArchivedEvent:
        kwargs = {
            **_base_kwargs(event_id=EVENT_ID, aggregate_id=AGGREGATE_ID),
            "model_name": "summarizer",
            "version": "0.9.0",
            "archive_reason": "superseded by 1.0.0",
        }
        kwargs.update(overrides)
        return ModelVersionArchivedEvent(**kwargs)

    def test_construction_valid(self):
        event = self._make(archived_by="curator")

        assert event.model_name == "summarizer"
        assert event.version == "0.9.0"
        assert event.archive_reason == "superseded by 1.0.0"
        assert event.archived_by == "curator"
        _assert_base_fields(
            event,
            event_id=EVENT_ID,
            aggregate_id=AGGREGATE_ID,
            occurred_at=OCCURRED_AT,
        )

    def test_archived_by_defaults_to_none(self):
        event = self._make()

        assert event.archived_by is None

    def test_is_frozen(self):
        event = self._make()

        with pytest.raises(FrozenInstanceError):
            event.archive_reason = "other"

    def test_to_dict(self):
        event = self._make(archived_by="curator")

        data = event.to_dict()

        _assert_base_dict(data, event)
        assert data["model_name"] == "summarizer"
        assert data["version"] == "0.9.0"
        assert data["archive_reason"] == "superseded by 1.0.0"
        assert data["archived_by"] == "curator"

    def test_to_dict_with_default_none(self):
        data = self._make().to_dict()

        assert data["archived_by"] is None

    def test_to_dict_keys(self):
        data = self._make().to_dict()

        assert set(data.keys()) == {
            "event_id",
            "event_type",
            "occurred_at",
            "aggregate_id",
            "model_name",
            "version",
            "archive_reason",
            "archived_by",
        }


class TestModelStorageFailedEvent:
    """Tests for ModelStorageFailedEvent."""

    def _make(self, **overrides) -> ModelStorageFailedEvent:
        kwargs = {
            **_base_kwargs(event_id=EVENT_ID, aggregate_id=AGGREGATE_ID),
            "model_name": "embedder",
            "version": "1.2.3",
            "error_message": "disk full",
            "error_type": "OSError",
        }
        kwargs.update(overrides)
        return ModelStorageFailedEvent(**kwargs)

    def test_construction_valid(self):
        event = self._make()

        assert event.model_name == "embedder"
        assert event.version == "1.2.3"
        assert event.error_message == "disk full"
        assert event.error_type == "OSError"
        _assert_base_fields(
            event,
            event_id=EVENT_ID,
            aggregate_id=AGGREGATE_ID,
            occurred_at=OCCURRED_AT,
        )

    def test_is_frozen(self):
        event = self._make()

        with pytest.raises(FrozenInstanceError):
            event.error_message = "other"

    def test_to_dict(self):
        event = self._make()

        data = event.to_dict()

        _assert_base_dict(data, event)
        assert data["model_name"] == "embedder"
        assert data["version"] == "1.2.3"
        assert data["error_message"] == "disk full"
        assert data["error_type"] == "OSError"

    def test_to_dict_keys(self):
        data = self._make().to_dict()

        assert set(data.keys()) == {
            "event_id",
            "event_type",
            "occurred_at",
            "aggregate_id",
            "model_name",
            "version",
            "error_message",
            "error_type",
        }

    def test_edge_case_empty_error_fields(self):
        event = self._make(error_message="", error_type="")

        assert event.error_message == ""
        assert event.error_type == ""


class TestStorageEventDataclassSemantics:
    """Cross-cutting dataclass behaviour for the storage events."""

    def _failed(self, **overrides) -> ModelStorageFailedEvent:
        kwargs = {
            "event_id": EVENT_ID,
            "occurred_at": OCCURRED_AT,
            "aggregate_id": AGGREGATE_ID,
            "model_name": "m",
            "version": "1",
            "error_message": "boom",
            "error_type": "IOError",
        }
        kwargs.update(overrides)
        return ModelStorageFailedEvent(**kwargs)

    def test_equality_for_identical_fields(self):
        assert self._failed() == self._failed()

    def test_inequality_when_a_field_differs(self):
        assert self._failed() != self._failed(error_message="different")

    def test_inequality_when_base_field_differs(self):
        assert self._failed() != self._failed(event_id=uuid4())

    def test_hashable(self):
        # frozen=True dataclasses are hashable; ensure it does not raise.
        assert isinstance(hash(self._failed()), int)

    def test_distinct_types_are_not_equal(self):
        failed = self._failed()
        deleted = ModelVersionDeletedEvent(
            event_id=EVENT_ID,
            occurred_at=OCCURRED_AT,
            aggregate_id=AGGREGATE_ID,
            model_name="m",
            version="1",
        )
        assert failed != deleted

    def test_all_events_subclass_domain_event(self):
        events = [
            ModelVersionCreatedEvent(
                event_id=EVENT_ID,
                occurred_at=OCCURRED_AT,
                aggregate_id=AGGREGATE_ID,
                model_name="m",
                version="1",
                base_model="b",
                mlflow_run_id=None,
                storage_path="/p",
                accuracy=None,
                training_examples=0,
            ),
            ModelVersionDeletedEvent(
                event_id=EVENT_ID,
                occurred_at=OCCURRED_AT,
                aggregate_id=AGGREGATE_ID,
                model_name="m",
                version="1",
            ),
            ModelRolledBackEvent(
                event_id=EVENT_ID,
                occurred_at=OCCURRED_AT,
                aggregate_id=AGGREGATE_ID,
                model_name="m",
                from_version="2",
                to_version="1",
                reason="r",
            ),
            ModelVersionActivatedEvent(
                event_id=EVENT_ID,
                occurred_at=OCCURRED_AT,
                aggregate_id=AGGREGATE_ID,
                model_name="m",
                version="1",
            ),
            ModelVersionArchivedEvent(
                event_id=EVENT_ID,
                occurred_at=OCCURRED_AT,
                aggregate_id=AGGREGATE_ID,
                model_name="m",
                version="1",
                archive_reason="r",
            ),
            self._failed(),
        ]
        for event in events:
            assert isinstance(event, DomainEvent)
