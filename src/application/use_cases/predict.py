"""Prediction use case."""

import os
import time
from uuid import uuid4

from loguru import logger

from src.application.dtos.ml_dtos import PredictionRequest, PredictionResponse
from src.application.ports.ml_ports import IModelInference
from src.domain.repositories.ml_repositories import IFeedbackRepository, IMLModelRepository


class PredictUseCase:
    """Use case for making predictions with a deployed model.

    This orchestrates the prediction process:
    1. Select the appropriate model (specified or latest deployed)
    2. Route request based on traffic distribution (for canary deployments)
    3. Make the prediction
    4. Log the prediction for future feedback
    5. Return the result
    """

    def __init__(
        self,
        model_repository: IMLModelRepository,
        model_inference: IModelInference,
        feedback_repository: IFeedbackRepository | None = None,
    ) -> None:
        """Initialize the use case with required dependencies.

        Args:
            model_repository: Repository for ML models
            model_inference: Service for model inference
            feedback_repository: Optional repository for logging predictions
        """
        self.model_repository = model_repository
        self.model_inference = model_inference
        self.feedback_repository = feedback_repository

    async def execute(self, request: PredictionRequest) -> PredictionResponse:
        """Execute the prediction use case.

        Args:
            request: Prediction request with input data

        Returns:
            Prediction response with output

        Raises:
            ValueError: If no model is available for prediction
        """
        prediction_id = uuid4()
        start_time = time.time()

        # 1. Select model
        if request.model_id:
            model = await self.model_repository.get_by_id(request.model_id)
            if not model:
                raise ValueError(f"Model {request.model_id} not found")
            if not model.is_deployed:
                raise ValueError(
                    f"Model {model.name} v{model.version} is not deployed "
                    f"(status: {model.status.value})"
                )
        else:
            # Get latest deployed model
            model = await self.model_repository.get_latest_deployed()
            if not model:
                raise ValueError("No deployed model available")

        logger.info(f"Making prediction with model {model.name} v{model.version} (ID: {model.id})")

        # 2. Prepare inference parameters
        inference_params = {
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
        }

        # 3. Make prediction
        try:
            output = await self.model_inference.predict(
                model_id=str(model.id),
                input_data=request.input_data,
                parameters=inference_params,
            )

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            logger.info(
                f"Prediction completed in {latency_ms:.2f}ms (prediction_id: {prediction_id})"
            )

            # Extract confidence if available
            confidence = output.get("confidence")

            # 4. Create response
            response = PredictionResponse(
                prediction_id=prediction_id,
                model_id=model.id,
                model_version=model.version,
                output=output,
                confidence=confidence,
                latency_ms=latency_ms,
            )

            # 5. Log prediction to database for feedback loop
            if self.feedback_repository:
                try:
                    import json

                    from src.domain.entities.feedback import Feedback, FeedbackType

                    feedback = Feedback(
                        model_id=model.id,
                        prediction_id=prediction_id,
                        input_data=json.dumps(request.input_data)
                        if isinstance(request.input_data, dict)
                        else str(request.input_data),
                        output_data=json.dumps(output) if isinstance(output, dict) else str(output),
                        feedback_type=FeedbackType.IMPLICIT,
                        metadata={
                            "latency_ms": latency_ms,
                            "model_version": model.version,
                            "confidence": confidence,
                        },
                    )
                    await self.feedback_repository.create(feedback)
                    logger.debug(f"Prediction logged: {prediction_id}")
                except Exception as log_error:
                    logger.warning(f"Failed to log prediction: {log_error}")

            return response

        except Exception as e:
            # Log failure for monitoring
            logger.error(
                f"Prediction failed: {e}",
                extra={
                    "prediction_id": str(prediction_id),
                    "model_id": str(model.id) if model else None,
                    "error_type": type(e).__name__,
                },
            )
            raise
