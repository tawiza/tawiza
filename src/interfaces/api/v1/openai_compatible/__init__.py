"""OpenAI-compatible API endpoints for LobeChat integration."""

from src.interfaces.api.v1.openai_compatible.schemas import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ChatRole,
    EmbeddingRequest,
    EmbeddingResponse,
    ErrorResponse,
    Model,
    ModelList,
)

__all__ = [
    "ChatMessage",
    "ChatRole",
    "ChatCompletionRequest",
    "ChatCompletionResponse",
    "ChatCompletionChunk",
    "Model",
    "ModelList",
    "EmbeddingRequest",
    "EmbeddingResponse",
    "ErrorResponse",
]
