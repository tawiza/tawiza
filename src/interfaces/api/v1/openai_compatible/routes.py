"""OpenAI-compatible API routes for LobeChat integration."""

import os
import time
from typing import Union

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger

from src.application.services.agent_orchestrator import AgentOrchestrator
from src.infrastructure.security.auth import User as AuthUser
from src.infrastructure.security.auth import get_current_user
from src.interfaces.api.v1.openai_compatible.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    Embedding,
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingUsage,
    Model,
    ModelList,
)

router = APIRouter(prefix="/v1", tags=["OpenAI Compatible"])

# Singleton orchestrator
_orchestrator: AgentOrchestrator = None


def get_orchestrator() -> AgentOrchestrator:
    """Get or create orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator


@router.post("/chat/completions", response_model=ChatCompletionResponse | dict)
async def chat_completions(
    request: ChatCompletionRequest,
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Create a chat completion (OpenAI-compatible).

    This endpoint supports both Tawiza agents (models starting with "tawiza-")
    and standard Ollama models.

    **Example with Tawiza agent:**
    ```json
    {
        "model": "tawiza-analyst",
        "messages": [
            {"role": "user", "content": "Analyze the economy of Paris"}
        ],
        "stream": false
    }
    ```

    **Example with Ollama model:**
    ```json
    {
        "model": "qwen3-coder:30b",
        "messages": [
            {"role": "user", "content": "Write a Python function"}
        ],
        "stream": false
    }
    ```

    **Streaming example:**
    Set `"stream": true` to receive Server-Sent Events.
    """
    try:
        orchestrator = get_orchestrator()

        if request.stream:
            # Return streaming response
            async def event_generator():
                try:
                    async for chunk in orchestrator.chat_completion_stream(request):
                        yield chunk
                except Exception as e:
                    logger.error(f"Streaming error: {e}", exc_info=True)
                    error_chunk = {
                        "error": {
                            "message": str(e),
                            "type": "internal_error",
                            "code": "streaming_error",
                        }
                    }
                    yield f"data: {error_chunk}\n\n"

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",  # Disable nginx buffering
                },
            )
        else:
            # Return synchronous response
            response = await orchestrator.chat_completion(request)
            return response

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Chat completion error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models", response_model=ModelList)
async def list_models(current_user: AuthUser = Depends(get_current_user)):
    """
    List available models.

    Returns both Tawiza agents and Ollama models in OpenAI-compatible format.

    **Tawiza Agents:**
    - `tawiza-analyst`: Strategic analysis and territorial intelligence
    - `tawiza-data`: Sirene data collection
    - `tawiza-geo`: Mapping and geolocation
    - `tawiza-veille`: Market monitoring (BODACC, BOAMP)
    - `tawiza-finance`: Financial data analysis
    - `tawiza-simulation`: Scenario simulation
    - `tawiza-prospection`: B2B lead generation
    - `tawiza-comparison`: Territory comparison
    - `tawiza-business-plan`: Business plan generation

    **Ollama Models:**
    All models available on the configured Ollama instance.
    """
    try:
        orchestrator = get_orchestrator()
        models = await orchestrator.list_models()

        # Convert to OpenAI format
        model_list = ModelList(
            object="list",
            data=[Model(**model) for model in models],
        )

        return model_list

    except Exception as e:
        logger.error(f"Failed to list models: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/embeddings", response_model=EmbeddingResponse)
async def create_embeddings(
    request: EmbeddingRequest,
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Create embeddings (forwarded to Ollama).

    **Example:**
    ```json
    {
        "model": "nomic-embed-text",
        "input": "The quick brown fox jumps over the lazy dog"
    }
    ```

    **Batch example:**
    ```json
    {
        "model": "nomic-embed-text",
        "input": [
            "First text to embed",
            "Second text to embed"
        ]
    }
    ```
    """
    try:
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        # Normalize input to list
        texts = [request.input] if isinstance(request.input, str) else request.input

        embeddings = []
        total_tokens = 0

        # Call Ollama for each text
        async with httpx.AsyncClient(timeout=120.0) as client:
            for idx, text in enumerate(texts):
                response = await client.post(
                    f"{ollama_url}/api/embed",
                    json={
                        "model": request.model,
                        "input": text,
                    },
                )
                response.raise_for_status()

                data = response.json()
                embs = data.get("embeddings", [[]])
                embedding_vector = embs[0] if embs else []

                embeddings.append(
                    Embedding(
                        object="embedding",
                        embedding=embedding_vector,
                        index=idx,
                    )
                )

                # Estimate tokens (rough approximation)
                total_tokens += len(text) // 4

        return EmbeddingResponse(
            object="list",
            data=embeddings,
            model=request.model,
            usage=EmbeddingUsage(
                prompt_tokens=total_tokens,
                total_tokens=total_tokens,
            ),
        )

    except httpx.HTTPStatusError as e:
        logger.error(f"Ollama embeddings error: {e}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Ollama error: {e.response.text}",
        )
    except Exception as e:
        logger.error(f"Embeddings error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models/{model_id}")
async def get_model(model_id: str, current_user: AuthUser = Depends(get_current_user)):
    """
    Get specific model details.

    **Example:**
    ```
    GET /v1/models/tawiza-analyst
    ```
    """
    try:
        orchestrator = get_orchestrator()
        models = await orchestrator.list_models()

        # Find the requested model
        model_data = next((m for m in models if m["id"] == model_id), None)

        if not model_data:
            raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")

        return Model(**model_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get model: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """
    Health check endpoint.

    Returns status of the API gateway and connected services.
    """
    try:
        orchestrator = get_orchestrator()

        # Check Ollama connectivity
        ollama_healthy = False
        try:
            models = await orchestrator.list_models()
            ollama_healthy = len(models) > 0
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")

        return {
            "status": "healthy",
            "timestamp": int(time.time()),
            "services": {
                "api_gateway": "healthy",
                "orchestrator": "healthy",
                "ollama": "healthy" if ollama_healthy else "degraded",
            },
            "tawiza_agents": list(orchestrator.tawiza_agents.keys()),
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": int(time.time()),
                "error": str(e),
            },
        )


@router.options("/chat/completions")
async def chat_completions_options():
    """CORS preflight for chat completions."""
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        },
    )


@router.options("/models")
async def models_options():
    """CORS preflight for models."""
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        },
    )


@router.options("/embeddings")
async def embeddings_options():
    """CORS preflight for embeddings."""
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        },
    )
