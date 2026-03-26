"""Ollama model management endpoints."""

import os
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/ollama", tags=["Ollama"])

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")


class OllamaModel(BaseModel):
    """Ollama model information."""

    name: str
    size: int  # bytes
    size_gb: float
    modified_at: str
    digest: str | None = None
    details: dict[str, Any] | None = None


class ModelListResponse(BaseModel):
    """Response for model list."""

    models: list[OllamaModel]
    default_model: str | None
    total: int


class PullModelRequest(BaseModel):
    """Request to pull a model."""

    name: str


class SetDefaultRequest(BaseModel):
    """Request to set default model."""

    name: str


# In-memory default model (could be persisted to file/db)
_default_model: str | None = None


def _get_default_model() -> str | None:
    """Get the default model from env or memory."""
    global _default_model
    if _default_model:
        return _default_model
    return os.getenv("OLLAMA_MODEL", "mistral-nemo:12b-instruct-2407-q8_0")


def _set_default_model(model: str) -> None:
    """Set the default model in memory."""
    global _default_model
    _default_model = model


@router.get("/models", response_model=ModelListResponse)
async def list_models() -> ModelListResponse:
    """List all available Ollama models."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            resp.raise_for_status()
            data = resp.json()

        models = []
        for m in data.get("models", []):
            size_bytes = m.get("size", 0)
            models.append(
                OllamaModel(
                    name=m["name"],
                    size=size_bytes,
                    size_gb=round(size_bytes / (1024**3), 2),
                    modified_at=m.get("modified_at", ""),
                    digest=m.get("digest"),
                    details=m.get("details"),
                )
            )

        # Sort by size (largest first)
        models.sort(key=lambda x: x.size, reverse=True)

        return ModelListResponse(
            models=models,
            default_model=_get_default_model(),
            total=len(models),
        )

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Ollama connection timeout")
    except httpx.HTTPError as e:
        logger.error(f"Ollama HTTP error listing models: {e}")
        raise HTTPException(status_code=502, detail="Ollama connection error")
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/models/running")
async def get_running_model() -> dict[str, Any]:
    """Get currently running/loaded model."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/ps")
            resp.raise_for_status()
            data = resp.json()

        models = data.get("models", [])
        if models:
            return {
                "running": True,
                "model": models[0].get("name"),
                "size": models[0].get("size"),
                "expires_at": models[0].get("expires_at"),
            }
        return {"running": False, "model": None}

    except Exception as e:
        logger.error(f"Failed to get running model: {e}")
        return {"running": False, "model": None, "error": "Erreur interne du serveur"}


@router.get("/models/default")
async def get_default_model() -> dict[str, str | None]:
    """Get the default model configuration."""
    return {"default_model": _get_default_model()}


@router.put("/models/default")
async def set_default_model(request: SetDefaultRequest) -> dict[str, Any]:
    """Set the default model for TAJINE."""
    # Verify model exists
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            resp.raise_for_status()
            data = resp.json()

        available = [m["name"] for m in data.get("models", [])]
        if request.name not in available:
            raise HTTPException(
                status_code=404,
                detail=f"Model '{request.name}' not found. Available: {available[:5]}",
            )

        _set_default_model(request.name)
        logger.info(f"Default model set to: {request.name}")

        return {
            "success": True,
            "default_model": request.name,
            "message": f"Default model changed to {request.name}",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set default model: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/models/pull")
async def pull_model(request: PullModelRequest) -> dict[str, Any]:
    """Pull/download a model from Ollama registry."""
    try:
        logger.info(f"Pulling model: {request.name}")

        async with httpx.AsyncClient(timeout=600.0) as client:  # 10 min timeout for large models
            resp = await client.post(
                f"{OLLAMA_URL}/api/pull",
                json={"name": request.name, "stream": False},
            )
            resp.raise_for_status()
            data = resp.json()

        return {
            "success": True,
            "model": request.name,
            "status": data.get("status", "success"),
        }

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Model pull timeout - try pulling directly with 'ollama pull'",
        )
    except httpx.HTTPError as e:
        logger.error(f"Ollama HTTP error pulling model: {e}")
        raise HTTPException(status_code=502, detail="Ollama connection error")
    except Exception as e:
        logger.error(f"Failed to pull model: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/models/{model_name}")
async def delete_model(model_name: str) -> dict[str, Any]:
    """Delete a model from Ollama."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(
                f"{OLLAMA_URL}/api/delete",
                json={"name": model_name},
            )
            resp.raise_for_status()

        logger.info(f"Deleted model: {model_name}")
        return {"success": True, "deleted": model_name}

    except httpx.HTTPError as e:
        logger.error(f"Ollama HTTP error deleting model: {e}")
        raise HTTPException(status_code=502, detail="Ollama connection error")
    except Exception as e:
        logger.error(f"Failed to delete model: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/models/{model_name}/load")
async def load_model(model_name: str) -> dict[str, Any]:
    """Pre-load a model into memory."""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Send a simple generate request to load the model
            resp = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": model_name,
                    "prompt": "Hello",
                    "stream": False,
                    "options": {"num_predict": 1},
                },
            )
            resp.raise_for_status()

        logger.info(f"Loaded model into memory: {model_name}")
        return {"success": True, "loaded": model_name}

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Model load timeout")
    except httpx.HTTPError as e:
        logger.error(f"Ollama HTTP error loading model: {e}")
        raise HTTPException(status_code=502, detail="Ollama connection error")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/status")
async def get_ollama_status() -> dict[str, Any]:
    """Get Ollama server status and GPU info."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Check server is responding
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            resp.raise_for_status()
            tags_data = resp.json()

            # Get running models
            ps_resp = await client.get(f"{OLLAMA_URL}/api/ps")
            ps_data = ps_resp.json() if ps_resp.status_code == 200 else {}

        return {
            "status": "connected",
            "url": OLLAMA_URL,
            "models_count": len(tags_data.get("models", [])),
            "running_models": ps_data.get("models", []),
            "default_model": _get_default_model(),
        }

    except Exception as e:
        return {
            "status": "disconnected",
            "url": OLLAMA_URL,
            "error": "Erreur interne du serveur",
        }
