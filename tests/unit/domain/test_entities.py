"""Tests for domain entities.

This module tests the core domain entities including:
- Entity and AggregateRoot base classes
- MLModel entity with state machine transitions
- Feedback entity with negative detection
- ModelMetrics value object
"""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest

from src.domain.entities.base import AggregateRoot, Entity
from src.domain.entities.dataset import (
    Dataset,
    DatasetMetadata,
    DatasetStatus,
    DatasetType,
)
from src.domain.entities.feedback import (
    Feedback,
    FeedbackStatus,
    FeedbackType,
)
from src.domain.entities.ml_model import (
    DeploymentStrategy,
    MLModel,
    ModelMetrics,
    ModelStatus,
)
from src.domain.entities.training_job import (
    TrainingConfig,
    TrainingJob,
    TrainingJobStatus,
    TrainingTrigger,
)


class TestEntity:
    """Tests for Entity base class."""

    def test_entity_creation_generates_uuid(self):
        """Entity should generate a UUID if not provided."""

        class ConcreteEntity(Entity):
            pass

        entity = ConcreteEntity()

        assert isinstance(entity.id, UUID)
        assert entity.created_at is not None
        assert entity.updated_at is not None

    def test_entity_creation_with_provided_id(self):
        """Entity should use provided UUID."""

        class ConcreteEntity(Entity):
            pass

        custom_id = uuid4()
        entity = ConcreteEntity(id=custom_id)

        assert entity.id == custom_id

    def test_entity_equality_based_on_id(self):
        """Two entities with same ID should be equal."""

        class ConcreteEntity(Entity):
            pass

        shared_id = uuid4()
        entity1 = ConcreteEntity(id=shared_id)
        entity2 = ConcreteEntity(id=shared_id)

        assert entity1 == entity2
        assert hash(entity1) == hash(entity2)

    def test_entity_inequality_with_different_ids(self):
        """Entities with different IDs should not be equal."""

        class ConcreteEntity(Entity):
            pass

        entity1 = ConcreteEntity()
        entity2 = ConcreteEntity()

        assert entity1 != entity2

    def test_entity_inequality_with_non_entity(self):
        """Entity should not be equal to non-Entity objects."""

        class ConcreteEntity(Entity):
            pass

        entity = ConcreteEntity()

        assert entity != "not an entity"
        assert entity != 123
        assert entity != None

    def test_entity_touch_updates_timestamp(self):
        """_touch() should update updated_at timestamp."""

        class ConcreteEntity(Entity):
            def update(self):
                self._touch()

        entity = ConcreteEntity()
        original_updated_at = entity.updated_at

        # Small delay to ensure timestamp changes
        import time

        time.sleep(0.001)
        entity.update()

        assert entity.updated_at >= original_updated_at

    def test_entity_to_dict(self):
        """Entity should serialize to dictionary."""

        class ConcreteEntity(Entity):
            pass

        entity = ConcreteEntity()
        data = entity.to_dict()

        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert data["id"] == str(entity.id)


class TestAggregateRoot:
    """Tests for AggregateRoot base class."""

    def test_aggregate_root_has_domain_events(self):
        """AggregateRoot should manage domain events."""

        class ConcreteAggregate(AggregateRoot):
            pass

        aggregate = ConcreteAggregate()

        assert aggregate.domain_events == []

    def test_aggregate_root_add_domain_event(self):
        """AggregateRoot should accept domain events."""

        class ConcreteAggregate(AggregateRoot):
            pass

        aggregate = ConcreteAggregate()
        event = {"type": "TestEvent", "data": "test"}

        aggregate.add_domain_event(event)

        assert len(aggregate.domain_events) == 1
        assert aggregate.domain_events[0] == event

    def test_aggregate_root_clear_events(self):
        """AggregateRoot should clear domain events."""

        class ConcreteAggregate(AggregateRoot):
            pass

        aggregate = ConcreteAggregate()
        aggregate.add_domain_event({"type": "Event1"})
        aggregate.add_domain_event({"type": "Event2"})

        aggregate.clear_domain_events()

        assert aggregate.domain_events == []

    def test_aggregate_root_events_are_copied(self):
        """domain_events property should return a copy."""

        class ConcreteAggregate(AggregateRoot):
            pass

        aggregate = ConcreteAggregate()
        aggregate.add_domain_event({"type": "Event1"})

        events = aggregate.domain_events
        events.append({"type": "Injected"})

        # Original should not be modified
        assert len(aggregate.domain_events) == 1


class TestModelMetrics:
    """Tests for ModelMetrics value object."""

    def test_model_metrics_creation(self):
        """ModelMetrics should be created with valid accuracy."""
        metrics = ModelMetrics(
            accuracy=0.95,
            precision=0.90,
            recall=0.92,
            f1_score=0.91,
        )

        assert metrics.accuracy == 0.95
        assert metrics.precision == 0.90
        assert metrics.recall == 0.92
        assert metrics.f1_score == 0.91

    def test_model_metrics_accuracy_validation_low(self):
        """ModelMetrics should reject accuracy below 0."""
        with pytest.raises(ValueError, match="Accuracy must be between 0 and 1"):
            ModelMetrics(accuracy=-0.1)

    def test_model_metrics_accuracy_validation_high(self):
        """ModelMetrics should reject accuracy above 1."""
        with pytest.raises(ValueError, match="Accuracy must be between 0 and 1"):
            ModelMetrics(accuracy=1.5)

    def test_model_metrics_edge_cases(self):
        """ModelMetrics should accept edge values 0 and 1."""
        metrics_zero = ModelMetrics(accuracy=0.0)
        metrics_one = ModelMetrics(accuracy=1.0)

        assert metrics_zero.accuracy == 0.0
        assert metrics_one.accuracy == 1.0

    def test_model_metrics_with_custom_metrics(self):
        """ModelMetrics should accept custom metrics."""
        custom = {"bleu_score": 0.85, "rouge_l": 0.78}
        metrics = ModelMetrics(accuracy=0.90, custom_metrics=custom)

        assert metrics.custom_metrics == custom

    def test_model_metrics_is_frozen(self):
        """ModelMetrics should be immutable."""
        metrics = ModelMetrics(accuracy=0.90)

        with pytest.raises(Exception):  # FrozenInstanceError
            metrics.accuracy = 0.95


class TestMLModel:
    """Tests for MLModel aggregate root."""

    def test_ml_model_creation_default_status(self):
        """MLModel should be created with DRAFT status by default."""
        model = MLModel(name="test-model", version="1.0.0")

        assert model.name == "test-model"
        assert model.version == "1.0.0"
        assert model.status == ModelStatus.DRAFT

    def test_ml_model_start_training(self):
        """MLModel should transition to TRAINING status."""
        model = MLModel(name="test-model")

        model.start_training(mlflow_run_id="run-123")

        assert model.status == ModelStatus.TRAINING
        assert model.mlflow_run_id == "run-123"

    def test_ml_model_start_training_invalid_status(self):
        """MLModel should reject training from invalid status."""
        model = MLModel(name="test-model", status=ModelStatus.DEPLOYED)

        with pytest.raises(ValueError, match="Cannot start training"):
            model.start_training(mlflow_run_id="run-123")

    def test_ml_model_complete_training(self):
        """MLModel should complete training with metrics."""
        model = MLModel(name="test-model")
        model.start_training("run-123")

        metrics = ModelMetrics(accuracy=0.95)
        model.complete_training(
            metrics=metrics,
            model_path="/models/test-model",
            hyperparameters={"lr": 0.001, "epochs": 10},
        )

        assert model.status == ModelStatus.TRAINED
        assert model.metrics.accuracy == 0.95
        assert model.model_path == "/models/test-model"
        assert model.hyperparameters["lr"] == 0.001

    def test_ml_model_complete_training_emits_event(self):
        """MLModel should emit ModelTrainedEvent."""
        model = MLModel(name="test-model")
        model.start_training("run-123")

        metrics = ModelMetrics(accuracy=0.95)
        model.complete_training(metrics, "/path", {})

        assert len(model.domain_events) == 1
        event = model.domain_events[0]
        assert event.aggregate_id == model.id  # Events use aggregate_id
        assert event.accuracy == 0.95

    def test_ml_model_fail_training(self):
        """MLModel should handle training failure."""
        model = MLModel(name="test-model")
        model.start_training("run-123")

        model.fail_training("Out of memory error")

        assert model.status == ModelStatus.FAILED

    def test_ml_model_validation_flow(self):
        """MLModel should handle validation flow."""
        model = MLModel(name="test-model")
        model.start_training("run-123")
        model.complete_training(ModelMetrics(accuracy=0.9), "/path", {})

        model.validate()
        assert model.status == ModelStatus.VALIDATING

        model.complete_validation(is_valid=True)
        assert model.status == ModelStatus.VALIDATED

    def test_ml_model_validation_failure(self):
        """MLModel should handle validation failure."""
        model = MLModel(name="test-model")
        model.start_training("run-123")
        model.complete_training(ModelMetrics(accuracy=0.9), "/path", {})
        model.validate()

        model.complete_validation(is_valid=False)

        assert model.status == ModelStatus.FAILED

    def test_ml_model_deployment(self):
        """MLModel should handle deployment."""
        model = MLModel(name="test-model")
        model.start_training("run-123")
        model.complete_training(ModelMetrics(accuracy=0.9), "/path", {})
        model.validate()
        model.complete_validation(True)

        model.deploy(strategy=DeploymentStrategy.CANARY, traffic_percentage=10)
        assert model.status == ModelStatus.DEPLOYING
        assert model.deployment_strategy == DeploymentStrategy.CANARY
        assert model.traffic_percentage == 10

        model.complete_deployment()
        assert model.status == ModelStatus.DEPLOYED
        assert model.is_deployed is True

    def test_ml_model_deployment_emits_event(self):
        """MLModel should emit ModelDeployedEvent."""
        model = MLModel(name="test-model")
        model.start_training("run-123")
        model.complete_training(ModelMetrics(accuracy=0.9), "/path", {})
        model.validate()
        model.complete_validation(True)
        model.deploy()
        model.clear_domain_events()  # Clear training event

        model.complete_deployment()

        assert len(model.domain_events) == 1
        event = model.domain_events[0]
        assert event.aggregate_id == model.id  # Events use aggregate_id

    def test_ml_model_update_traffic(self):
        """MLModel should allow traffic updates when deployed."""
        model = MLModel(name="test-model")
        model.start_training("run-123")
        model.complete_training(ModelMetrics(accuracy=0.9), "/path", {})
        model.validate()
        model.complete_validation(True)
        model.deploy(strategy=DeploymentStrategy.CANARY, traffic_percentage=10)
        model.complete_deployment()

        model.update_traffic(50)

        assert model.traffic_percentage == 50

    def test_ml_model_invalid_traffic_percentage(self):
        """MLModel should reject invalid traffic percentages."""
        model = MLModel(name="test-model", status=ModelStatus.VALIDATED)

        with pytest.raises(ValueError, match="Traffic percentage must be between"):
            model.deploy(traffic_percentage=150)

    def test_ml_model_retire(self):
        """MLModel should handle retirement."""
        model = MLModel(name="test-model")
        model.start_training("run-123")
        model.complete_training(ModelMetrics(accuracy=0.9), "/path", {})
        model.validate()
        model.complete_validation(True)
        model.deploy()
        model.complete_deployment()

        model.retire(reason="Replaced by v2")

        assert model.status == ModelStatus.RETIRED
        assert model.traffic_percentage == 0

    def test_ml_model_to_dict(self):
        """MLModel should serialize to dictionary."""
        model = MLModel(
            name="test-model",
            version="2.0.0",
            base_model="llama-7b",
            description="Test description",
        )

        data = model.to_dict()

        assert data["name"] == "test-model"
        assert data["version"] == "2.0.0"
        assert data["base_model"] == "llama-7b"
        assert data["description"] == "Test description"
        assert data["status"] == "draft"


class TestFeedback:
    """Tests for Feedback entity."""

    def test_feedback_creation(self):
        """Feedback should be created with required fields."""
        model_id = uuid4()
        feedback = Feedback(
            model_id=model_id,
            feedback_type=FeedbackType.RATING,
            rating=5,
        )

        assert feedback.model_id == model_id
        assert feedback.feedback_type == FeedbackType.RATING
        assert feedback.rating == 5
        assert feedback.status == FeedbackStatus.PENDING

    def test_feedback_rating_validation(self):
        """Feedback should validate rating range."""
        model_id = uuid4()

        with pytest.raises(ValueError, match="Rating must be between 1 and 5"):
            Feedback(
                model_id=model_id,
                feedback_type=FeedbackType.RATING,
                rating=10,
            )

    def test_feedback_is_negative_thumbs_down(self):
        """is_negative should return True for thumbs down."""
        feedback = Feedback(
            model_id=uuid4(),
            feedback_type=FeedbackType.THUMBS_DOWN,
        )

        assert feedback.is_negative() is True

    def test_feedback_is_negative_low_rating(self):
        """is_negative should return True for low ratings."""
        feedback = Feedback(
            model_id=uuid4(),
            feedback_type=FeedbackType.RATING,
            rating=2,
        )

        assert feedback.is_negative() is True

    def test_feedback_is_negative_correction(self):
        """is_negative should return True for corrections."""
        feedback = Feedback(
            model_id=uuid4(),
            feedback_type=FeedbackType.CORRECTION,
            correction="Fixed output",
        )

        assert feedback.is_negative() is True

    def test_feedback_is_negative_bug_report(self):
        """is_negative should return True for bug reports."""
        feedback = Feedback(
            model_id=uuid4(),
            feedback_type=FeedbackType.BUG_REPORT,
        )

        assert feedback.is_negative() is True

    def test_feedback_is_positive(self):
        """is_negative should return False for positive feedback."""
        feedback = Feedback(
            model_id=uuid4(),
            feedback_type=FeedbackType.THUMBS_UP,
        )

        assert feedback.is_negative() is False

    def test_feedback_is_positive_high_rating(self):
        """is_negative should return False for high ratings."""
        feedback = Feedback(
            model_id=uuid4(),
            feedback_type=FeedbackType.RATING,
            rating=5,
        )

        assert feedback.is_negative() is False

    def test_feedback_status_transitions(self):
        """Feedback should support status transitions."""
        feedback = Feedback(
            model_id=uuid4(),
            feedback_type=FeedbackType.RATING,
            rating=4,
        )

        assert feedback.status == FeedbackStatus.PENDING

        feedback.mark_reviewed()
        assert feedback.status == FeedbackStatus.REVIEWED

        feedback.mark_actioned()
        assert feedback.status == FeedbackStatus.ACTIONED

    def test_feedback_dismiss(self):
        """Feedback should support dismissal."""
        feedback = Feedback(
            model_id=uuid4(),
            feedback_type=FeedbackType.RATING,
            rating=3,
        )

        feedback.dismiss()

        assert feedback.status == FeedbackStatus.DISMISSED

    def test_feedback_add_comment(self):
        """Feedback should allow adding comments."""
        feedback = Feedback(
            model_id=uuid4(),
            feedback_type=FeedbackType.RATING,
            rating=3,
        )

        feedback.add_comment("This is helpful")

        assert feedback.comment == "This is helpful"

    def test_feedback_update_metadata(self):
        """Feedback should allow updating metadata."""
        feedback = Feedback(
            model_id=uuid4(),
            feedback_type=FeedbackType.RATING,
            rating=4,
            metadata={"source": "web"},
        )

        feedback.update_metadata({"user_agent": "Chrome"})

        assert feedback.metadata["source"] == "web"
        assert feedback.metadata["user_agent"] == "Chrome"

    def test_feedback_to_dict(self):
        """Feedback should serialize to dictionary."""
        model_id = uuid4()
        feedback = Feedback(
            model_id=model_id,
            feedback_type=FeedbackType.RATING,
            rating=4,
            comment="Good prediction",
        )

        data = feedback.to_dict()

        assert data["model_id"] == str(model_id)
        assert data["feedback_type"] == "rating"
        assert data["rating"] == 4
        assert data["comment"] == "Good prediction"
        assert data["is_negative"] is False


class TestFeedbackTypes:
    """Tests for FeedbackType enum."""

    def test_feedback_types_values(self):
        """FeedbackType should have correct string values."""
        assert FeedbackType.THUMBS_UP.value == "thumbs_up"
        assert FeedbackType.THUMBS_DOWN.value == "thumbs_down"
        assert FeedbackType.RATING.value == "rating"
        assert FeedbackType.CORRECTION.value == "correction"
        assert FeedbackType.BUG_REPORT.value == "bug_report"
        assert FeedbackType.IMPLICIT.value == "implicit"


class TestModelStatus:
    """Tests for ModelStatus enum."""

    def test_model_status_values(self):
        """ModelStatus should have correct string values."""
        assert ModelStatus.DRAFT.value == "draft"
        assert ModelStatus.TRAINING.value == "training"
        assert ModelStatus.TRAINED.value == "trained"
        assert ModelStatus.DEPLOYED.value == "deployed"
        assert ModelStatus.RETIRED.value == "retired"


class TestDeploymentStrategy:
    """Tests for DeploymentStrategy enum."""

    def test_deployment_strategy_values(self):
        """DeploymentStrategy should have correct string values."""
        assert DeploymentStrategy.DIRECT.value == "direct"
        assert DeploymentStrategy.CANARY.value == "canary"
        assert DeploymentStrategy.BLUE_GREEN.value == "blue_green"
        assert DeploymentStrategy.A_B_TEST.value == "a_b_test"


class TestDatasetMetadata:
    """Tests for DatasetMetadata value object."""

    def test_metadata_creation(self):
        """DatasetMetadata should be created with required fields."""
        metadata = DatasetMetadata(
            size=1000,
            source="user_interactions",
            format="jsonl",
        )

        assert metadata.size == 1000
        assert metadata.source == "user_interactions"
        assert metadata.format == "jsonl"

    def test_metadata_annotation_progress_complete(self):
        """Should calculate annotation progress."""
        metadata = DatasetMetadata(
            size=100,
            source="manual",
            format="jsonl",
            annotations_required=True,
            annotations_completed=50,
        )

        assert metadata.annotation_progress() == 50.0

    def test_metadata_annotation_progress_not_required(self):
        """Should return 100% when annotations not required."""
        metadata = DatasetMetadata(
            size=100,
            source="manual",
            format="jsonl",
            annotations_required=False,
        )

        assert metadata.annotation_progress() == 100.0

    def test_metadata_annotation_progress_empty_dataset(self):
        """Should handle empty dataset."""
        metadata = DatasetMetadata(
            size=0,
            source="manual",
            format="jsonl",
        )

        assert metadata.annotation_progress() == 100.0

    def test_metadata_is_frozen(self):
        """DatasetMetadata should be immutable."""
        metadata = DatasetMetadata(size=100, source="test", format="jsonl")

        with pytest.raises(Exception):
            metadata.size = 200


class TestDataset:
    """Tests for Dataset aggregate root."""

    def test_dataset_creation_default_status(self):
        """Dataset should be created with DRAFT status."""
        dataset = Dataset(name="test-dataset")

        assert dataset.name == "test-dataset"
        assert dataset.status == DatasetStatus.DRAFT
        assert dataset.dataset_type == DatasetType.TRAINING

    def test_dataset_creation_custom_type(self):
        """Dataset should accept custom type."""
        dataset = Dataset(
            name="validation-data",
            dataset_type=DatasetType.VALIDATION,
        )

        assert dataset.dataset_type == DatasetType.VALIDATION

    def test_dataset_is_ready(self):
        """is_ready should return True only when READY."""
        dataset = Dataset(name="test")
        assert dataset.is_ready is False

        dataset._status = DatasetStatus.READY
        assert dataset.is_ready is True

    def test_dataset_create_method(self):
        """create() should set metadata and transition to PROCESSING."""
        dataset = Dataset(name="test")
        metadata = DatasetMetadata(size=100, source="test", format="jsonl")

        dataset.create(metadata, "/path/to/data")

        assert dataset.status == DatasetStatus.PROCESSING
        assert dataset.metadata == metadata
        assert dataset.storage_path == "/path/to/data"

    def test_dataset_create_invalid_status(self):
        """create() should fail if not in DRAFT status."""
        dataset = Dataset(name="test", status=DatasetStatus.READY)
        metadata = DatasetMetadata(size=100, source="test", format="jsonl")

        with pytest.raises(ValueError, match="only create datasets in draft"):
            dataset.create(metadata, "/path")

    def test_dataset_complete_processing_with_annotations(self):
        """complete_processing should transition to ANNOTATING."""
        dataset = Dataset(name="test")
        metadata = DatasetMetadata(
            size=100, source="test", format="jsonl", annotations_required=True
        )
        dataset.create(metadata, "/path")

        dataset.complete_processing({"total_rows": 100})

        assert dataset.status == DatasetStatus.ANNOTATING

    def test_dataset_complete_processing_without_annotations(self):
        """complete_processing should transition to READY if no annotations needed."""
        dataset = Dataset(name="test")
        metadata = DatasetMetadata(
            size=100, source="test", format="jsonl", annotations_required=False
        )
        dataset.create(metadata, "/path")

        dataset.complete_processing({"total_rows": 100})

        assert dataset.status == DatasetStatus.READY

    def test_dataset_link_label_studio_project(self):
        """Should link Label Studio project."""
        dataset = Dataset(name="test")

        dataset.link_label_studio_project(123)

        assert dataset.label_studio_project_id == 123

    def test_dataset_update_annotation_progress(self):
        """Should update annotation progress."""
        dataset = Dataset(name="test")
        metadata = DatasetMetadata(size=100, source="test", format="jsonl")
        dataset.create(metadata, "/path")
        dataset.complete_processing({})

        dataset.update_annotation_progress(50)

        assert dataset.metadata.annotations_completed == 50

    def test_dataset_update_annotation_progress_complete(self):
        """Should mark READY when all annotations complete."""
        dataset = Dataset(name="test")
        metadata = DatasetMetadata(size=100, source="test", format="jsonl")
        dataset.create(metadata, "/path")
        dataset.complete_processing({})

        dataset.update_annotation_progress(100)

        assert dataset.status == DatasetStatus.READY

    def test_dataset_fail(self):
        """fail() should mark dataset as FAILED."""
        dataset = Dataset(name="test")

        dataset.fail("Processing error")

        assert dataset.status == DatasetStatus.FAILED

    def test_dataset_archive(self):
        """archive() should mark dataset as ARCHIVED."""
        dataset = Dataset(name="test")

        dataset.archive()

        assert dataset.status == DatasetStatus.ARCHIVED

    def test_dataset_add_tag(self):
        """Should add tags to dataset."""
        dataset = Dataset(name="test")

        dataset.add_tag("version", "v1.0")
        dataset.add_tag("project", "ml-training")

        data = dataset.to_dict()
        assert data["tags"]["version"] == "v1.0"
        assert data["tags"]["project"] == "ml-training"

    def test_dataset_to_dict(self):
        """Dataset should serialize to dictionary."""
        dataset = Dataset(
            name="test-dataset",
            dataset_type=DatasetType.TEST,
        )

        data = dataset.to_dict()

        assert data["name"] == "test-dataset"
        assert data["dataset_type"] == "test"
        assert data["status"] == "draft"


class TestDatasetType:
    """Tests for DatasetType enum."""

    def test_dataset_type_values(self):
        """DatasetType should have correct values."""
        assert DatasetType.TRAINING.value == "training"
        assert DatasetType.VALIDATION.value == "validation"
        assert DatasetType.TEST.value == "test"
        assert DatasetType.PRODUCTION.value == "production"


class TestDatasetStatus:
    """Tests for DatasetStatus enum."""

    def test_dataset_status_values(self):
        """DatasetStatus should have correct values."""
        assert DatasetStatus.DRAFT.value == "draft"
        assert DatasetStatus.PROCESSING.value == "processing"
        assert DatasetStatus.READY.value == "ready"
        assert DatasetStatus.ANNOTATING.value == "annotating"
        assert DatasetStatus.FAILED.value == "failed"


class TestTrainingConfig:
    """Tests for TrainingConfig value object."""

    def test_training_config_creation(self):
        """TrainingConfig should be created with default values."""
        config = TrainingConfig(
            base_model="qwen2.5-coder-7b",
            dataset_id=uuid4(),
        )

        assert config.base_model == "qwen2.5-coder-7b"
        assert config.batch_size == 4  # Default is 4
        assert config.num_epochs == 3

    def test_training_config_custom_values(self):
        """TrainingConfig should accept custom hyperparameters."""
        dataset_id = uuid4()
        config = TrainingConfig(
            base_model="llama3.2",
            dataset_id=dataset_id,
            batch_size=16,
            learning_rate=5e-5,
            num_epochs=5,
            lora_rank=16,
        )

        assert config.batch_size == 16
        assert config.learning_rate == 5e-5
        assert config.num_epochs == 5
        assert config.lora_rank == 16


class TestTrainingJob:
    """Tests for TrainingJob aggregate root."""

    def test_training_job_creation(self):
        """TrainingJob should be created with PENDING status."""
        job = TrainingJob(name="train-model-v1")

        assert job.name == "train-model-v1"
        assert job.status == TrainingJobStatus.PENDING
        assert job.trigger == TrainingTrigger.MANUAL

    def test_training_job_configure(self):
        """configure() should set training config."""
        job = TrainingJob(name="train-model-v1")
        config = TrainingConfig(base_model="llama3.2", dataset_id=uuid4())

        job.configure(config)

        assert job.config == config
        # configure() doesn't change status, only stores config

    def test_training_job_start(self):
        """start() should transition to PREPARING_DATA."""
        job = TrainingJob(name="train-model-v1")
        config = TrainingConfig(base_model="llama3.2", dataset_id=uuid4())
        job.configure(config)

        job.start(mlflow_run_id="run-123")

        assert job.status == TrainingJobStatus.PREPARING_DATA
        assert job.mlflow_run_id == "run-123"

    def test_training_job_start_training_phase(self):
        """start_training_phase() should transition to TRAINING."""
        job = TrainingJob(name="train-model-v1")
        config = TrainingConfig(base_model="llama3.2", dataset_id=uuid4())
        job.configure(config)
        job.start(mlflow_run_id="run-123")

        job.start_training_phase()

        assert job.status == TrainingJobStatus.TRAINING

    def test_training_job_start_evaluation_phase(self):
        """start_evaluation_phase() should transition to EVALUATING."""
        job = TrainingJob(name="train-model-v1")
        config = TrainingConfig(base_model="llama3.2", dataset_id=uuid4())
        job.configure(config)
        job.start(mlflow_run_id="run-123")
        job.start_training_phase()

        job.start_evaluation_phase()

        assert job.status == TrainingJobStatus.EVALUATING

    def test_training_job_complete(self):
        """complete() should transition to COMPLETED."""
        job = TrainingJob(name="train-model-v1")
        config = TrainingConfig(base_model="llama3.2", dataset_id=uuid4())
        job.configure(config)
        job.start("run-123")
        job.start_training_phase()
        job.start_evaluation_phase()

        output_model_id = uuid4()
        job.complete(
            output_model_id=output_model_id,
            final_metrics={"accuracy": 0.95, "loss": 0.1},
        )

        assert job.status == TrainingJobStatus.COMPLETED
        assert job.output_model_id == output_model_id

    def test_training_job_fail(self):
        """fail() should transition to FAILED."""
        job = TrainingJob(name="train-model-v1")
        config = TrainingConfig(base_model="llama3.2", dataset_id=uuid4())
        job.configure(config)
        job.start("run-123")

        job.fail("Out of memory")

        assert job.status == TrainingJobStatus.FAILED

    def test_training_job_cancel(self):
        """cancel() should transition to CANCELLED."""
        job = TrainingJob(name="train-model-v1")
        config = TrainingConfig(base_model="llama3.2", dataset_id=uuid4())
        job.configure(config)
        job.start("run-123")

        job.cancel()

        assert job.status == TrainingJobStatus.CANCELLED

    def test_training_job_is_completed(self):
        """is_completed should return True for COMPLETED state."""
        job = TrainingJob(name="test")

        assert job.is_completed is False

        job._status = TrainingJobStatus.COMPLETED
        assert job.is_completed is True

    def test_training_job_is_failed(self):
        """is_failed should return True for FAILED state."""
        job = TrainingJob(name="test")

        assert job.is_failed is False

        job._status = TrainingJobStatus.FAILED
        assert job.is_failed is True

    def test_training_job_update_metrics(self):
        """update_metrics() should update job metrics."""
        job = TrainingJob(name="train-model-v1")
        config = TrainingConfig(base_model="llama3.2", dataset_id=uuid4())
        job.configure(config)
        job.start("run-123")

        job.update_metrics({"loss": 0.5, "accuracy": 0.8})

        assert job.metrics["loss"] == 0.5
        assert job.metrics["accuracy"] == 0.8

    def test_training_job_to_dict(self):
        """TrainingJob should serialize to dictionary."""
        job = TrainingJob(
            name="train-model-v1",
            trigger=TrainingTrigger.SCHEDULED,
        )

        data = job.to_dict()

        assert data["name"] == "train-model-v1"
        assert data["trigger"] == "scheduled"
        assert data["status"] == "pending"


class TestTrainingJobStatus:
    """Tests for TrainingJobStatus enum."""

    def test_training_status_values(self):
        """TrainingJobStatus should have correct values."""
        assert TrainingJobStatus.PENDING.value == "pending"
        assert TrainingJobStatus.PREPARING_DATA.value == "preparing_data"
        assert TrainingJobStatus.TRAINING.value == "training"
        assert TrainingJobStatus.EVALUATING.value == "evaluating"
        assert TrainingJobStatus.COMPLETED.value == "completed"
        assert TrainingJobStatus.FAILED.value == "failed"
        assert TrainingJobStatus.CANCELLED.value == "cancelled"


class TestTrainingTrigger:
    """Tests for TrainingTrigger enum."""

    def test_training_trigger_values(self):
        """TrainingTrigger should have correct values."""
        assert TrainingTrigger.MANUAL.value == "manual"
        assert TrainingTrigger.SCHEDULED.value == "scheduled"
        assert TrainingTrigger.PERFORMANCE_DEGRADATION.value == "performance_degradation"
        assert TrainingTrigger.DATA_DRIFT.value == "data_drift"
        assert TrainingTrigger.NEW_DATA_THRESHOLD.value == "new_data_threshold"
