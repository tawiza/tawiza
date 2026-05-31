"""Unit tests for the model version domain entities (issue #161, batch 3 coverage).

Covers:
- VersionMetadata: construction (required + optional fields), default factories,
  to_dict() serialization, from_dict() parsing, and to_dict/from_dict round-trip.
- ModelVersionSnapshot: construction with defaults, custom construction, and
  to_dict() serialization including the nested metadata dict.

The production code is the source of truth. VersionMetadata is a plain dataclass
with no explicit validation or ordering, so version comparison is exercised
through the AutoIncrementVersion value object it carries (the entity does not
define its own ordering / transition methods, and none are invented here).
"""

from datetime import datetime
from uuid import UUID, uuid4

import pytest

from src.domain.entities.model_version import (
    ModelVersionSnapshot,
    VersionMetadata,
)
from src.domain.value_objects.version import AutoIncrementVersion


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_metadata(**overrides) -> VersionMetadata:
    """Build a VersionMetadata with sensible required defaults."""
    kwargs = {
        "model_name": "tajine-classifier",
        "version": AutoIncrementVersion(1),
        "base_model": "qwen3.5:27b",
    }
    kwargs.update(overrides)
    return VersionMetadata(**kwargs)


# ---------------------------------------------------------------------------
# VersionMetadata — construction
# ---------------------------------------------------------------------------
class TestVersionMetadataConstruction:
    """Construction of VersionMetadata: required + optional fields and defaults."""

    def test_minimal_construction_sets_required_fields(self):
        meta = _make_metadata()
        assert meta.model_name == "tajine-classifier"
        assert meta.version == AutoIncrementVersion(1)
        assert meta.base_model == "qwen3.5:27b"

    def test_version_is_auto_increment_version_instance(self):
        meta = _make_metadata()
        assert isinstance(meta.version, AutoIncrementVersion)
        assert int(meta.version) == 1

    def test_mlflow_defaults_are_none(self):
        meta = _make_metadata()
        assert meta.mlflow_run_id is None
        assert meta.mlflow_experiment_id is None

    def test_metric_defaults_are_none(self):
        meta = _make_metadata()
        assert meta.accuracy is None
        assert meta.precision is None
        assert meta.recall is None
        assert meta.f1_score is None
        assert meta.loss is None
        assert meta.perplexity is None

    def test_training_defaults(self):
        meta = _make_metadata()
        assert meta.training_examples == 0
        assert meta.task_type == "classification"
        assert meta.hyperparameters == {}

    def test_storage_defaults(self):
        meta = _make_metadata()
        assert meta.storage_path is None
        assert meta.modelfile_size_bytes == 0
        assert meta.checksum is None

    def test_created_at_is_datetime_by_default(self):
        meta = _make_metadata()
        assert isinstance(meta.created_at, datetime)

    def test_trained_at_default_is_none(self):
        meta = _make_metadata()
        assert meta.trained_at is None

    def test_tags_default_is_empty_dict(self):
        meta = _make_metadata()
        assert meta.tags == {}

    def test_flag_defaults(self):
        meta = _make_metadata()
        assert meta.is_active is True
        assert meta.is_baseline is False

    def test_note_defaults_are_none(self):
        meta = _make_metadata()
        assert meta.description is None
        assert meta.training_notes is None

    def test_hyperparameters_default_factory_is_independent(self):
        """Each instance must get its own dict (mutable default factory)."""
        m1 = _make_metadata()
        m2 = _make_metadata()
        m1.hyperparameters["lr"] = 0.001
        assert m2.hyperparameters == {}

    def test_tags_default_factory_is_independent(self):
        m1 = _make_metadata()
        m2 = _make_metadata()
        m1.tags["env"] = "prod"
        assert m2.tags == {}

    def test_fully_populated_construction(self):
        created = datetime(2026, 1, 1, 12, 0, 0)
        trained = datetime(2026, 1, 2, 9, 30, 0)
        meta = VersionMetadata(
            model_name="full",
            version=AutoIncrementVersion(3),
            base_model="base",
            mlflow_run_id="run-1",
            mlflow_experiment_id="exp-1",
            accuracy=0.95,
            precision=0.9,
            recall=0.85,
            f1_score=0.875,
            loss=0.12,
            perplexity=3.4,
            training_examples=1000,
            task_type="ner",
            hyperparameters={"lr": 0.01},
            storage_path="s3://bucket/path",
            modelfile_size_bytes=2048,
            checksum="deadbeef",
            created_at=created,
            trained_at=trained,
            tags={"team": "tawiza"},
            is_active=False,
            is_baseline=True,
            description="desc",
            training_notes="notes",
        )
        assert meta.accuracy == 0.95
        assert meta.task_type == "ner"
        assert meta.hyperparameters == {"lr": 0.01}
        assert meta.created_at == created
        assert meta.trained_at == trained
        assert meta.is_active is False
        assert meta.is_baseline is True


# ---------------------------------------------------------------------------
# VersionMetadata — version handling / ordering via the carried value object
# ---------------------------------------------------------------------------
class TestVersionMetadataVersioning:
    """Ordering and version semantics flow through AutoIncrementVersion."""

    def test_versions_compare_via_value_object(self):
        v1 = _make_metadata(version=AutoIncrementVersion(1))
        v2 = _make_metadata(version=AutoIncrementVersion(2))
        assert v1.version < v2.version
        assert v2.version > v1.version

    def test_next_version_metadata(self):
        meta = _make_metadata(version=AutoIncrementVersion(1))
        bumped = _make_metadata(version=meta.version.next())
        assert int(bumped.version) == 2

    def test_str_of_version_uses_v_prefix(self):
        meta = _make_metadata(version=AutoIncrementVersion(7))
        assert str(meta.version) == "v7"


# ---------------------------------------------------------------------------
# VersionMetadata — to_dict
# ---------------------------------------------------------------------------
class TestVersionMetadataToDict:
    """Serialization of VersionMetadata via to_dict()."""

    def test_to_dict_returns_dict(self):
        assert isinstance(_make_metadata().to_dict(), dict)

    def test_to_dict_version_is_string_with_prefix(self):
        d = _make_metadata(version=AutoIncrementVersion(5)).to_dict()
        assert d["version"] == "v5"
        assert isinstance(d["version"], str)

    def test_to_dict_created_at_is_isoformat(self):
        created = datetime(2026, 5, 31, 10, 0, 0)
        d = _make_metadata(created_at=created).to_dict()
        assert d["created_at"] == created.isoformat()

    def test_to_dict_trained_at_none_when_missing(self):
        d = _make_metadata().to_dict()
        assert d["trained_at"] is None

    def test_to_dict_trained_at_isoformat_when_present(self):
        trained = datetime(2026, 5, 30, 8, 0, 0)
        d = _make_metadata(trained_at=trained).to_dict()
        assert d["trained_at"] == trained.isoformat()

    def test_to_dict_contains_all_expected_keys(self):
        d = _make_metadata().to_dict()
        expected = {
            "model_name",
            "version",
            "base_model",
            "mlflow_run_id",
            "mlflow_experiment_id",
            "accuracy",
            "precision",
            "recall",
            "f1_score",
            "loss",
            "perplexity",
            "training_examples",
            "task_type",
            "hyperparameters",
            "storage_path",
            "modelfile_size_bytes",
            "checksum",
            "created_at",
            "trained_at",
            "tags",
            "is_active",
            "is_baseline",
            "description",
            "training_notes",
        }
        assert set(d.keys()) == expected

    def test_to_dict_passes_through_scalar_values(self):
        d = _make_metadata(
            accuracy=0.5,
            training_examples=42,
            is_baseline=True,
            tags={"k": "v"},
        ).to_dict()
        assert d["accuracy"] == 0.5
        assert d["training_examples"] == 42
        assert d["is_baseline"] is True
        assert d["tags"] == {"k": "v"}


# ---------------------------------------------------------------------------
# VersionMetadata — from_dict
# ---------------------------------------------------------------------------
class TestVersionMetadataFromDict:
    """Deserialization of VersionMetadata via from_dict()."""

    def _payload(self, **overrides) -> dict:
        base = {
            "model_name": "m",
            "version": "v2",
            "base_model": "b",
        }
        base.update(overrides)
        return base

    def test_from_dict_minimal(self):
        meta = VersionMetadata.from_dict(self._payload())
        assert meta.model_name == "m"
        assert meta.base_model == "b"
        assert meta.version == AutoIncrementVersion(2)

    def test_from_dict_version_string_without_prefix(self):
        meta = VersionMetadata.from_dict(self._payload(version="3"))
        assert meta.version == AutoIncrementVersion(3)

    def test_from_dict_applies_defaults_for_missing_optionals(self):
        meta = VersionMetadata.from_dict(self._payload())
        assert meta.training_examples == 0
        assert meta.task_type == "classification"
        assert meta.hyperparameters == {}
        assert meta.tags == {}
        assert meta.is_active is True
        assert meta.is_baseline is False
        assert meta.accuracy is None

    def test_from_dict_parses_created_at_string(self):
        created = datetime(2026, 5, 31, 14, 30, 0)
        meta = VersionMetadata.from_dict(self._payload(created_at=created.isoformat()))
        assert meta.created_at == created

    def test_from_dict_accepts_datetime_created_at(self):
        created = datetime(2026, 5, 31, 14, 30, 0)
        meta = VersionMetadata.from_dict(self._payload(created_at=created))
        assert meta.created_at == created

    def test_from_dict_created_at_missing_defaults_to_datetime(self):
        meta = VersionMetadata.from_dict(self._payload())
        assert isinstance(meta.created_at, datetime)

    def test_from_dict_parses_trained_at_string(self):
        trained = datetime(2026, 5, 30, 8, 0, 0)
        meta = VersionMetadata.from_dict(self._payload(trained_at=trained.isoformat()))
        assert meta.trained_at == trained

    def test_from_dict_accepts_datetime_trained_at(self):
        trained = datetime(2026, 5, 30, 8, 0, 0)
        meta = VersionMetadata.from_dict(self._payload(trained_at=trained))
        assert meta.trained_at == trained

    def test_from_dict_trained_at_missing_is_none(self):
        meta = VersionMetadata.from_dict(self._payload())
        assert meta.trained_at is None

    def test_from_dict_falsy_trained_at_is_none(self):
        # Empty string / None are falsy -> trained_at stays None.
        assert VersionMetadata.from_dict(self._payload(trained_at="")).trained_at is None
        assert VersionMetadata.from_dict(self._payload(trained_at=None)).trained_at is None

    def test_from_dict_populates_metrics_and_storage(self):
        meta = VersionMetadata.from_dict(
            self._payload(
                accuracy=0.9,
                precision=0.8,
                recall=0.7,
                f1_score=0.75,
                loss=0.2,
                perplexity=2.1,
                storage_path="minio://x",
                modelfile_size_bytes=99,
                checksum="abc",
                training_examples=10,
                task_type="regression",
                hyperparameters={"a": 1},
                tags={"t": "1"},
                is_active=False,
                is_baseline=True,
                description="d",
                training_notes="n",
                mlflow_run_id="r",
                mlflow_experiment_id="e",
            )
        )
        assert meta.accuracy == 0.9
        assert meta.storage_path == "minio://x"
        assert meta.modelfile_size_bytes == 99
        assert meta.checksum == "abc"
        assert meta.task_type == "regression"
        assert meta.hyperparameters == {"a": 1}
        assert meta.is_active is False
        assert meta.is_baseline is True
        assert meta.mlflow_run_id == "r"

    def test_from_dict_missing_required_key_raises(self):
        with pytest.raises(KeyError):
            VersionMetadata.from_dict({"model_name": "m", "base_model": "b"})

    def test_from_dict_invalid_version_raises(self):
        with pytest.raises(ValueError):
            VersionMetadata.from_dict(self._payload(version="not-a-number"))


# ---------------------------------------------------------------------------
# VersionMetadata — round-trip
# ---------------------------------------------------------------------------
class TestVersionMetadataRoundTrip:
    """to_dict() -> from_dict() must preserve the entity's content."""

    def test_round_trip_minimal(self):
        original = _make_metadata(created_at=datetime(2026, 1, 1, 0, 0, 0))
        restored = VersionMetadata.from_dict(original.to_dict())
        assert restored.model_name == original.model_name
        assert restored.base_model == original.base_model
        assert restored.version == original.version
        assert restored.created_at == original.created_at
        assert restored.trained_at is None

    def test_round_trip_full(self):
        original = VersionMetadata(
            model_name="rt",
            version=AutoIncrementVersion(4),
            base_model="base",
            mlflow_run_id="run",
            mlflow_experiment_id="exp",
            accuracy=0.99,
            precision=0.98,
            recall=0.97,
            f1_score=0.975,
            loss=0.01,
            perplexity=1.5,
            training_examples=500,
            task_type="ner",
            hyperparameters={"lr": 0.001, "epochs": 3},
            storage_path="minio://models/rt",
            modelfile_size_bytes=4096,
            checksum="cafe",
            created_at=datetime(2026, 2, 2, 2, 2, 2),
            trained_at=datetime(2026, 2, 3, 3, 3, 3),
            tags={"team": "ml", "stage": "prod"},
            is_active=False,
            is_baseline=True,
            description="round trip",
            training_notes="all fields",
        )
        restored = VersionMetadata.from_dict(original.to_dict())
        assert restored == original


# ---------------------------------------------------------------------------
# ModelVersionSnapshot — construction
# ---------------------------------------------------------------------------
class TestModelVersionSnapshotConstruction:
    """Construction of ModelVersionSnapshot with defaults and overrides."""

    def test_default_construction(self):
        snap = ModelVersionSnapshot()
        assert isinstance(snap.id, UUID)
        assert snap.model_name == ""
        assert snap.version == AutoIncrementVersion(1)
        assert isinstance(snap.metadata, VersionMetadata)
        assert snap.modelfile_content == ""
        assert isinstance(snap.snapshot_created_at, datetime)
        assert snap.snapshot_reason == "backup"

    def test_default_metadata_is_placeholder(self):
        snap = ModelVersionSnapshot()
        assert snap.metadata.model_name == ""
        assert snap.metadata.base_model == ""
        assert snap.metadata.version == AutoIncrementVersion(1)

    def test_each_default_snapshot_gets_unique_id(self):
        assert ModelVersionSnapshot().id != ModelVersionSnapshot().id

    def test_default_factories_are_independent(self):
        """Mutable default metadata must not be shared across instances."""
        s1 = ModelVersionSnapshot()
        s2 = ModelVersionSnapshot()
        s1.metadata.tags["k"] = "v"
        assert s2.metadata.tags == {}

    def test_custom_construction(self):
        fixed_id = uuid4()
        meta = _make_metadata(version=AutoIncrementVersion(2))
        created = datetime(2026, 3, 3, 3, 3, 3)
        snap = ModelVersionSnapshot(
            id=fixed_id,
            model_name="custom",
            version=AutoIncrementVersion(2),
            metadata=meta,
            modelfile_content="FROM base\n",
            snapshot_created_at=created,
            snapshot_reason="pre-rollback",
        )
        assert snap.id == fixed_id
        assert snap.model_name == "custom"
        assert snap.version == AutoIncrementVersion(2)
        assert snap.metadata is meta
        assert snap.modelfile_content == "FROM base\n"
        assert snap.snapshot_created_at == created
        assert snap.snapshot_reason == "pre-rollback"


# ---------------------------------------------------------------------------
# ModelVersionSnapshot — to_dict
# ---------------------------------------------------------------------------
class TestModelVersionSnapshotToDict:
    """Serialization of ModelVersionSnapshot via to_dict()."""

    def test_to_dict_returns_dict_with_expected_keys(self):
        d = ModelVersionSnapshot().to_dict()
        assert set(d.keys()) == {
            "id",
            "model_name",
            "version",
            "metadata",
            "modelfile_content",
            "snapshot_created_at",
            "snapshot_reason",
        }

    def test_to_dict_id_is_string(self):
        snap = ModelVersionSnapshot()
        d = snap.to_dict()
        assert d["id"] == str(snap.id)
        assert isinstance(d["id"], str)

    def test_to_dict_version_is_string_with_prefix(self):
        d = ModelVersionSnapshot(version=AutoIncrementVersion(9)).to_dict()
        assert d["version"] == "v9"

    def test_to_dict_metadata_is_nested_dict(self):
        meta = _make_metadata(version=AutoIncrementVersion(3))
        d = ModelVersionSnapshot(metadata=meta).to_dict()
        assert isinstance(d["metadata"], dict)
        assert d["metadata"] == meta.to_dict()
        assert d["metadata"]["version"] == "v3"

    def test_to_dict_snapshot_created_at_is_isoformat(self):
        created = datetime(2026, 4, 4, 4, 4, 4)
        d = ModelVersionSnapshot(snapshot_created_at=created).to_dict()
        assert d["snapshot_created_at"] == created.isoformat()

    def test_to_dict_passes_through_scalar_fields(self):
        snap = ModelVersionSnapshot(
            model_name="abc",
            modelfile_content="content",
            snapshot_reason="manual",
        )
        d = snap.to_dict()
        assert d["model_name"] == "abc"
        assert d["modelfile_content"] == "content"
        assert d["snapshot_reason"] == "manual"
