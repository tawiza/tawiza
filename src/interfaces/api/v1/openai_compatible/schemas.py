"""OpenAI-compatible API schemas for LobeChat integration."""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatRole(StrEnum):
    """Chat message roles (OpenAI-compatible)."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ChatMessage(BaseModel):
    """OpenAI-compatible chat message."""

    role: ChatRole = Field(..., description="Role of the message sender")
    content: str | list[dict[str, Any]] = Field(
        ..., description="Message content (text or multi-modal array)"
    )
    name: str | None = Field(None, description="Name of the sender")
    tool_calls: list[dict[str, Any]] | None = Field(
        None, description="Tool calls made by the assistant"
    )
    tool_call_id: str | None = Field(
        None, description="ID of the tool call this message is responding to"
    )

    model_config = ConfigDict(
        json_schema_extra={"example": {"role": "user", "content": "What is the capital of France?"}}
    )


class FunctionCall(BaseModel):
    """Function call definition."""

    name: str = Field(..., description="Function name")
    arguments: str = Field(..., description="Function arguments as JSON string")


class ToolCall(BaseModel):
    """Tool call definition."""

    id: str = Field(..., description="Unique identifier for the tool call")
    type: Literal["function"] = Field(default="function")
    function: FunctionCall


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request."""

    model: str = Field(..., description="Model to use (e.g., 'tawiza-analyst', 'qwen3-coder:30b')")
    messages: list[ChatMessage] = Field(..., description="List of messages in the conversation")
    temperature: float | None = Field(
        default=0.7, ge=0.0, le=2.0, description="Sampling temperature"
    )
    top_p: float | None = Field(
        default=1.0, ge=0.0, le=1.0, description="Nucleus sampling parameter"
    )
    n: int | None = Field(default=1, ge=1, description="Number of completions to generate")
    stream: bool | None = Field(default=False, description="Whether to stream responses")
    stop: str | list[str] | None = Field(None, description="Stop sequences")
    max_tokens: int | None = Field(None, gt=0, description="Maximum tokens to generate")
    presence_penalty: float | None = Field(
        default=0.0, ge=-2.0, le=2.0, description="Presence penalty"
    )
    frequency_penalty: float | None = Field(
        default=0.0, ge=-2.0, le=2.0, description="Frequency penalty"
    )
    logit_bias: dict[str, float] | None = Field(None, description="Token logit biases")
    user: str | None = Field(None, description="User identifier for tracking")
    tools: list[dict[str, Any]] | None = Field(None, description="Available tools/functions")
    tool_choice: str | dict[str, Any] | None = Field(None, description="Tool choice strategy")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "model": "tawiza-analyst",
                "messages": [
                    {"role": "user", "content": "Analyze the economic situation in Paris"}
                ],
                "temperature": 0.7,
                "stream": False,
            }
        }
    )


class ChatCompletionChoice(BaseModel):
    """Chat completion choice."""

    index: int = Field(..., description="Choice index")
    message: ChatMessage = Field(..., description="Generated message")
    finish_reason: str | None = Field(
        None, description="Reason for completion finish (stop, length, tool_calls, content_filter)"
    )
    logprobs: dict[str, Any] | None = Field(None, description="Log probabilities (if requested)")


class ChatCompletionUsage(BaseModel):
    """Token usage statistics."""

    prompt_tokens: int = Field(..., description="Tokens in the prompt")
    completion_tokens: int = Field(..., description="Tokens in the completion")
    total_tokens: int = Field(..., description="Total tokens used")


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response."""

    id: str = Field(..., description="Unique identifier for the completion")
    object: Literal["chat.completion"] = Field(default="chat.completion")
    created: int = Field(..., description="Unix timestamp of creation")
    model: str = Field(..., description="Model used")
    choices: list[ChatCompletionChoice] = Field(..., description="List of completion choices")
    usage: ChatCompletionUsage | None = Field(None, description="Token usage")
    system_fingerprint: str | None = Field(None, description="System fingerprint")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "chatcmpl-123",
                "object": "chat.completion",
                "created": 1677652288,
                "model": "tawiza-analyst",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Paris is the capital and largest city of France...",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 9, "completion_tokens": 12, "total_tokens": 21},
            }
        }
    )


class ChatCompletionChunk(BaseModel):
    """OpenAI-compatible streaming chunk."""

    id: str = Field(..., description="Unique identifier")
    object: Literal["chat.completion.chunk"] = Field(default="chat.completion.chunk")
    created: int = Field(..., description="Unix timestamp")
    model: str = Field(..., description="Model used")
    choices: list[dict[str, Any]] = Field(..., description="Streaming choices")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "chatcmpl-123",
                "object": "chat.completion.chunk",
                "created": 1677652288,
                "model": "tawiza-analyst",
                "choices": [{"index": 0, "delta": {"content": "Paris"}, "finish_reason": None}],
            }
        }
    )


class Model(BaseModel):
    """OpenAI-compatible model object."""

    id: str = Field(..., description="Model identifier")
    object: Literal["model"] = Field(default="model")
    created: int = Field(..., description="Unix timestamp of creation")
    owned_by: str = Field(..., description="Organization that owns the model")
    permission: list[dict[str, Any]] | None = Field(None)
    root: str | None = Field(None, description="Parent model")
    parent: str | None = Field(None, description="Parent model")


class ModelList(BaseModel):
    """OpenAI-compatible model list."""

    object: Literal["list"] = Field(default="list")
    data: list[Model] = Field(..., description="List of available models")


class EmbeddingRequest(BaseModel):
    """OpenAI-compatible embedding request."""

    model: str = Field(default="nomic-embed-text", description="Embedding model to use")
    input: str | list[str] = Field(..., description="Text(s) to embed")
    encoding_format: Literal["float", "base64"] | None = Field(
        default="float", description="Format for embeddings"
    )
    user: str | None = Field(None, description="User identifier")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "model": "nomic-embed-text",
                "input": "The quick brown fox jumps over the lazy dog",
            }
        }
    )


class Embedding(BaseModel):
    """Embedding object."""

    object: Literal["embedding"] = Field(default="embedding")
    embedding: list[float] = Field(..., description="Embedding vector")
    index: int = Field(..., description="Index in the input list")


class EmbeddingUsage(BaseModel):
    """Embedding usage statistics."""

    prompt_tokens: int = Field(..., description="Tokens in the prompt")
    total_tokens: int = Field(..., description="Total tokens")


class EmbeddingResponse(BaseModel):
    """OpenAI-compatible embedding response."""

    object: Literal["list"] = Field(default="list")
    data: list[Embedding] = Field(..., description="List of embeddings")
    model: str = Field(..., description="Model used")
    usage: EmbeddingUsage = Field(..., description="Token usage")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "object": "list",
                "data": [
                    {"object": "embedding", "embedding": [0.0023, -0.0091, 0.0042], "index": 0}
                ],
                "model": "nomic-embed-text",
                "usage": {"prompt_tokens": 8, "total_tokens": 8},
            }
        }
    )


class ErrorResponse(BaseModel):
    """OpenAI-compatible error response."""

    error: dict[str, Any] = Field(..., description="Error details")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": {
                    "message": "Invalid API key",
                    "type": "invalid_request_error",
                    "param": None,
                    "code": "invalid_api_key",
                }
            }
        }
    )
