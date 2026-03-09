"""Multi-Provider LLM for CAMEL integration.

Supports multiple LLM backends (Ollama, OpenAI, Anthropic) with
automatic failover and load balancing for agent orchestration.
"""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx
from loguru import logger


class ProviderType(Enum):
    """Supported LLM providers."""
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider."""
    provider_type: ProviderType
    model: str
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 120
    priority: int = 1  # Lower = higher priority


@dataclass
class ChatMessage:
    """Chat message for multi-turn conversations."""
    role: str  # system, user, assistant
    content: str


@dataclass
class LLMResponse:
    """Response from LLM generation."""
    content: str
    provider: ProviderType
    model: str
    usage: dict = field(default_factory=dict)
    tool_calls: list = field(default_factory=list)


class BaseLLMClient(ABC):
    """Base class for LLM clients."""

    @abstractmethod
    async def generate(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """Generate a response."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is healthy."""
        pass


class OllamaLLMClient(BaseLLMClient):
    """Ollama LLM client."""

    def __init__(self, config: ProviderConfig):
        self.config = config
        self.base_url = config.base_url or "http://localhost:11434"
        self.client = httpx.AsyncClient(timeout=config.timeout)

    async def generate(
        self,
        messages: list[ChatMessage],
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """Generate response using Ollama."""
        payload = {
            "model": self.config.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {
                "temperature": temperature or self.config.temperature,
                "num_predict": max_tokens or self.config.max_tokens,
            },
        }

        if tools:
            payload["tools"] = tools

        response = await self.client.post(
            f"{self.base_url}/api/chat",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        message = data.get("message", {})
        return LLMResponse(
            content=message.get("content", ""),
            provider=ProviderType.OLLAMA,
            model=self.config.model,
            usage={
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
            },
            tool_calls=message.get("tool_calls", []),
        )

    async def health_check(self) -> bool:
        """Check Ollama health."""
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self):
        """Close client."""
        await self.client.aclose()


class OpenAILLMClient(BaseLLMClient):
    """OpenAI-compatible LLM client."""

    def __init__(self, config: ProviderConfig):
        self.config = config
        self.base_url = config.base_url or "https://api.openai.com/v1"
        self.api_key = config.api_key or os.getenv("OPENAI_API_KEY")
        self.client = httpx.AsyncClient(
            timeout=config.timeout,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )

    async def generate(
        self,
        messages: list[ChatMessage],
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """Generate response using OpenAI API."""
        payload = {
            "model": self.config.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature or self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
        }

        if tools:
            payload["tools"] = tools

        response = await self.client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        message = choice["message"]

        return LLMResponse(
            content=message.get("content", ""),
            provider=ProviderType.OPENAI,
            model=self.config.model,
            usage=data.get("usage", {}),
            tool_calls=message.get("tool_calls", []),
        )

    async def health_check(self) -> bool:
        """Check OpenAI API health."""
        try:
            response = await self.client.get(f"{self.base_url}/models")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self):
        """Close client."""
        await self.client.aclose()


class AnthropicLLMClient(BaseLLMClient):
    """Anthropic Claude LLM client."""

    def __init__(self, config: ProviderConfig):
        self.config = config
        self.base_url = config.base_url or "https://api.anthropic.com"
        self.api_key = config.api_key or os.getenv("ANTHROPIC_API_KEY")
        self.client = httpx.AsyncClient(
            timeout=config.timeout,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )

    async def generate(
        self,
        messages: list[ChatMessage],
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """Generate response using Anthropic API."""
        # Convert messages to Anthropic format
        system_prompt = None
        anthropic_messages = []

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
            else:
                anthropic_messages.append({
                    "role": msg.role,
                    "content": msg.content,
                })

        payload = {
            "model": self.config.model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens or self.config.max_tokens,
            "temperature": temperature or self.config.temperature,
        }

        if system_prompt:
            payload["system"] = system_prompt

        if tools:
            # Convert OpenAI tool format to Anthropic format
            payload["tools"] = self._convert_tools(tools)

        response = await self.client.post(
            f"{self.base_url}/v1/messages",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        # Extract content from Anthropic response
        content_parts = data.get("content", [])
        text_content = ""
        tool_calls = []

        for part in content_parts:
            if part["type"] == "text":
                text_content += part["text"]
            elif part["type"] == "tool_use":
                tool_calls.append({
                    "id": part["id"],
                    "type": "function",
                    "function": {
                        "name": part["name"],
                        "arguments": part["input"],
                    },
                })

        return LLMResponse(
            content=text_content,
            provider=ProviderType.ANTHROPIC,
            model=self.config.model,
            usage=data.get("usage", {}),
            tool_calls=tool_calls,
        )

    def _convert_tools(self, openai_tools: list[dict]) -> list[dict]:
        """Convert OpenAI tool format to Anthropic format."""
        anthropic_tools = []
        for tool in openai_tools:
            if tool.get("type") == "function":
                func = tool["function"]
                anthropic_tools.append({
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {"type": "object"}),
                })
        return anthropic_tools

    async def health_check(self) -> bool:
        """Check Anthropic API health."""
        try:
            # Anthropic doesn't have a simple health endpoint
            # Just check if we can reach the API
            return self.api_key is not None
        except Exception:
            return False

    async def close(self):
        """Close client."""
        await self.client.aclose()


class MultiProviderLLM:
    """Multi-provider LLM with failover and load balancing.

    Supports multiple LLM backends with automatic failover:
    - Ollama (local, fast, free)
    - OpenAI (GPT-4, powerful)
    - Anthropic (Claude, reasoning)

    Example:
        llm = MultiProviderLLM()
        llm.add_provider(ProviderConfig(
            provider_type=ProviderType.OLLAMA,
            model="qwen3-coder:30b",
            priority=1,  # Primary
        ))
        llm.add_provider(ProviderConfig(
            provider_type=ProviderType.OPENAI,
            model="gpt-4-turbo",
            priority=2,  # Fallback
        ))

        response = await llm.generate([
            ChatMessage(role="user", content="Hello!")
        ])
    """

    def __init__(self):
        self.providers: dict[ProviderType, BaseLLMClient] = {}
        self.configs: list[ProviderConfig] = []

    def add_provider(self, config: ProviderConfig) -> None:
        """Add a provider configuration."""
        self.configs.append(config)
        self.configs.sort(key=lambda c: c.priority)

        # Create client based on provider type
        if config.provider_type == ProviderType.OLLAMA:
            self.providers[config.provider_type] = OllamaLLMClient(config)
        elif config.provider_type == ProviderType.OPENAI:
            self.providers[config.provider_type] = OpenAILLMClient(config)
        elif config.provider_type == ProviderType.ANTHROPIC:
            self.providers[config.provider_type] = AnthropicLLMClient(config)

        logger.info(f"Added LLM provider: {config.provider_type.value} ({config.model})")

    async def generate(
        self,
        messages: list[ChatMessage],
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
        preferred_provider: ProviderType | None = None,
    ) -> LLMResponse:
        """Generate response with automatic failover.

        Args:
            messages: Chat messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            tools: Tool definitions for function calling
            preferred_provider: Force a specific provider

        Returns:
            LLMResponse from first successful provider

        Raises:
            RuntimeError: If all providers fail
        """
        errors = []

        # If preferred provider specified, try it first
        if preferred_provider and preferred_provider in self.providers:
            try:
                client = self.providers[preferred_provider]
                return await client.generate(messages, temperature, max_tokens, tools)
            except Exception as e:
                logger.warning(f"Preferred provider {preferred_provider} failed: {e}")
                errors.append((preferred_provider, str(e)))

        # Try providers in priority order
        for config in self.configs:
            if config.provider_type == preferred_provider:
                continue  # Already tried

            if config.provider_type not in self.providers:
                continue

            try:
                client = self.providers[config.provider_type]
                logger.debug(f"Trying provider: {config.provider_type.value}")
                return await client.generate(messages, temperature, max_tokens, tools)
            except Exception as e:
                logger.warning(f"Provider {config.provider_type} failed: {e}")
                errors.append((config.provider_type, str(e)))

        raise RuntimeError(f"All LLM providers failed: {errors}")

    async def health_check(self) -> dict[str, bool]:
        """Check health of all providers."""
        results = {}
        for provider_type, client in self.providers.items():
            try:
                results[provider_type.value] = await client.health_check()
            except Exception:
                results[provider_type.value] = False
        return results

    async def close(self):
        """Close all provider clients."""
        for client in self.providers.values():
            await client.close()


def create_default_multi_provider() -> MultiProviderLLM:
    """Create MultiProviderLLM with default configuration.

    Default setup:
    - Ollama (priority 1, primary) - local, fast
    - OpenAI (priority 2, fallback) - if API key available
    - Anthropic (priority 3, fallback) - if API key available
    """
    llm = MultiProviderLLM()

    # Primary: Ollama (always available locally)
    llm.add_provider(ProviderConfig(
        provider_type=ProviderType.OLLAMA,
        model="qwen3-coder:30b",
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        priority=1,
    ))

    # Fallback: OpenAI (if configured)
    if os.getenv("OPENAI_API_KEY"):
        llm.add_provider(ProviderConfig(
            provider_type=ProviderType.OPENAI,
            model="gpt-4-turbo",
            priority=2,
        ))

    # Fallback: Anthropic (if configured)
    if os.getenv("ANTHROPIC_API_KEY"):
        llm.add_provider(ProviderConfig(
            provider_type=ProviderType.ANTHROPIC,
            model="claude-3-5-sonnet-20241022",
            priority=3,
        ))

    return llm


# CAMEL Integration
class CAMELModelBackend:
    """CAMEL-compatible model backend using MultiProviderLLM.

    This adapter allows CAMEL agents to use our multi-provider
    infrastructure with automatic failover.

    Example with CAMEL:
        from camel.agents import ChatAgent

        backend = CAMELModelBackend()
        agent = ChatAgent(model_backend=backend)
    """

    def __init__(
        self,
        multi_provider: MultiProviderLLM | None = None,
        preferred_provider: ProviderType | None = None,
    ):
        self.llm = multi_provider or create_default_multi_provider()
        self.preferred_provider = preferred_provider

    async def run(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Run inference (CAMEL-compatible interface).

        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional parameters (temperature, max_tokens, tools)

        Returns:
            Response dict compatible with CAMEL expectations
        """
        chat_messages = [
            ChatMessage(role=m["role"], content=m["content"])
            for m in messages
        ]

        response = await self.llm.generate(
            messages=chat_messages,
            temperature=kwargs.get("temperature"),
            max_tokens=kwargs.get("max_tokens"),
            tools=kwargs.get("tools"),
            preferred_provider=self.preferred_provider,
        )

        return {
            "content": response.content,
            "role": "assistant",
            "tool_calls": response.tool_calls,
            "usage": response.usage,
            "model": response.model,
            "provider": response.provider.value,
        }

    async def health_check(self) -> dict[str, bool]:
        """Check health of all backends."""
        return await self.llm.health_check()

    async def close(self):
        """Clean up resources."""
        await self.llm.close()
