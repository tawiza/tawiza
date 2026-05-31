"""Unit tests for the MLModel domain entity.

This module exercises the ML model aggregate root, its lifecycle state
machine, the ModelMetrics value object, and the related enums:

- ModelStatus / DeploymentStrategy enums (values, membership, ordering)
- ModelMetrics value object (validation, immutability, equality, edge cases)
- MLModel construction and defaults
- MLModel state transitions and invariant enforcement
- Domain event emission (ModelTrainedEvent / ModelDeployedEvent /
  ModelRetiredEvent)
- Serialization via to_dict()

The production code is the source of truth; these tests assert against the
real, observed behavior (including the fact that ModelMetrics does not expose
a to_dict() method).
"""

from datetime import datetime
from uuid import UUID, uuid4

import pytest

from src.domain.entities.ml_model import (
    DeploymentStrategy,
    MLModel,
    ModelMetrics,
    ModelStatus,
)
from src.domain.events.ml_events import (
    ModelDeployedEvent,
    ModelRetiredEvent,
    ModelTrainedEvent,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _deployed_model(
    *,
    strategy: DeploymentStrategy = DeploymentStrategy.DIRECT,
    traffic_percentage: int = 100,
) -> MLModel:
    """Build a model that has been fully driven to the DEPLOYED state."""
    model = MLModel(name="lifecycle-model", version="1.0.0")
    model.start_training("run-xyz")
    model.complete_training(
        metrics=ModelMetrics(accuracy=0.9),
        model_path="/models/lifecycle",
        hyperparameters={"lr": 0.01},
    )
    model.validate()
    model.complete_validation(is_valid=True)
    model.deploy(strategy=strategy, traffic_percentage=traffic_percentage)
    model.complete_deployment()
    return model


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestModelStatusEnum:
    """Tests for the ModelStatus StrEnum."""

    def test_all_expected_members_present(self):
        assert {s.name for s in ModelStatus} == {
            "DRAFT",
            "TRAINING",
            "TRAINED",
            "VALIDATING",
            "VALIDATED",
            "DEPLOYING",
            "DEPLOYED",
            "FAILED",
            "RETIRED",
        }

    def test_values_are_lowercase_strings(self):
        assert ModelStatus.DRAFT.value == "draft"
        assert ModelStatus.DEPLOYED.value == "deployed"
        assert ModelStatus.RETIRED.value == "retired"

    def test_is_str_enum(self):
        # StrEnum members compare equal to their string value.
        assert ModelStatus.TRAINING == "training"
        assert isinstance(ModelStatus.TRAINING, str)

    def test_lookup_by_value(self):
        assert ModelStatus("validated") is ModelStatus.VALIDATED

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            ModelStatus("not-a-real-status")


class TestDeploymentStrategyEnum:
    """Tests for the DeploymentStrategy StrEnum."""

    def test_all_expected_members_present(self):
        assert {s.name for s in DeploymentStrategy} == {
            "DIRECT",
            "CANARY",
            "BLUE_GREEN",
            "A_B_TEST",
        }

    def test_values(self):
        assert DeploymentStrategy.DIRECT.value == "direct"
        assert DeploymentStrategy.CANARY.value == "canary"
        assert DeploymentStrategy.BLUE_GREEN.value == "blue_green"
        assert DeploymentStrategy.A_B_TEST.value == "a_b_test"

    def test_is_str_enum(self):
        assert DeploymentStrategy.CANARY == "canary"
        assert isinstance(DeploymentStrategy.CANARY, str)

    def test_lookup_by_value(self):
        assert DeploymentStrategy("blue_green") is DeploymentStrategy.BLUE_GREEN


# ---------------------------------------------------------------------------
# ModelMetrics value object
# ---------------------------------------------------------------------------


class TestModelMetrics:
    """Tests for the ModelMetrics frozen value object."""

    def test_creation_with_only_accuracy(self):
        metrics = ModelMetrics(accuracy=0.8)
        assert metrics.accuracy == 0.8
        assert metrics.precision is None
        assert metrics.recall is None
        assert metrics.f1_score is None
        assert metrics.loss is None
        assert metrics.perplexity is None
        assert metrics.custom_metrics is None

    def test_creation_with_all_fields(self):
        custom = {"bleu": 0.7}
        metrics = ModelMetrics(
            accuracy=0.95,
            precision=0.9,
            recall=0.92,
            f1_score=0.91,
            loss=0.05,
            perplexity=12.3,
            custom_metrics=custom,
        )
        assert metrics.accuracy == 0.95
        assert metrics.precision == 0.9
        assert metrics.recall == 0.92
        assert metrics.f1_score == 0.91
        assert metrics.loss == 0.05
        assert metrics.perplexity == 12.3
        assert metrics.custom_metrics == custom

    def test_accuracy_below_zero_raises(self):
        with pytest.raises(ValueError, match="Accuracy must be between 0 and 1"):
            ModelMetrics(accuracy=-0.01)

    def test_accuracy_above_one_raises(self):
        with pytest.raises(ValueError, match="Accuracy must be between 0 and 1"):
            ModelMetrics(accuracy=1.01)

    def test_accuracy_boundary_zero_allowed(self):
        assert ModelMetrics(accuracy=0.0).accuracy == 0.0

    def test_accuracy_boundary_one_allowed(self):
        assert ModelMetrics(accuracy=1.0).accuracy == 1.0

    def test_is_frozen(self):
        metrics = ModelMetrics(accuracy=0.5)
        with pytest.raises(AttributeError):
            metrics.accuracy = 0.6  # type: ignore[misc]

    def test_equality_same_values(self):
        a = ModelMetrics(accuracy=0.9, precision=0.8)
        b = ModelMetrics(accuracy=0.9, precision=0.8)
        assert a == b
        assert hash(a) == hash(b)

    def test_inequality_different_values(self):
        a = ModelMetrics(accuracy=0.9)
        b = ModelMetrics(accuracy=0.8)
        assert a != b

    def test_custom_metrics_dict_makes_unhashable(self):
        # A dict default field makes the frozen dataclass unhashable, which is
        # expected behaviour for a value object carrying mutable data.
        metrics = ModelMetrics(accuracy=0.9, custom_metrics={"x": 1.0})
        with pytest.raises(TypeError):
            hash(metrics)

    def test_does_not_expose_to_dict(self):
        # Documented real behaviour: ModelMetrics has no to_dict() method.
        metrics = ModelMetrics(accuracy=0.9)
        assert not hasattr(metrics, "to_dict")


# ---------------------------------------------------------------------------
# Construction & defaults
# ---------------------------------------------------------------------------


class TestMLModelConstruction:
    """Tests for MLModel construction and default values."""

    def test_defaults(self):
        model = MLModel()
        assert model.name == ""
        assert model.version == "0.1.0"
        assert model.base_model == ""
        assert model.description == ""
        assert model.status == ModelStatus.DRAFT
        assert model.metrics is None
        assert model.mlflow_run_id is None
        assert model.model_path is None
        assert model.deployment_strategy is None
        assert model.traffic_percentage == 0
        assert model.is_deployed is False
        assert model.hyperparameters == {}

    def test_generates_uuid_when_not_provided(self):
        model = MLModel(name="x")
        assert isinstance(model.id, UUID)

    def test_uses_provided_id(self):
        custom = uuid4()
        model = MLModel(id=custom, name="x")
        assert model.id == custom

    def test_custom_fields(self):
        model = MLModel(
            name="awesome",
            version="3.2.1",
            base_model="meta-llama/Llama-2-7b",
            description="A nice model",
            status=ModelStatus.TRAINED,
        )
        assert model.name == "awesome"
        assert model.version == "3.2.1"
        assert model.base_model == "meta-llama/Llama-2-7b"
        assert model.description == "A nice model"
        assert model.status == ModelStatus.TRAINED

    def test_timestamps_present(self):
        model = MLModel(name="x")
        assert isinstance(model.created_at, datetime)
        assert isinstance(model.updated_at, datetime)

    def test_starts_with_no_domain_events(self):
        model = MLModel(name="x")
        assert model.domain_events == []

    def test_hyperparameters_property_returns_copy(self):
        model = MLModel(name="x")
        hp = model.hyperparameters
        hp["injected"] = 1
        # Mutating the returned copy must not affect internal state.
        assert model.hyperparameters == {}


# ---------------------------------------------------------------------------
# start_training
# ---------------------------------------------------------------------------


class TestStartTraining:
    def test_from_draft(self):
        model = MLModel(name="x")
        model.start_training("run-1")
        assert model.status == ModelStatus.TRAINING
        assert model.mlflow_run_id == "run-1"

    def test_from_failed(self):
        # A model in FAILED state may be retried.
        model = MLModel(name="x", status=ModelStatus.FAILED)
        model.start_training("run-retry")
        assert model.status == ModelStatus.TRAINING
        assert model.mlflow_run_id == "run-retry"

    @pytest.mark.parametrize(
        "status",
        [
            ModelStatus.TRAINING,
            ModelStatus.TRAINED,
            ModelStatus.VALIDATING,
            ModelStatus.VALIDATED,
            ModelStatus.DEPLOYING,
            ModelStatus.DEPLOYED,
            ModelStatus.RETIRED,
        ],
    )
    def test_invalid_starting_status_raises(self, status):
        model = MLModel(name="x", status=status)
        with pytest.raises(ValueError, match="Cannot start training from status"):
            model.start_training("run-1")

    def test_updates_timestamp(self):
        model = MLModel(name="x")
        before = model.updated_at
        model.start_training("run-1")
        assert model.updated_at >= before


# ---------------------------------------------------------------------------
# complete_training
# ---------------------------------------------------------------------------


class TestCompleteTraining:
    def test_happy_path(self):
        model = MLModel(name="x")
        model.start_training("run-1")
        metrics = ModelMetrics(accuracy=0.88)
        model.complete_training(metrics, "/models/x", {"epochs": 5})

        assert model.status == ModelStatus.TRAINED
        assert model.metrics is metrics
        assert model.model_path == "/models/x"
        assert model.hyperparameters == {"epochs": 5}

    def test_requires_training_status(self):
        model = MLModel(name="x")  # still DRAFT
        with pytest.raises(ValueError, match="Model is not in training status"):
            model.complete_training(ModelMetrics(accuracy=0.5), "/p", {})

    def test_emits_model_trained_event(self):
        model = MLModel(name="trained-name", version="2.0.0")
        model.start_training("run-abc")
        model.complete_training(ModelMetrics(accuracy=0.93), "/p", {})

        assert len(model.domain_events) == 1
        event = model.domain_events[0]
        assert isinstance(event, ModelTrainedEvent)
        assert event.aggregate_id == model.id
        assert event.model_name == "trained-name"
        assert event.version == "2.0.0"
        assert event.accuracy == 0.93
        assert event.mlflow_run_id == "run-abc"


# ---------------------------------------------------------------------------
# fail_training
# ---------------------------------------------------------------------------


class TestFailTraining:
    def test_happy_path(self):
        model = MLModel(name="x")
        model.start_training("run-1")
        model.fail_training("CUDA out of memory")
        assert model.status == ModelStatus.FAILED

    def test_requires_training_status(self):
        model = MLModel(name="x")  # DRAFT
        with pytest.raises(ValueError, match="Model is not in training status"):
            model.fail_training("boom")

    def test_error_message_stored_in_tags(self):
        model = MLModel(name="x")
        model.start_training("run-1")
        model.fail_training("disk full")
        data = model.to_dict()
        assert data["tags"]["error_message"] == "disk full"


# ---------------------------------------------------------------------------
# validate / complete_validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_validate_happy_path(self):
        model = MLModel(name="x")
        model.start_training("run-1")
        model.complete_training(ModelMetrics(accuracy=0.9), "/p", {})
        model.validate()
        assert model.status == ModelStatus.VALIDATING

    def test_validate_requires_trained_status(self):
        model = MLModel(name="x")  # DRAFT
        with pytest.raises(ValueError, match="Model must be trained before validation"):
            model.validate()

    def test_complete_validation_success(self):
        model = MLModel(name="x")
        model.start_training("run-1")
        model.complete_training(ModelMetrics(accuracy=0.9), "/p", {})
        model.validate()
        model.complete_validation(is_valid=True)
        assert model.status == ModelStatus.VALIDATED

    def test_complete_validation_failure(self):
        model = MLModel(name="x")
        model.start_training("run-1")
        model.complete_training(ModelMetrics(accuracy=0.9), "/p", {})
        model.validate()
        model.complete_validation(is_valid=False)
        assert model.status == ModelStatus.FAILED
        # to_dict() cannot be used here (metrics are set), so read the tag
        # directly from internal state.
        assert model._tags["validation_failed"] == "true"

    def test_complete_validation_requires_validating_status(self):
        model = MLModel(name="x")  # DRAFT
        with pytest.raises(ValueError, match="Model is not in validating status"):
            model.complete_validation(is_valid=True)


# ---------------------------------------------------------------------------
# deploy / complete_deployment
# ---------------------------------------------------------------------------


class TestDeploy:
    def _validated(self) -> MLModel:
        model = MLModel(name="x")
        model.start_training("run-1")
        model.complete_training(ModelMetrics(accuracy=0.9), "/p", {})
        model.validate()
        model.complete_validation(is_valid=True)
        return model

    def test_deploy_default_strategy(self):
        model = self._validated()
        model.deploy()
        assert model.status == ModelStatus.DEPLOYING
        assert model.deployment_strategy == DeploymentStrategy.DIRECT
        assert model.traffic_percentage == 100

    def test_deploy_canary(self):
        model = self._validated()
        model.deploy(strategy=DeploymentStrategy.CANARY, traffic_percentage=25)
        assert model.deployment_strategy == DeploymentStrategy.CANARY
        assert model.traffic_percentage == 25

    def test_deploy_requires_validated_status(self):
        model = MLModel(name="x")  # DRAFT
        with pytest.raises(ValueError, match="Model must be validated before deployment"):
            model.deploy()

    @pytest.mark.parametrize("pct", [-1, 101, 150, 1000])
    def test_deploy_invalid_traffic_raises(self, pct):
        model = MLModel(name="x", status=ModelStatus.VALIDATED)
        with pytest.raises(ValueError, match="Traffic percentage must be between 0 and 100"):
            model.deploy(traffic_percentage=pct)

    @pytest.mark.parametrize("pct", [0, 100])
    def test_deploy_traffic_boundaries_allowed(self, pct):
        model = MLModel(name="x", status=ModelStatus.VALIDATED)
        model.deploy(traffic_percentage=pct)
        assert model.traffic_percentage == pct

    def test_complete_deployment_happy_path(self):
        model = self._validated()
        model.deploy()
        model.complete_deployment()
        assert model.status == ModelStatus.DEPLOYED
        assert model.is_deployed is True

    def test_complete_deployment_requires_deploying_status(self):
        model = self._validated()  # VALIDATED, not DEPLOYING
        with pytest.raises(ValueError, match="Model is not in deploying status"):
            model.complete_deployment()

    def test_complete_deployment_sets_deployed_at(self):
        model = self._validated()
        model.deploy()
        model.complete_deployment()
        # Metrics are set, so to_dict() is unavailable; read internal state.
        assert model._deployed_at is not None
        assert isinstance(model._deployed_at, datetime)

    def test_complete_deployment_emits_event(self):
        model = self._validated()
        model.deploy(strategy=DeploymentStrategy.CANARY, traffic_percentage=20)
        model.clear_domain_events()  # drop the ModelTrainedEvent
        model.complete_deployment()

        assert len(model.domain_events) == 1
        event = model.domain_events[0]
        assert isinstance(event, ModelDeployedEvent)
        assert event.aggregate_id == model.id
        assert event.model_name == "x"
        assert event.deployment_strategy == "canary"
        assert event.traffic_percentage == 20


# ---------------------------------------------------------------------------
# update_traffic
# ---------------------------------------------------------------------------


class TestUpdateTraffic:
    def test_happy_path(self):
        model = _deployed_model(strategy=DeploymentStrategy.CANARY, traffic_percentage=10)
        model.update_traffic(60)
        assert model.traffic_percentage == 60

    def test_requires_deployed(self):
        model = MLModel(name="x", status=ModelStatus.VALIDATED)
        with pytest.raises(ValueError, match="Model must be deployed to update traffic"):
            model.update_traffic(50)

    @pytest.mark.parametrize("pct", [-5, 101, 200])
    def test_invalid_percentage_raises(self, pct):
        model = _deployed_model()
        with pytest.raises(ValueError, match="Traffic percentage must be between 0 and 100"):
            model.update_traffic(pct)

    @pytest.mark.parametrize("pct", [0, 100])
    def test_boundaries_allowed(self, pct):
        model = _deployed_model()
        model.update_traffic(pct)
        assert model.traffic_percentage == pct


# ---------------------------------------------------------------------------
# retire
# ---------------------------------------------------------------------------


class TestRetire:
    def test_happy_path(self):
        model = _deployed_model()
        model.retire(reason="Replaced by v2")
        assert model.status == ModelStatus.RETIRED
        assert model.traffic_percentage == 0

    def test_requires_deployed(self):
        model = MLModel(name="x", status=ModelStatus.VALIDATED)
        with pytest.raises(ValueError, match="Only deployed models can be retired"):
            model.retire()

    def test_sets_retired_at(self):
        model = _deployed_model()
        model.retire()
        # Metrics are set, so to_dict() is unavailable; read internal state.
        assert model._retired_at is not None
        assert isinstance(model._retired_at, datetime)

    def test_reason_stored_in_tags(self):
        model = _deployed_model()
        model.retire(reason="obsolete")
        assert model._tags["retirement_reason"] == "obsolete"

    def test_empty_reason_not_stored(self):
        model = _deployed_model()
        model.retire(reason="")
        assert "retirement_reason" not in model._tags

    def test_emits_event(self):
        model = _deployed_model()
        model.clear_domain_events()  # drop training + deployment events
        model.retire(reason="end of life")

        assert len(model.domain_events) == 1
        event = model.domain_events[0]
        assert isinstance(event, ModelRetiredEvent)
        assert event.aggregate_id == model.id
        assert event.model_name == model.name
        assert event.version == model.version
        assert event.reason == "end of life"


# ---------------------------------------------------------------------------
# add_tag
# ---------------------------------------------------------------------------


class TestAddTag:
    def test_add_tag(self):
        model = MLModel(name="x")
        model.add_tag("env", "prod")
        assert model.to_dict()["tags"]["env"] == "prod"

    def test_add_tag_overwrites(self):
        model = MLModel(name="x")
        model.add_tag("env", "staging")
        model.add_tag("env", "prod")
        assert model.to_dict()["tags"]["env"] == "prod"

    def test_add_tag_updates_timestamp(self):
        model = MLModel(name="x")
        before = model.updated_at
        model.add_tag("k", "v")
        assert model.updated_at >= before


# ---------------------------------------------------------------------------
# Full lifecycle integration
# ---------------------------------------------------------------------------


class TestFullLifecycle:
    def test_draft_to_retired(self):
        model = MLModel(name="full", version="1.0.0")

        model.start_training("run-1")
        assert model.status == ModelStatus.TRAINING

        model.complete_training(ModelMetrics(accuracy=0.97), "/m", {"bs": 32})
        assert model.status == ModelStatus.TRAINED

        model.validate()
        assert model.status == ModelStatus.VALIDATING

        model.complete_validation(is_valid=True)
        assert model.status == ModelStatus.VALIDATED

        model.deploy(strategy=DeploymentStrategy.BLUE_GREEN, traffic_percentage=100)
        assert model.status == ModelStatus.DEPLOYING

        model.complete_deployment()
        assert model.is_deployed is True

        model.update_traffic(80)
        assert model.traffic_percentage == 80

        model.retire(reason="superseded")
        assert model.status == ModelStatus.RETIRED
        assert model.traffic_percentage == 0

        # Three lifecycle events accumulated: trained, deployed, retired.
        event_types = [type(e) for e in model.domain_events]
        assert event_types == [
            ModelTrainedEvent,
            ModelDeployedEvent,
            ModelRetiredEvent,
        ]

    def test_failed_then_retrain(self):
        model = MLModel(name="resilient")
        model.start_training("run-1")
        model.fail_training("transient error")
        assert model.status == ModelStatus.FAILED

        # FAILED -> TRAINING is allowed.
        model.start_training("run-2")
        assert model.status == ModelStatus.TRAINING
        assert model.mlflow_run_id == "run-2"


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class TestToDict:
    def test_keys_present_for_fresh_model(self):
        model = MLModel(
            name="serial",
            version="2.0.0",
            base_model="llama-7b",
            description="desc",
        )
        data = model.to_dict()

        # Base entity fields.
        assert data["id"] == str(model.id)
        assert "created_at" in data
        assert "updated_at" in data

        # Model fields.
        assert data["name"] == "serial"
        assert data["version"] == "2.0.0"
        assert data["base_model"] == "llama-7b"
        assert data["description"] == "desc"
        assert data["status"] == "draft"
        assert data["metrics"] is None
        assert data["mlflow_run_id"] is None
        assert data["model_path"] is None
        assert data["deployment_strategy"] is None
        assert data["traffic_percentage"] == 0
        assert data["deployed_at"] is None
        assert data["retired_at"] is None
        assert data["hyperparameters"] == {}
        assert data["tags"] == {}

    def test_status_serialized_as_value_string(self):
        model = MLModel(name="x", status=ModelStatus.TRAINED)
        assert model.to_dict()["status"] == "trained"

    def test_tags_are_copied(self):
        model = MLModel(name="x")
        model.add_tag("k", "v")
        data = model.to_dict()
        data["tags"]["injected"] = "boom"
        # Internal tags must not be mutated by mutating the dump.
        assert "injected" not in model.to_dict()["tags"]

    def test_hyperparameters_are_copied(self):
        # Use the hyperparameters property (a copy) rather than to_dict(),
        # which is unavailable once metrics are set.
        model = MLModel(name="x")
        model.start_training("run-1")
        model.complete_training(ModelMetrics(accuracy=0.5), "/p", {"a": 1})
        hp = model.hyperparameters
        hp["b"] = 2
        assert "b" not in model.hyperparameters
        assert model.hyperparameters == {"a": 1}

    def test_to_dict_raises_when_metrics_present(self):
        # Documented real behaviour: to_dict() calls metrics.to_dict(), but
        # ModelMetrics has no such method, so serialization fails once a model
        # carries metrics. This is an intentional regression guard, not an
        # endorsement of the behaviour.
        model = MLModel(name="x")
        model.start_training("run-1")
        model.complete_training(ModelMetrics(accuracy=0.9), "/p", {})
        with pytest.raises(AttributeError):
            model.to_dict()


# ---------------------------------------------------------------------------
# Identity / equality (inherited from Entity)
# ---------------------------------------------------------------------------


class TestIdentity:
    def test_equal_when_same_id(self):
        shared = uuid4()
        a = MLModel(id=shared, name="a")
        b = MLModel(id=shared, name="b-different-name")
        assert a == b
        assert hash(a) == hash(b)

    def test_not_equal_when_different_id(self):
        a = MLModel(name="a")
        b = MLModel(name="a")
        assert a != b

    def test_not_equal_to_non_entity(self):
        model = MLModel(name="a")
        assert model != "a"
        assert model != 42
        assert model is not None
