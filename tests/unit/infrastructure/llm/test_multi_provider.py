"""Tests for Multi-Provider LLM.

Tests the multi-provider LLM with failover capabilities.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.llm.multi_provider import (
    AnthropicLLMClient,
    CAMELModelBackend,
    ChatMessage,
    LLMResponse,
    MultiProviderLLM,
    OllamaLLMClient,
    OpenAILLMClient,
    ProviderConfig,
    ProviderType,
    create_default_multi_provider,
)


class TestProviderConfig:
    """Tests for ProviderConfig dataclass."""

    def test_default_values(self):
        """Should have sensible defaults."""
        config = ProviderConfig(
            provider_type=ProviderType.OLLAMA,
            model="qwen3-coder:30b",
        )

        assert config.temperature == 0.7
        assert config.max_tokens == 4096
        assert config.timeout == 120
        assert config.priority == 1

    def test_custom_values(self):
        """Should accept custom values."""
        config = ProviderConfig(
            provider_type=ProviderType.OPENAI,
            model="gpt-4-turbo",
            api_key="sk-test",
            base_url="https://custom.openai.com",
            temperature=0.5,
            max_tokens=2048,
            priority=2,
        )

        assert config.provider_type == ProviderType.OPENAI
        assert config.model == "gpt-4-turbo"
        assert config.api_key == "sk-test"
        assert config.priority == 2


class TestChatMessage:
    """Tests for ChatMessage dataclass."""

    def test_user_message(self):
        """Should create user message."""
        msg = ChatMessage(role="user", content="Hello!")
        assert msg.role == "user"
        assert msg.content == "Hello!"

    def test_assistant_message(self):
        """Should create assistant message."""
        msg = ChatMessage(role="assistant", content="Hi there!")
        assert msg.role == "assistant"


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_basic_response(self):
        """Should create basic response."""
        response = LLMResponse(
            content="Hello!",
            provider=ProviderType.OLLAMA,
            model="qwen3-coder:30b",
        )

        assert response.content == "Hello!"
        assert response.provider == ProviderType.OLLAMA
        assert response.usage == {}
        assert response.tool_calls == []

    def test_response_with_tools(self):
        """Should include tool calls."""
        response = LLMResponse(
            content="",
            provider=ProviderType.OPENAI,
            model="gpt-4",
            tool_calls=[{"id": "call_1", "function": {"name": "search"}}],
        )

        assert len(response.tool_calls) == 1


class TestOllamaLLMClient:
    """Tests for OllamaLLMClient."""

    def test_init(self):
        """Should initialize with config."""
        config = ProviderConfig(
            provider_type=ProviderType.OLLAMA,
            model="qwen3-coder:30b",
        )
        client = OllamaLLMClient(config)

        assert client.base_url == "http://localhost:11434"
        assert client.config.model == "qwen3-coder:30b"

    def test_custom_base_url(self):
        """Should use custom base URL."""
        config = ProviderConfig(
            provider_type=ProviderType.OLLAMA,
            model="test",
            base_url="http://localhost:11434",
        )
        client = OllamaLLMClient(config)

        assert client.base_url == "http://localhost:11434"

    @pytest.mark.asyncio
    async def test_generate_success(self):
        """Should generate response."""
        config = ProviderConfig(
            provider_type=ProviderType.OLLAMA,
            model="test-model",
        )
        client = OllamaLLMClient(config)

        # Mock the HTTP client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {"content": "Test response", "role": "assistant"},
            "prompt_eval_count": 10,
            "eval_count": 20,
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            messages = [ChatMessage(role="user", content="Hello")]
            response = await client.generate(messages)

            assert response.content == "Test response"
            assert response.provider == ProviderType.OLLAMA

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Should return True when healthy."""
        config = ProviderConfig(
            provider_type=ProviderType.OLLAMA,
            model="test",
        )
        client = OllamaLLMClient(config)

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await client.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Should return False when unhealthy."""
        config = ProviderConfig(
            provider_type=ProviderType.OLLAMA,
            model="test",
        )
        client = OllamaLLMClient(config)

        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Connection failed")
            result = await client.health_check()
            assert result is False


class TestOpenAILLMClient:
    """Tests for OpenAILLMClient."""

    def test_init_default_url(self):
        """Should use default OpenAI URL."""
        config = ProviderConfig(
            provider_type=ProviderType.OPENAI,
            model="gpt-4",
            api_key="sk-test",
        )
        client = OpenAILLMClient(config)

        assert client.base_url == "https://api.openai.com/v1"

    @pytest.mark.asyncio
    async def test_generate_success(self):
        """Should generate response from OpenAI."""
        config = ProviderConfig(
            provider_type=ProviderType.OPENAI,
            model="gpt-4",
            api_key="sk-test",
        )
        client = OpenAILLMClient(config)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "OpenAI response", "role": "assistant"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            messages = [ChatMessage(role="user", content="Hello")]
            response = await client.generate(messages)

            assert response.content == "OpenAI response"
            assert response.provider == ProviderType.OPENAI


class TestAnthropicLLMClient:
    """Tests for AnthropicLLMClient."""

    def test_init_default_url(self):
        """Should use default Anthropic URL."""
        config = ProviderConfig(
            provider_type=ProviderType.ANTHROPIC,
            model="claude-3-5-sonnet",
            api_key="sk-ant-test",
        )
        client = AnthropicLLMClient(config)

        assert client.base_url == "https://api.anthropic.com"

    @pytest.mark.asyncio
    async def test_generate_success(self):
        """Should generate response from Anthropic."""
        config = ProviderConfig(
            provider_type=ProviderType.ANTHROPIC,
            model="claude-3-5-sonnet",
            api_key="sk-ant-test",
        )
        client = AnthropicLLMClient(config)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "Claude response"}],
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            messages = [ChatMessage(role="user", content="Hello")]
            response = await client.generate(messages)

            assert response.content == "Claude response"
            assert response.provider == ProviderType.ANTHROPIC

    def test_convert_tools(self):
        """Should convert OpenAI tools to Anthropic format."""
        config = ProviderConfig(
            provider_type=ProviderType.ANTHROPIC,
            model="claude-3-5-sonnet",
            api_key="test-key",
        )
        client = AnthropicLLMClient(config)

        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": "search",
                    "description": "Search the web",
                    "parameters": {"type": "object", "properties": {"query": {"type": "string"}}},
                },
            }
        ]

        anthropic_tools = client._convert_tools(openai_tools)

        assert len(anthropic_tools) == 1
        assert anthropic_tools[0]["name"] == "search"
        assert anthropic_tools[0]["description"] == "Search the web"


class TestMultiProviderLLM:
    """Tests for MultiProviderLLM."""

    def test_init_empty(self):
        """Should initialize with no providers."""
        llm = MultiProviderLLM()
        assert len(llm.providers) == 0
        assert len(llm.configs) == 0

    def test_add_provider(self):
        """Should add provider to list."""
        llm = MultiProviderLLM()

        config = ProviderConfig(
            provider_type=ProviderType.OLLAMA,
            model="test",
        )
        llm.add_provider(config)

        assert ProviderType.OLLAMA in llm.providers
        assert len(llm.configs) == 1

    def test_providers_sorted_by_priority(self):
        """Should sort providers by priority."""
        llm = MultiProviderLLM()

        # Add in reverse priority order
        llm.add_provider(
            ProviderConfig(
                provider_type=ProviderType.OPENAI,
                model="gpt-4",
                api_key="test",
                priority=2,
            )
        )
        llm.add_provider(
            ProviderConfig(
                provider_type=ProviderType.OLLAMA,
                model="qwen",
                priority=1,
            )
        )

        assert llm.configs[0].provider_type == ProviderType.OLLAMA
        assert llm.configs[1].provider_type == ProviderType.OPENAI

    @pytest.mark.asyncio
    async def test_generate_uses_first_provider(self):
        """Should use first available provider."""
        llm = MultiProviderLLM()

        config = ProviderConfig(
            provider_type=ProviderType.OLLAMA,
            model="test",
            priority=1,
        )
        llm.add_provider(config)

        # Mock the provider
        mock_response = LLMResponse(
            content="Test response",
            provider=ProviderType.OLLAMA,
            model="test",
        )
        llm.providers[ProviderType.OLLAMA].generate = AsyncMock(return_value=mock_response)

        messages = [ChatMessage(role="user", content="Hello")]
        response = await llm.generate(messages)

        assert response.content == "Test response"

    @pytest.mark.asyncio
    async def test_generate_failover(self):
        """Should failover to next provider on error."""
        llm = MultiProviderLLM()

        # Add two providers
        llm.add_provider(
            ProviderConfig(
                provider_type=ProviderType.OLLAMA,
                model="primary",
                priority=1,
            )
        )
        llm.add_provider(
            ProviderConfig(
                provider_type=ProviderType.OPENAI,
                model="fallback",
                api_key="test",
                priority=2,
            )
        )

        # First provider fails
        llm.providers[ProviderType.OLLAMA].generate = AsyncMock(
            side_effect=Exception("Primary failed")
        )

        # Second provider succeeds
        mock_response = LLMResponse(
            content="Fallback response",
            provider=ProviderType.OPENAI,
            model="fallback",
        )
        llm.providers[ProviderType.OPENAI].generate = AsyncMock(return_value=mock_response)

        messages = [ChatMessage(role="user", content="Hello")]
        response = await llm.generate(messages)

        assert response.content == "Fallback response"
        assert response.provider == ProviderType.OPENAI

    @pytest.mark.asyncio
    async def test_generate_all_fail(self):
        """Should raise error when all providers fail."""
        llm = MultiProviderLLM()

        llm.add_provider(
            ProviderConfig(
                provider_type=ProviderType.OLLAMA,
                model="test",
            )
        )

        llm.providers[ProviderType.OLLAMA].generate = AsyncMock(side_effect=Exception("Failed"))

        messages = [ChatMessage(role="user", content="Hello")]

        with pytest.raises(RuntimeError) as exc_info:
            await llm.generate(messages)

        assert "All LLM providers failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_preferred_provider(self):
        """Should try preferred provider first."""
        llm = MultiProviderLLM()

        llm.add_provider(
            ProviderConfig(
                provider_type=ProviderType.OLLAMA,
                model="primary",
                priority=1,
            )
        )
        llm.add_provider(
            ProviderConfig(
                provider_type=ProviderType.OPENAI,
                model="secondary",
                api_key="test",
                priority=2,
            )
        )

        # Both succeed but we prefer OpenAI
        mock_ollama = LLMResponse(content="Ollama", provider=ProviderType.OLLAMA, model="primary")
        mock_openai = LLMResponse(content="OpenAI", provider=ProviderType.OPENAI, model="secondary")

        llm.providers[ProviderType.OLLAMA].generate = AsyncMock(return_value=mock_ollama)
        llm.providers[ProviderType.OPENAI].generate = AsyncMock(return_value=mock_openai)

        messages = [ChatMessage(role="user", content="Hello")]
        response = await llm.generate(messages, preferred_provider=ProviderType.OPENAI)

        assert response.provider == ProviderType.OPENAI

    @pytest.mark.asyncio
    async def test_health_check_all(self):
        """Should check health of all providers."""
        llm = MultiProviderLLM()

        llm.add_provider(
            ProviderConfig(
                provider_type=ProviderType.OLLAMA,
                model="test",
            )
        )

        llm.providers[ProviderType.OLLAMA].health_check = AsyncMock(return_value=True)

        results = await llm.health_check()

        assert results["ollama"] is True


class TestCAMELModelBackend:
    """Tests for CAMELModelBackend."""

    @pytest.mark.asyncio
    async def test_run_interface(self):
        """Should provide CAMEL-compatible run interface."""
        mock_llm = MagicMock(spec=MultiProviderLLM)
        mock_response = LLMResponse(
            content="Response",
            provider=ProviderType.OLLAMA,
            model="test",
        )
        mock_llm.generate = AsyncMock(return_value=mock_response)

        backend = CAMELModelBackend(multi_provider=mock_llm)

        messages = [{"role": "user", "content": "Hello"}]
        result = await backend.run(messages)

        assert result["content"] == "Response"
        assert result["role"] == "assistant"
        assert result["provider"] == "ollama"

    @pytest.mark.asyncio
    async def test_run_with_tools(self):
        """Should pass tools to LLM."""
        mock_llm = MagicMock(spec=MultiProviderLLM)
        mock_response = LLMResponse(
            content="",
            provider=ProviderType.OLLAMA,
            model="test",
            tool_calls=[{"id": "1", "function": {"name": "search"}}],
        )
        mock_llm.generate = AsyncMock(return_value=mock_response)

        backend = CAMELModelBackend(multi_provider=mock_llm)

        tools = [{"type": "function", "function": {"name": "search"}}]
        result = await backend.run(
            [{"role": "user", "content": "Search for X"}],
            tools=tools,
        )

        assert len(result["tool_calls"]) == 1

    @pytest.mark.asyncio
    async def test_preferred_provider(self):
        """Should use preferred provider."""
        mock_llm = MagicMock(spec=MultiProviderLLM)
        mock_response = LLMResponse(
            content="Response",
            provider=ProviderType.OPENAI,
            model="gpt-4",
        )
        mock_llm.generate = AsyncMock(return_value=mock_response)

        backend = CAMELModelBackend(
            multi_provider=mock_llm,
            preferred_provider=ProviderType.OPENAI,
        )

        await backend.run([{"role": "user", "content": "Hello"}])

        # Verify preferred_provider was passed
        call_args = mock_llm.generate.call_args
        assert call_args.kwargs["preferred_provider"] == ProviderType.OPENAI


class TestCreateDefaultMultiProvider:
    """Tests for create_default_multi_provider factory."""

    @patch.dict("os.environ", {}, clear=True)
    def test_creates_ollama_only(self):
        """Should create Ollama provider when no API keys."""
        llm = create_default_multi_provider()

        assert ProviderType.OLLAMA in llm.providers
        assert ProviderType.OPENAI not in llm.providers
        assert ProviderType.ANTHROPIC not in llm.providers

    @patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"})
    def test_adds_openai_with_key(self):
        """Should add OpenAI when API key present."""
        llm = create_default_multi_provider()

        assert ProviderType.OLLAMA in llm.providers
        assert ProviderType.OPENAI in llm.providers

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-test"})
    def test_adds_anthropic_with_key(self):
        """Should add Anthropic when API key present."""
        llm = create_default_multi_provider()

        assert ProviderType.OLLAMA in llm.providers
        assert ProviderType.ANTHROPIC in llm.providers
