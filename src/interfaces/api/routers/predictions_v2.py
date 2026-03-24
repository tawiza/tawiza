"""Predictions API router v2 - With Ollama integration."""

import time
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.ml_model import ModelStatus
from src.infrastructure.config.settings import get_settings
from src.infrastructure.ml.ollama import OllamaAdapter, OllamaInferenceService
from src.infrastructure.persistence.database import get_db_session
from src.infrastructure.persistence.repositories.ml_model_repository import (
    SQLAlchemyMLModelRepository,
)

router = APIRouter()


# Request/Response models for API
class PredictionRequestModel(BaseModel):
    """API model for prediction request."""

    prompt: str = Field(..., description="Input prompt for prediction")
    model_id: UUID | None = Field(
        None, description="Specific model ID (uses latest deployed if not provided)"
    )
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(512, ge=1, le=4096, description="Maximum tokens to generate")
    top_p: float = Field(0.9, ge=0.0, le=1.0, description="Nucleus sampling parameter")


class PredictionResponseModel(BaseModel):
    """API model for prediction response."""

    prediction_id: UUID
    model_id: UUID
    model_name: str
    model_version: str
    prompt: str
    text: str
    confidence: float | None = None
    latency_ms: float
    usage: dict = {}


# Dependency to get Ollama service
async def get_ollama_service() -> OllamaInferenceService:
    """Get Ollama inference service with configuration from settings."""
    settings = get_settings()
    adapter = OllamaAdapter(
        base_url=settings.ollama.base_url,
        pool_connections=settings.ollama.pool_connections,
        pool_maxsize=settings.ollama.pool_maxsize,
    )
    service = OllamaInferenceService(adapter, default_model="qwen3.5:27b")
    return service


@router.post(
    "",
    response_model=PredictionResponseModel,
    status_code=status.HTTP_200_OK,
    summary="Make a prediction",
    description="Generate a prediction using Ollama LLM",
)
async def predict(
    request: PredictionRequestModel,
    session: AsyncSession = Depends(get_db_session),
    ollama_service: OllamaInferenceService = Depends(get_ollama_service),
) -> PredictionResponseModel:
    """
    Make a prediction using Ollama.

    This endpoint:
    1. Gets the specified model or latest deployed
    2. Maps model_id to Ollama model name
    3. Generates prediction using OllamaInferenceService
    4. Tracks metrics and returns response

    Args:
        request: Prediction request with prompt and parameters
        session: Database session
        ollama_service: Ollama inference service

    Returns:
        Prediction response with generated text

    Raises:
        HTTPException: If prediction fails or model not found
    """
    start_time = time.time()
    prediction_id = uuid4()

    try:
        model_repo = SQLAlchemyMLModelRepository(session)

        # 1. Get model (use specified or latest deployed)
        if request.model_id:
            model = await model_repo.get_by_id(request.model_id)
            if not model:
                raise ValueError(f"Model {request.model_id} not found")

            # Verify model is deployed
            if model.status != ModelStatus.DEPLOYED:
                raise ValueError(
                    f"Model {model.name} v{model.version} is not deployed "
                    f"(status: {model.status.value})"
                )
        else:
            # Get latest deployed model
            deployed_models = await model_repo.get_by_status(ModelStatus.DEPLOYED)
            if not deployed_models:
                # If no deployed model, use default Ollama model
                logger.warning("No deployed models found, using default qwen3.5:27b")
                model = None
            else:
                # Sort by created_at descending and take first
                model = sorted(deployed_models, key=lambda m: m.created_at, reverse=True)[0]
                logger.info(f"Using latest deployed model: {model.name} v{model.version}")

        # 2. Determine which Ollama model to use
        if model and model.base_model:
            # Use the base_model from our model entity as Ollama model name
            ollama_model = model.base_model
        else:
            # Default to qwen3.5:27b
            ollama_model = "qwen3.5:27b"

        # Register mapping if we have a model
        if model:
            ollama_service.register_model(str(model.id), ollama_model)

        logger.info(
            f"Making prediction with Ollama model: {ollama_model} (prediction_id: {prediction_id})"
        )

        # 3. Generate prediction using Ollama
        result = await ollama_service.predict(
            model_id=str(model.id) if model else ollama_model,
            input_data={"prompt": request.prompt},
            parameters={
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
            },
        )

        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000

        logger.info(
            f"Prediction {prediction_id} completed in {latency_ms:.2f}ms "
            f"(tokens: {result['usage']['total_tokens']})"
        )

        # 4. Store prediction in database
        from src.infrastructure.persistence.repositories.prediction_repository import (
            PredictionRepository,
        )

        pred_repo = PredictionRepository(session)
        await pred_repo.create(
            prediction_id=prediction_id,
            model_id=model.id if model else None,
            model_name=model.name if model else ollama_model,
            model_version=model.version if model else "1.0.0",
            prompt=request.prompt,
            response_text=result["text"],
            confidence=result.get("confidence"),
            latency_ms=round(latency_ms, 2),
            prompt_tokens=result["usage"].get("prompt_tokens", 0),
            completion_tokens=result["usage"].get("completion_tokens", 0),
            total_tokens=result["usage"].get("total_tokens", 0),
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        await session.commit()

        # 5. Return response
        return PredictionResponseModel(
            prediction_id=prediction_id,
            model_id=model.id if model else uuid4(),
            model_name=model.name if model else ollama_model,
            model_version=model.version if model else "1.0.0",
            prompt=request.prompt,
            text=result["text"],
            confidence=result.get("confidence"),
            latency_ms=round(latency_ms, 2),
            usage=result["usage"],
        )

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Prediction failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction failed: {str(e)}",
        )


@router.get(
    "/{prediction_id}",
    response_model=PredictionResponseModel,
    status_code=status.HTTP_200_OK,
    summary="Get prediction result",
    description="Retrieve a prediction result by ID",
)
async def get_prediction(
    prediction_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> PredictionResponseModel:
    """
    Get prediction result by ID.

    Args:
        prediction_id: Prediction UUID
        session: Database session

    Returns:
        Prediction details

    Raises:
        HTTPException: If prediction not found
    """
    from src.infrastructure.persistence.repositories.prediction_repository import (
        PredictionRepository,
    )

    pred_repo = PredictionRepository(session)
    prediction = await pred_repo.get_by_id(prediction_id)

    if not prediction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prediction {prediction_id} not found",
        )

    return PredictionResponseModel(
        prediction_id=prediction.id,
        model_id=prediction.model_id or uuid4(),
        model_name=prediction.model_name,
        model_version=prediction.model_version,
        prompt=prediction.prompt,
        text=prediction.response_text,
        confidence=prediction.confidence,
        latency_ms=prediction.latency_ms,
        usage={
            "prompt_tokens": prediction.prompt_tokens,
            "completion_tokens": prediction.completion_tokens,
            "total_tokens": prediction.total_tokens,
        },
    )


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="List predictions",
    description="List recent predictions with optional filtering",
)
async def list_predictions(
    limit: int = 50,
    offset: int = 0,
    model_name: str | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    List recent predictions.

    Args:
        limit: Maximum number of results
        offset: Pagination offset
        model_name: Filter by model name
        session: Database session

    Returns:
        List of predictions with pagination info
    """
    from src.infrastructure.persistence.repositories.prediction_repository import (
        PredictionRepository,
    )

    pred_repo = PredictionRepository(session)
    predictions = await pred_repo.list_recent(limit=limit, offset=offset, model_name=model_name)
    total = await pred_repo.count(model_name=model_name)

    return {
        "predictions": [
            {
                "prediction_id": str(p.id),
                "model_name": p.model_name,
                "prompt": p.prompt[:100] + "..." if len(p.prompt) > 100 else p.prompt,
                "latency_ms": p.latency_ms,
                "total_tokens": p.total_tokens,
                "created_at": p.created_at.isoformat(),
            }
            for p in predictions
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/stats",
    status_code=status.HTTP_200_OK,
    summary="Get prediction stats",
    description="Get aggregate statistics for predictions",
)
async def get_prediction_stats(
    model_name: str | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Get prediction statistics.

    Args:
        model_name: Filter by model name
        session: Database session

    Returns:
        Aggregate statistics
    """
    from src.infrastructure.persistence.repositories.prediction_repository import (
        PredictionRepository,
    )

    pred_repo = PredictionRepository(session)
    stats = await pred_repo.get_stats(model_name=model_name)

    return {
        "model_name": model_name or "all",
        **stats,
    }
