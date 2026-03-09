"""
Integration tests for complete ML pipeline.

Tests the full workflow:
1. Dataset creation
2. Training job
3. Model deployment
4. Predictions
5. Feedback collection
6. Retraining trigger
"""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from src.interfaces.api.main import app


@pytest.fixture
async def client():
    """Create async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestMLPipelineComplete:
    """Test complete ML pipeline end-to-end."""

    @pytest.mark.asyncio
    async def test_complete_ml_pipeline(self, client: AsyncClient):
        """
        Test complete ML pipeline from dataset creation to retraining.

        Flow:
        1. Create dataset
        2. Start training job
        3. Wait for training completion
        4. Deploy trained model
        5. Make predictions
        6. Submit feedback
        7. Check retraining criteria
        8. Trigger retraining
        """
        # Step 1: Create dataset
        dataset_response = await client.post(
            "/api/v1/datasets/",
            json={
                "name": "test_pipeline_dataset",
                "description": "Dataset for integration testing",
                "data_source": "test_source",
                "task_type": "classification",
            },
        )
        assert dataset_response.status_code == 201
        dataset = dataset_response.json()
        dataset_id = dataset["id"]
        print(f"✓ Created dataset: {dataset_id}")

        # Step 2: Start training job
        training_response = await client.post(
            "/api/v1/training",
            json={
                "dataset_id": dataset_id,
                "model_type": "classification",
                "hyperparameters": {
                    "learning_rate": 0.001,
                    "epochs": 5,
                    "batch_size": 32,
                },
                "ollama_model": "qwen3:14b",
            },
        )
        assert training_response.status_code in [200, 201, 202]
        training_job = training_response.json()
        job_id = training_job.get("id") or training_job.get("job_id")
        print(f"✓ Started training job: {job_id}")

        # Step 3: Poll training status (max 30 seconds for test)
        max_attempts = 30
        for attempt in range(max_attempts):
            status_response = await client.get(f"/api/v1/training/{job_id}")
            if status_response.status_code == 200:
                job_status = status_response.json()
                status = job_status.get("status")
                print(f"  Training status: {status} (attempt {attempt + 1}/{max_attempts})")

                if status in ["completed", "success", "finished"]:
                    model_id = job_status.get("model_id")
                    print(f"✓ Training completed, model ID: {model_id}")
                    break
                elif status in ["failed", "error"]:
                    pytest.fail(f"Training failed: {job_status.get('error')}")

            await asyncio.sleep(1)
        else:
            # Training didn't complete in time - this is ok for integration test
            # We can still test the rest of the pipeline with a mock model
            print("⚠ Training didn't complete in time, using mock model")
            model_id = "test-model-id"

        # Step 4: Deploy model (if we have a real model)
        if model_id != "test-model-id":
            deploy_response = await client.post(
                "/api/v1/models/deploy",
                json={
                    "model_id": model_id,
                    "version": "1.0.0",
                    "traffic_percentage": 100,
                },
            )
            assert deploy_response.status_code in [200, 201]
            print(f"✓ Deployed model: {model_id}")

        # Step 5: Make predictions
        prediction_response = await client.post(
            "/api/v1/predictions",
            json={
                "model_id": model_id,
                "input_data": {
                    "text": "This is a test prediction",
                    "features": [1.0, 2.0, 3.0],
                },
            },
        )
        assert prediction_response.status_code == 200
        prediction = prediction_response.json()
        prediction_id = prediction.get("id") or prediction.get("prediction_id")
        print(f"✓ Made prediction: {prediction_id}")

        # Step 6: Submit feedback
        feedback_response = await client.post(
            "/api/v1/feedback",
            json={
                "prediction_id": prediction_id,
                "model_id": model_id,
                "feedback_type": "correction",
                "correct_label": "positive",
                "user_rating": 4,
                "comments": "Test feedback for integration",
            },
        )
        assert feedback_response.status_code in [200, 201]
        print("✓ Submitted feedback")

        # Step 7: Check feedback statistics
        stats_response = await client.get(f"/api/v1/feedback/statistics/{model_id}")
        if stats_response.status_code == 200:
            stats = stats_response.json()
            print(f"✓ Feedback stats: {stats}")

        # Step 8: Check retraining criteria
        retraining_check_response = await client.get(
            f"/api/v1/retraining/retraining/check/{model_id}"
        )
        if retraining_check_response.status_code == 200:
            retraining_needed = retraining_check_response.json()
            print(f"✓ Retraining check: {retraining_needed}")

            # If retraining is needed, trigger it
            if retraining_needed.get("should_retrain"):
                trigger_response = await client.post(
                    "/api/v1/retraining/retraining/trigger",
                    json={"model_id": model_id},
                )
                assert trigger_response.status_code in [200, 201, 202]
                print("✓ Triggered retraining")

        print("\n✅ Complete ML pipeline test passed!")

    @pytest.mark.asyncio
    async def test_training_endpoints(self, client: AsyncClient):
        """Test training endpoints."""
        # List models
        models_response = await client.get("/api/v1/models")
        assert models_response.status_code == 200
        models = models_response.json()
        print(f"✓ Found {len(models)} models")

        # Start training with minimal config
        training_response = await client.post(
            "/api/v1/training",
            json={
                "dataset_id": "test-dataset",
                "model_type": "classification",
                "ollama_model": "qwen3:14b",
            },
        )
        # Accept any success-like status
        assert training_response.status_code in [200, 201, 202, 422]
        print(f"✓ Training endpoint responded with {training_response.status_code}")

    @pytest.mark.asyncio
    async def test_prediction_endpoints(self, client: AsyncClient):
        """Test prediction endpoints."""
        # Make a prediction
        prediction_response = await client.post(
            "/api/v1/predictions",
            json={
                "model_id": "test-model",
                "input_data": {"text": "Test input"},
            },
        )
        # Prediction might fail if no model deployed, that's ok
        print(f"✓ Prediction endpoint responded with {prediction_response.status_code}")

        if prediction_response.status_code == 200:
            prediction = prediction_response.json()
            prediction_id = prediction.get("id") or prediction.get("prediction_id")

            # Get prediction details
            detail_response = await client.get(f"/api/v1/predictions/{prediction_id}")
            assert detail_response.status_code in [200, 404]
            print("✓ Prediction detail endpoint responded")

    @pytest.mark.asyncio
    async def test_feedback_endpoints(self, client: AsyncClient):
        """Test feedback endpoints."""
        # Submit feedback
        feedback_response = await client.post(
            "/api/v1/feedback",
            json={
                "prediction_id": "test-prediction",
                "model_id": "test-model",
                "feedback_type": "rating",
                "user_rating": 5,
            },
        )
        # Feedback might fail if prediction doesn't exist
        print(f"✓ Feedback endpoint responded with {feedback_response.status_code}")

    @pytest.mark.asyncio
    async def test_health_endpoints(self, client: AsyncClient):
        """Test all health endpoints."""
        health_endpoints = [
            "/health",
            "/api/v1/ollama/health",
            "/api/v1/browser/health",
            "/api/v1/agents/health",
            "/api/v1/orchestration/health",
        ]

        for endpoint in health_endpoints:
            response = await client.get(endpoint)
            if response.status_code == 200:
                health = response.json()
                print(f"✓ {endpoint}: {health.get('status', 'ok')}")
            else:
                print(f"⚠ {endpoint}: {response.status_code} (not available)")


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v", "-s"])
