"""
Integration tests for complete fine-tuning pipeline.

Tests end-to-end fine-tuning workflow:
1. Data preparation from annotations
2. Fine-tuning job creation
3. MLflow tracking integration
4. Automatic MinIO backup
5. Version management
6. Model testing
7. Cleanup
"""

import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from loguru import logger

from src.infrastructure.ml.fine_tuning.fine_tuning_service import FineTuningService
from src.infrastructure.storage.minio_adapter import MinIOStorageAdapter
from src.infrastructure.storage.versioning_service import ModelVersioningService


@pytest.mark.integration
@pytest.mark.ollama
@pytest.mark.mlflow
class TestFineTuningCompletePipeline:
    """Test complete fine-tuning pipeline end-to-end."""

    @pytest.mark.asyncio
    async def test_data_preparation_from_annotations(
        self,
        sample_annotations: list[dict],
    ):
        """Test converting Label Studio annotations to training data."""
        from src.infrastructure.ml.fine_tuning.data_preparation import (
            DataPreparationService,
        )

        data_prep = DataPreparationService()

        # Prepare training data
        training_data = data_prep.prepare_training_data(
            annotations=sample_annotations,
            task_type="classification",
        )

        assert len(training_data) > 0
        assert all("prompt" in item for item in training_data)
        assert all("completion" in item for item in training_data)

        logger.info(f"✓ Prepared {len(training_data)} training examples")

        # Validate data
        validation_stats = data_prep.validate_training_data(training_data)

        assert validation_stats["total_examples"] == len(training_data)
        assert validation_stats["valid_examples"] > 0

        logger.info(
            f"✓ Validation: {validation_stats['valid_examples']}/{validation_stats['total_examples']} valid"
        )

    @pytest.mark.asyncio
    async def test_modelfile_generation(
        self,
        sample_annotations: list[dict],
    ):
        """Test Ollama Modelfile generation from training data."""
        from src.infrastructure.ml.fine_tuning.data_preparation import (
            DataPreparationService,
        )

        data_prep = DataPreparationService()

        # Prepare data
        training_data = data_prep.prepare_training_data(
            annotations=sample_annotations,
            task_type="classification",
        )

        # Generate Modelfile
        modelfile = data_prep.convert_to_ollama_format(
            training_data=training_data,
            base_model="qwen3-coder:30b",
        )

        assert "FROM qwen3-coder:30b" in modelfile
        assert "PARAMETER" in modelfile
        assert "MESSAGE" in modelfile

        logger.info("✓ Generated Ollama Modelfile")
        logger.info(f"  Length: {len(modelfile)} chars")
        logger.info(f"  Examples: {modelfile.count('MESSAGE user')}")

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_fine_tuning_job_creation(
        self,
        mock_subprocess,
        sample_annotations: list[dict],
        settings,
    ):
        """Test creating and starting a fine-tuning job."""
        # Mock subprocess for ollama create
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"Model created successfully", b""))
        mock_subprocess.return_value = mock_process

        # Create service
        service = FineTuningService(
            ollama_url=settings.ollama.url,
            mlflow_tracking_uri=None,  # Disable MLflow for this test
        )

        # Start fine-tuning
        project_id = str(uuid4())
        base_model = "qwen3-coder:30b"

        job = await service.start_fine_tuning(
            project_id=project_id,
            base_model=base_model,
            annotations=sample_annotations,
            task_type="classification",
        )

        assert job["job_id"] is not None
        assert job["project_id"] == project_id
        assert job["base_model"] == base_model
        assert job["status"] in ["preparing", "training"]
        assert job["training_examples"] == len(sample_annotations)

        logger.info(f"✓ Created fine-tuning job: {job['job_id']}")
        logger.info(f"  Status: {job['status']}")
        logger.info(f"  Training examples: {job['training_examples']}")

        # Wait briefly for background task
        await asyncio.sleep(0.5)

        # Get job status
        status = await service.get_job_status(job["job_id"])
        assert status is not None

        logger.info(f"✓ Job status retrieved: {status['status']}")

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    @patch("httpx.AsyncClient.post")
    async def test_fine_tuning_with_mlflow_tracking(
        self,
        mock_http_post,
        mock_subprocess,
        sample_annotations: list[dict],
        settings,
        tmp_path,
    ):
        """Test fine-tuning with MLflow experiment tracking."""
        # Mock subprocess for ollama create
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"Model created successfully", b""))
        mock_subprocess.return_value = mock_process

        # Mock HTTP response for model testing
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"response": "Hello, I am a fine-tuned model."})
        mock_http_post.return_value = mock_response

        # Create service with MLflow
        mlflow_uri = f"file://{tmp_path}/mlruns"
        service = FineTuningService(
            ollama_url=settings.ollama.url,
            mlflow_tracking_uri=mlflow_uri,
        )

        # Start fine-tuning
        job = await service.start_fine_tuning(
            project_id="test-project",
            base_model="qwen3-coder:30b",
            annotations=sample_annotations,
            task_type="classification",
            model_name="test-finetuned-model",
        )

        assert "mlflow_run_id" in job
        logger.info(f"✓ MLflow run created: {job['mlflow_run_id']}")

        # Wait for training to complete
        await asyncio.sleep(1)

        # Verify MLflow tracking
        mlflow_dir = Path(mlflow_uri.replace("file://", ""))
        assert mlflow_dir.exists()

        logger.info("✓ MLflow tracking enabled and working")

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_fine_tuning_with_minio_backup(
        self,
        mock_subprocess,
        sample_annotations: list[dict],
        storage_adapter: MinIOStorageAdapter,
        versioning_service: ModelVersioningService,
        settings,
    ):
        """Test automatic MinIO backup after fine-tuning."""
        # Mock successful ollama create
        mock_create_process = AsyncMock()
        mock_create_process.returncode = 0
        mock_create_process.communicate = AsyncMock(return_value=(b"Model created", b""))

        # Mock successful ollama show --modelfile
        mock_show_process = AsyncMock()
        mock_show_process.returncode = 0
        mock_show_process.communicate = AsyncMock(
            return_value=(b"FROM qwen3-coder:30b\nSYSTEM Test", b"")
        )

        async def subprocess_side_effect(*args, **kwargs):
            """Return different mocks based on command."""
            if "show" in args:
                return mock_show_process
            return mock_create_process

        mock_subprocess.side_effect = subprocess_side_effect

        # Create service with storage
        service = FineTuningService(
            ollama_url=settings.ollama.url,
            mlflow_tracking_uri=None,
            storage_service=storage_adapter,
            versioning_service=versioning_service,
        )

        # Start fine-tuning
        model_name = f"test-model-{uuid4().hex[:8]}"
        job = await service.start_fine_tuning(
            project_id="test-project",
            base_model="qwen3-coder:30b",
            annotations=sample_annotations,
            task_type="classification",
            model_name=model_name,
        )

        logger.info(f"✓ Started fine-tuning job: {job['job_id']}")

        # Wait for training and backup to complete
        max_wait = 10
        for i in range(max_wait):
            await asyncio.sleep(0.5)
            status = await service.get_job_status(job["job_id"])

            if status["status"] == "completed":
                break

        assert status["status"] == "completed"
        logger.info("✓ Fine-tuning completed")

        # Verify MinIO backup
        if "storage_version" in status:
            assert status["storage_version"] is not None
            assert status["storage_path"] is not None

            logger.info("✓ Model backed up to MinIO:")
            logger.info(f"  Version: {status['storage_version']}")
            logger.info(f"  Path: {status['storage_path']}")

            # Verify version exists in storage
            from src.domain.value_objects.version import AutoIncrementVersion

            version = AutoIncrementVersion.from_string(status["storage_version"])
            exists = await storage_adapter.version_exists(model_name, version)
            assert exists

            logger.info("✓ Backup verified in MinIO storage")

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_fine_tuning_failure_handling(
        self,
        mock_subprocess,
        sample_annotations: list[dict],
        settings,
    ):
        """Test error handling when fine-tuning fails."""
        # Mock failed ollama create
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", b"Error: Model creation failed"))
        mock_subprocess.return_value = mock_process

        service = FineTuningService(ollama_url=settings.ollama.url)

        # Start fine-tuning (should fail)
        job = await service.start_fine_tuning(
            project_id="test-project",
            base_model="qwen3-coder:30b",
            annotations=sample_annotations,
            task_type="classification",
        )

        # Wait for failure
        await asyncio.sleep(1)

        # Check job status
        status = await service.get_job_status(job["job_id"])
        assert status["status"] == "failed"
        assert "error" in status

        logger.info("✓ Failed job handled correctly")
        logger.info(f"  Error: {status['error']}")

    @pytest.mark.asyncio
    async def test_job_listing_and_filtering(
        self,
        sample_annotations: list[dict],
        settings,
    ):
        """Test listing and filtering fine-tuning jobs."""
        service = FineTuningService(ollama_url=settings.ollama.url)

        # Create jobs for different projects
        projects = ["project-1", "project-2", "project-1"]

        with patch("asyncio.create_subprocess_exec"):
            for project_id in projects:
                await service.start_fine_tuning(
                    project_id=project_id,
                    base_model="qwen3-coder:30b",
                    annotations=sample_annotations,
                    task_type="classification",
                )

        # List all jobs
        all_jobs = await service.list_jobs()
        assert len(all_jobs) == 3

        logger.info(f"✓ Listed all jobs: {len(all_jobs)}")

        # Filter by project
        project1_jobs = await service.list_jobs(project_id="project-1")
        assert len(project1_jobs) == 2
        assert all(j["project_id"] == "project-1" for j in project1_jobs)

        logger.info(f"✓ Filtered by project: {len(project1_jobs)} jobs")

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_model_deletion(
        self,
        mock_subprocess,
        settings,
    ):
        """Test deleting a fine-tuned model."""
        # Mock successful deletion
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"deleted 'test-model'", b""))
        mock_subprocess.return_value = mock_process

        service = FineTuningService(ollama_url=settings.ollama.url)

        # Delete model
        result = await service.delete_model("test-model")

        assert result["status"] == "success"
        logger.info("✓ Model deleted successfully")

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.get")
    async def test_list_fine_tuned_models(
        self,
        mock_http_get,
        settings,
    ):
        """Test listing all fine-tuned models."""
        # Mock Ollama API response
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={
                "models": [
                    {"name": "qwen3-coder-finetuned-20250113"},
                    {"name": "llama2-7b-finetuned-20250112"},
                    {"name": "qwen3-coder:30b"},  # Not fine-tuned
                ]
            }
        )
        mock_http_get.return_value = mock_response

        service = FineTuningService(ollama_url=settings.ollama.url)

        # List fine-tuned models
        models = await service.list_fine_tuned_models()

        assert len(models) == 2
        assert all("finetuned" in m["name"].lower() for m in models)

        logger.info(f"✓ Listed {len(models)} fine-tuned models")

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_model_export(
        self,
        mock_subprocess,
        settings,
        tmp_path,
    ):
        """Test exporting a fine-tuned model."""
        # Mock ollama show --modelfile
        modelfile_content = "FROM qwen3-coder:30b\nSYSTEM Test export"
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(modelfile_content.encode(), b""))
        mock_subprocess.return_value = mock_process

        service = FineTuningService(ollama_url=settings.ollama.url)

        # Export model
        export_path = tmp_path / "exported_model"
        result = await service.export_model(
            model_name="test-finetuned-model",
            export_path=export_path,
        )

        assert result["status"] == "success"
        assert export_path.exists()
        assert export_path.read_text() == modelfile_content

        logger.info(f"✓ Model exported to: {export_path}")


@pytest.mark.integration
@pytest.mark.ollama
class TestFineTuningEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_empty_annotations(
        self,
        settings,
    ):
        """Test handling empty annotations."""
        service = FineTuningService(ollama_url=settings.ollama.url)

        # Should raise error for empty annotations
        with pytest.raises(ValueError, match="No training data"):
            await service.start_fine_tuning(
                project_id="test",
                base_model="qwen3-coder:30b",
                annotations=[],
                task_type="classification",
            )

        logger.info("✓ Empty annotations rejected correctly")

    @pytest.mark.asyncio
    async def test_invalid_annotations(
        self,
        settings,
    ):
        """Test handling invalid annotation format."""
        from src.infrastructure.ml.fine_tuning.data_preparation import (
            DataPreparationService,
        )

        data_prep = DataPreparationService()

        # Invalid annotations (missing required fields)
        invalid_annotations = [
            {"id": 1, "data": {}},  # Missing text
            {"id": 2},  # Missing data
        ]

        # Prepare should return empty list or raise error
        training_data = data_prep.prepare_training_data(
            annotations=invalid_annotations,
            task_type="classification",
        )

        # Should have no valid training examples
        validation_stats = data_prep.validate_training_data(training_data)
        assert validation_stats["valid_examples"] == 0

        logger.info("✓ Invalid annotations handled correctly")

    @pytest.mark.asyncio
    async def test_job_not_found(
        self,
        settings,
    ):
        """Test retrieving non-existent job."""
        service = FineTuningService(ollama_url=settings.ollama.url)

        status = await service.get_job_status("non-existent-job-id")
        assert status is None

        logger.info("✓ Non-existent job returns None")

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_concurrent_fine_tuning_jobs(
        self,
        mock_subprocess,
        sample_annotations: list[dict],
        settings,
    ):
        """Test running multiple fine-tuning jobs concurrently."""
        # Mock successful creation
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"Model created", b""))
        mock_subprocess.return_value = mock_process

        service = FineTuningService(ollama_url=settings.ollama.url)

        # Start multiple jobs concurrently
        jobs = await asyncio.gather(
            service.start_fine_tuning(
                project_id="project-1",
                base_model="qwen3-coder:30b",
                annotations=sample_annotations,
                task_type="classification",
            ),
            service.start_fine_tuning(
                project_id="project-2",
                base_model="qwen3-coder:30b",
                annotations=sample_annotations,
                task_type="classification",
            ),
            service.start_fine_tuning(
                project_id="project-3",
                base_model="qwen3-coder:30b",
                annotations=sample_annotations,
                task_type="classification",
            ),
        )

        # Verify all jobs created with unique IDs
        job_ids = [j["job_id"] for j in jobs]
        assert len(job_ids) == len(set(job_ids))  # All unique

        logger.info(f"✓ Created {len(jobs)} concurrent jobs successfully")
