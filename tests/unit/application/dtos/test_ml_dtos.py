"""Tests for ML DTOs - dataclass validation."""

from uuid import uuid4

from src.application.dtos.ml_dtos import (
    CheckDataDriftRequest,
    CheckDataDriftResponse,
    CreateAnnotationProjectRequest,
    CreateAnnotationProjectResponse,
    CreateDatasetRequest,
    CreateDatasetResponse,
    DataDriftReport,
    DeployModelRequest,
    DeployModelResponse,
    FeedbackStatisticsResponse,
    ListModelsResponse,
    ListTrainingJobsResponse,
    ModelInfo,
    ModelMetricsRequest,
    ModelMetricsResponse,
    PredictionRequest,
    PredictionResponse,
    SubmitFeedbackRequest,
    SubmitFeedbackResponse,
    TrainingJobInfo,
    TrainModelRequest,
    TrainModelResponse,
    TriggerRetrainingRequest,
    TriggerRetrainingResponse,
    UpdateTrafficRequest,
    UpdateTrafficResponse,
)


class TestTrainModelDTOs:
    """Test training DTOs."""

    def test_train_request_defaults(self):
        req = TrainModelRequest(
            name="my_model",
            base_model="llama2",
            dataset_id=uuid4(),
        )
        assert req.version == "1.0.0"
        assert req.batch_size == 4
        assert req.learning_rate == 2e-5
        assert req.num_epochs == 3
        assert req.lora_rank == 8
        assert req.use_rlhf is False

    def test_train_response(self):
        uid = uuid4()
        resp = TrainModelResponse(
            training_job_id=uid,
            model_id=uuid4(),
            status="running",
        )
        assert resp.status == "running"
        assert resp.mlflow_run_id is None


class TestPredictionDTOs:
    """Test prediction DTOs."""

    def test_prediction_request_defaults(self):
        req = PredictionRequest(input_data={"text": "hello"})
        assert req.temperature == 0.7
        assert req.max_tokens == 512
        assert req.model_id is None

    def test_prediction_response(self):
        resp = PredictionResponse(
            prediction_id=uuid4(),
            model_id=uuid4(),
            model_version="1.0",
            output={"text": "world"},
        )
        assert resp.confidence is None


class TestFeedbackDTOs:
    """Test feedback DTOs."""

    def test_submit_request(self):
        req = SubmitFeedbackRequest(
            model_id=uuid4(),
            feedback_type="thumbs_up",
        )
        assert req.rating is None
        assert req.comment is None

    def test_submit_response(self):
        resp = SubmitFeedbackResponse(
            feedback_id=uuid4(),
            model_id=uuid4(),
            feedback_type="thumbs_up",
            status="recorded",
            created_at="2026-01-01T00:00:00",
        )
        assert resp.status == "recorded"

    def test_statistics_response(self):
        resp = FeedbackStatisticsResponse(
            model_id=uuid4(),
            model_name="m",
            model_version="1",
            total_count=100,
            counts_by_type={"thumbs_up": 80, "thumbs_down": 20},
            average_rating=4.2,
            negative_count=20,
            negative_percentage=20.0,
        )
        assert resp.negative_percentage == 20.0


class TestDatasetDTOs:
    """Test dataset DTOs."""

    def test_create_request(self):
        req = CreateDatasetRequest(
            name="train_v1",
            dataset_type="training",
            source="sirene",
            storage_path="/data/datasets/v1",
            size=10000,
        )
        assert req.format == "jsonl"
        assert req.annotations_required is True

    def test_create_response(self):
        resp = CreateDatasetResponse(
            dataset_id=uuid4(),
            name="train_v1",
            status="created",
        )
        assert resp.status == "created"


class TestDeploymentDTOs:
    """Test deployment DTOs."""

    def test_deploy_request_defaults(self):
        req = DeployModelRequest(model_id=uuid4())
        assert req.strategy == "canary"
        assert req.traffic_percentage == 10
        assert req.auto_promote is False
        assert req.rollback_threshold == 0.1

    def test_deploy_response(self):
        resp = DeployModelResponse(
            model_id=uuid4(),
            deployment_status="deployed",
            traffic_percentage=100,
        )
        assert resp.endpoint_url is None

    def test_update_traffic(self):
        uid = uuid4()
        req = UpdateTrafficRequest(model_id=uid, new_percentage=50)
        assert req.new_percentage == 50
        resp = UpdateTrafficResponse(model_id=uid, traffic_percentage=50, status="updated")
        assert resp.status == "updated"


class TestModelDTOs:
    """Test model info DTOs."""

    def test_model_info(self):
        info = ModelInfo(
            id=uuid4(),
            name="m",
            version="1.0",
            status="deployed",
            accuracy=0.95,
            traffic_percentage=100,
        )
        assert info.accuracy == 0.95

    def test_list_models_response(self):
        resp = ListModelsResponse(models=[], total=0, page=1, page_size=10)
        assert resp.total == 0


class TestTrainingJobDTOs:
    """Test training job DTOs."""

    def test_job_info_defaults(self):
        info = TrainingJobInfo(
            id=uuid4(),
            name="job1",
            status="completed",
            trigger="manual",
        )
        assert info.metrics == {}  # __post_init__

    def test_job_info_with_metrics(self):
        info = TrainingJobInfo(
            id=uuid4(),
            name="job1",
            status="completed",
            trigger="manual",
            metrics={"loss": 0.1},
        )
        assert info.metrics["loss"] == 0.1

    def test_list_jobs(self):
        resp = ListTrainingJobsResponse(jobs=[], total=0, page=1, page_size=10)
        assert resp.total == 0


class TestRetrainingDTOs:
    """Test retraining DTOs."""

    def test_trigger_request(self):
        req = TriggerRetrainingRequest(trigger_reason="scheduled")
        assert req.current_model_id is None

    def test_trigger_response(self):
        resp = TriggerRetrainingResponse(
            training_job_id=uuid4(),
            trigger_reason="drift",
            status="started",
        )
        assert resp.status == "started"


class TestAnnotationDTOs:
    """Test annotation DTOs."""

    def test_create_project_request(self):
        req = CreateAnnotationProjectRequest(
            dataset_id=uuid4(),
            project_name="proj1",
            labeling_config="<View></View>",
        )
        assert req.enable_ml_backend is True

    def test_create_project_response(self):
        resp = CreateAnnotationProjectResponse(
            project_id=42,
            dataset_id=uuid4(),
            project_url="http://labelstudio/project/42",
        )
        assert resp.project_id == 42


class TestMetricsDTOs:
    """Test metrics DTOs."""

    def test_request(self):
        req = ModelMetricsRequest(
            model_id=uuid4(),
            metric_types=["accuracy", "latency"],
        )
        assert req.time_range_hours == 24

    def test_response(self):
        resp = ModelMetricsResponse(
            model_id=uuid4(),
            metrics={"accuracy": 0.95},
            time_range_hours=24,
        )
        assert resp.metrics["accuracy"] == 0.95


class TestDataDriftDTOs:
    """Test data drift DTOs."""

    def test_drift_report(self):
        report = DataDriftReport(
            drift_detected=True,
            drift_score=0.7,
            drifted_features=["feature1", "feature2"],
        )
        assert len(report.drifted_features) == 2
        assert report.report_path is None

    def test_check_request(self):
        req = CheckDataDriftRequest(reference_dataset_id=uuid4())
        assert req.threshold == 0.5

    def test_check_response(self):
        report = DataDriftReport(
            drift_detected=True,
            drift_score=0.7,
            drifted_features=["f1"],
        )
        resp = CheckDataDriftResponse(report=report, should_retrain=True)
        assert resp.should_retrain is True
