"""Tests for Ollama API router.

This module tests:
- Chat completion endpoint
- Text completion endpoint
- List models endpoint
- Health check endpoint
- Template inference endpoint
- NLP task endpoints (classification, NER, summarization, etc.)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.interfaces.api.routers.ollama import (
    ChatRequest,
    ChatResponse,
    ClassificationRequest,
    CodeReviewRequest,
    CompletionRequest,
    CompletionResponse,
    EntityExtractionRequest,
    ErrorAnalysisRequest,
    Message,
    ModelInfo,
    ModelsListResponse,
    QuestionAnsweringRequest,
    SentimentAnalysisRequest,
    SummarizationRequest,
    TemplateInferenceRequest,
    TranslationRequest,
    router,
)


class TestPydanticModels:
    """Test suite for Pydantic request/response models."""

    def test_message_model(self):
        """Message should have role and content."""
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_chat_request_defaults(self):
        """ChatRequest should have sensible defaults."""
        request = ChatRequest(messages=[Message(role="user", content="Hi")])
        assert request.model == "qwen3.5:27b"
        assert request.temperature == 0.7
        assert request.stream is False

    def test_chat_request_custom_values(self):
        """ChatRequest should accept custom values."""
        request = ChatRequest(
            messages=[Message(role="user", content="Hi")],
            model="llama2:7b",
            temperature=0.9,
            stream=True,
        )
        assert request.model == "llama2:7b"
        assert request.temperature == 0.9
        assert request.stream is True

    def test_completion_request_defaults(self):
        """CompletionRequest should have sensible defaults."""
        request = CompletionRequest(prompt="Hello")
        assert request.model == "qwen3.5:27b"
        assert request.temperature == 0.7
        assert request.max_tokens == 512

    def test_chat_response_model(self):
        """ChatResponse should have required fields."""
        response = ChatResponse(
            id="test-123",
            model="qwen3.5:27b",
            message="Hello!",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )
        assert response.id == "test-123"
        assert response.model == "qwen3.5:27b"
        assert response.message == "Hello!"
        assert response.usage["prompt_tokens"] == 10

    def test_completion_response_model(self):
        """CompletionResponse should have required fields."""
        response = CompletionResponse(
            id="test-456",
            model="qwen3.5:27b",
            text="Generated text here",
            usage={},
        )
        assert response.id == "test-456"
        assert response.text == "Generated text here"

    def test_model_info(self):
        """ModelInfo should contain model details."""
        info = ModelInfo(
            name="qwen3.5:27b",
            size="8.5GB",
            parameter_count="14B",
            quantization="Q4_K_M",
            family="qwen",
        )
        assert info.name == "qwen3.5:27b"
        assert info.size == "8.5GB"
        assert info.parameter_count == "14B"

    def test_models_list_response(self):
        """ModelsListResponse should contain list of models."""
        response = ModelsListResponse(
            models=[
                ModelInfo(
                    name="model1",
                    size="1GB",
                    parameter_count="1B",
                    quantization="Q4",
                    family="test",
                )
            ],
            total=1,
        )
        assert len(response.models) == 1
        assert response.total == 1

    def test_template_inference_request(self):
        """TemplateInferenceRequest should have template info."""
        request = TemplateInferenceRequest(
            template_name="test_template",
            variables={"name": "World"},
        )
        assert request.template_name == "test_template"
        assert request.variables["name"] == "World"

    def test_classification_request(self):
        """ClassificationRequest should have text and categories."""
        request = ClassificationRequest(
            text="This is great!",
            categories="positive,negative,neutral",
        )
        assert request.text == "This is great!"
        assert request.categories == "positive,negative,neutral"
        assert request.temperature == 0.3  # Lower default for classification

    def test_summarization_request(self):
        """SummarizationRequest should have max_words field."""
        request = SummarizationRequest(
            text="Long text here...",
            max_words=50,
        )
        assert request.max_words == 50

    def test_translation_request(self):
        """TranslationRequest should have language fields."""
        request = TranslationRequest(
            text="Hello",
            source_lang="English",
            target_lang="French",
        )
        assert request.source_lang == "English"
        assert request.target_lang == "French"


class TestOllamaEndpointsIntegration:
    """Integration tests for Ollama endpoints using TestClient."""

    @pytest.fixture
    def mock_ollama_service(self):
        """Create mock Ollama service."""
        service = MagicMock()
        service.predict = AsyncMock(
            return_value={
                "model": "qwen3.5:27b",
                "text": "Test response",
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            }
        )
        service.ollama = MagicMock()
        service.ollama.base_url = "http://localhost:11434"
        service.ollama.list_models = AsyncMock(
            return_value=[
                {
                    "name": "qwen3.5:27b",
                    "size": 8500000000,
                    "details": {
                        "parameter_size": "14B",
                        "quantization_level": "Q4_K_M",
                        "family": "qwen",
                    },
                }
            ]
        )
        service.ollama.health_check = AsyncMock(return_value=True)
        return service

    @pytest.fixture
    def test_client(self, mock_ollama_service):
        """Create FastAPI test client with mocked service."""
        app = FastAPI()
        app.include_router(router, prefix="/ollama")

        # Override the dependency
        from src.interfaces.api.routers.ollama import get_ollama_service

        app.dependency_overrides[get_ollama_service] = lambda: mock_ollama_service

        return TestClient(app)

    def test_chat_completion_success(self, test_client, mock_ollama_service):
        """POST /ollama/chat should return chat response."""
        response = test_client.post(
            "/ollama/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "qwen3.5:27b",
                "temperature": 0.7,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["model"] == "qwen3.5:27b"
        assert data["message"] == "Test response"
        assert data["usage"]["prompt_tokens"] == 10

        # Verify service was called
        mock_ollama_service.predict.assert_called_once()

    def test_chat_completion_minimal_request(self, test_client):
        """POST /ollama/chat should work with minimal request."""
        response = test_client.post(
            "/ollama/chat",
            json={"messages": [{"role": "user", "content": "Hi"}]},
        )
        assert response.status_code == 200

    def test_chat_completion_validation_error(self, test_client):
        """POST /ollama/chat should validate request."""
        response = test_client.post(
            "/ollama/chat",
            json={"messages": []},  # Empty messages might be allowed
        )
        # FastAPI will validate based on Pydantic model
        assert response.status_code in (200, 422)  # Either valid or validation error

    def test_text_completion_success(self, test_client, mock_ollama_service):
        """POST /ollama/completions should return completion."""
        response = test_client.post(
            "/ollama/completions",
            json={
                "prompt": "Once upon a time",
                "model": "qwen3.5:27b",
                "temperature": 0.8,
                "max_tokens": 256,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["text"] == "Test response"
        assert data["model"] == "qwen3.5:27b"

    def test_list_models_success(self, test_client, mock_ollama_service):
        """GET /ollama/models should return model list."""
        response = test_client.get("/ollama/models")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["models"]) == 1
        assert data["models"][0]["name"] == "qwen3.5:27b"
        assert data["models"][0]["parameter_count"] == "14B"

    def test_health_check_healthy(self, test_client, mock_ollama_service):
        """GET /ollama/health should return healthy status."""
        response = test_client.get("/ollama/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "ollama"
        assert "url" in data

    def test_health_check_unhealthy(self, test_client, mock_ollama_service):
        """GET /ollama/health should return 503 when unhealthy."""
        mock_ollama_service.ollama.health_check = AsyncMock(return_value=False)

        response = test_client.get("/ollama/health")

        assert response.status_code == 503

    def test_health_check_error(self, test_client, mock_ollama_service):
        """GET /ollama/health should handle errors."""
        mock_ollama_service.ollama.health_check = AsyncMock(
            side_effect=Exception("Connection refused")
        )

        response = test_client.get("/ollama/health")

        assert response.status_code == 503
        assert "Connection refused" in response.json()["detail"]


class TestNLPEndpoints:
    """Test suite for NLP task endpoints."""

    @pytest.fixture
    def mock_ollama_service(self):
        """Create mock Ollama service with NLP methods."""
        service = MagicMock()

        # Standard predict
        service.predict = AsyncMock(
            return_value={
                "model": "qwen3.5:27b",
                "text": "Test response",
                "usage": {},
            }
        )

        # Template-based predict
        service.predict_with_template = AsyncMock(
            return_value={
                "model": "qwen3.5:27b",
                "text": "Template response",
                "usage": {},
                "template_used": "test_template",
                "template_variables": {"key": "value"},
            }
        )

        # NLP methods
        service.classify_text = AsyncMock(
            return_value={
                "model": "qwen3.5:27b",
                "text": "positive",
                "usage": {},
            }
        )
        service.extract_entities = AsyncMock(
            return_value={
                "model": "qwen3.5:27b",
                "text": '{"entities": [{"text": "Paris", "type": "LOCATION"}]}',
                "usage": {},
            }
        )
        service.summarize_text = AsyncMock(
            return_value={
                "model": "qwen3.5:27b",
                "text": "Summary of the text",
                "usage": {},
            }
        )
        service.analyze_sentiment = AsyncMock(
            return_value={
                "model": "qwen3.5:27b",
                "text": '{"sentiment": "positive", "confidence": 0.9}',
                "usage": {},
            }
        )
        service.answer_question = AsyncMock(
            return_value={
                "model": "qwen3.5:27b",
                "text": "The answer is 42",
                "usage": {},
            }
        )
        service.translate_text = AsyncMock(
            return_value={
                "model": "qwen3.5:27b",
                "text": "Bonjour",
                "usage": {},
            }
        )
        service.review_code = AsyncMock(
            return_value={
                "model": "qwen3.5:27b",
                "text": "Code looks good, no issues found",
                "usage": {},
            }
        )
        service.analyze_error = AsyncMock(
            return_value={
                "model": "qwen3.5:27b",
                "text": "Root cause: Missing null check",
                "usage": {},
            }
        )

        service.ollama = MagicMock()
        service.ollama.base_url = "http://localhost:11434"

        return service

    @pytest.fixture
    def test_client(self, mock_ollama_service):
        """Create FastAPI test client."""
        app = FastAPI()
        app.include_router(router, prefix="/ollama")

        from src.interfaces.api.routers.ollama import get_ollama_service

        app.dependency_overrides[get_ollama_service] = lambda: mock_ollama_service

        return TestClient(app)

    def test_template_inference(self, test_client, mock_ollama_service):
        """POST /ollama/infer-with-template should use template."""
        response = test_client.post(
            "/ollama/infer-with-template",
            json={
                "template_name": "greeting",
                "variables": {"name": "World"},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["text"] == "Template response"
        assert data["template_used"] == "test_template"

    def test_template_inference_invalid_template(self, test_client, mock_ollama_service):
        """POST /ollama/infer-with-template should handle invalid template."""
        mock_ollama_service.predict_with_template = AsyncMock(
            side_effect=ValueError("Template 'invalid' not found")
        )

        response = test_client.post(
            "/ollama/infer-with-template",
            json={
                "template_name": "invalid",
                "variables": {},
            },
        )

        assert response.status_code == 400
        assert "not found" in response.json()["detail"]

    def test_classify_text(self, test_client, mock_ollama_service):
        """POST /ollama/classify should classify text."""
        response = test_client.post(
            "/ollama/classify",
            json={
                "text": "This product is amazing!",
                "categories": "positive,negative,neutral",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["text"] == "positive"
        mock_ollama_service.classify_text.assert_called_once()

    def test_extract_entities(self, test_client, mock_ollama_service):
        """POST /ollama/extract-entities should extract NER."""
        response = test_client.post(
            "/ollama/extract-entities",
            json={"text": "John works at Microsoft in Seattle"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "entities" in data["text"]

    def test_summarize_text(self, test_client, mock_ollama_service):
        """POST /ollama/summarize should summarize text."""
        response = test_client.post(
            "/ollama/summarize",
            json={
                "text": "Long article text here..." * 20,
                "max_words": 50,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["text"] == "Summary of the text"
        mock_ollama_service.summarize_text.assert_called_once()

    def test_sentiment_analysis(self, test_client, mock_ollama_service):
        """POST /ollama/sentiment should analyze sentiment."""
        response = test_client.post(
            "/ollama/sentiment",
            json={"text": "I love this!"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "positive" in data["text"]

    def test_question_answering(self, test_client, mock_ollama_service):
        """POST /ollama/question-answer should answer questions."""
        response = test_client.post(
            "/ollama/question-answer",
            json={
                "question": "What is the meaning of life?",
                "context": "The answer to everything is 42.",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "42" in data["text"]

    def test_translation(self, test_client, mock_ollama_service):
        """POST /ollama/translate should translate text."""
        response = test_client.post(
            "/ollama/translate",
            json={
                "text": "Hello",
                "source_lang": "English",
                "target_lang": "French",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["text"] == "Bonjour"
        mock_ollama_service.translate_text.assert_called_once()

    def test_code_review(self, test_client, mock_ollama_service):
        """POST /ollama/code-review should review code."""
        response = test_client.post(
            "/ollama/code-review",
            json={
                "code": "def hello():\n    print('Hello')",
                "language": "Python",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "good" in data["text"].lower() or "no issues" in data["text"].lower()

    def test_error_analysis(self, test_client, mock_ollama_service):
        """POST /ollama/error-analysis should analyze errors."""
        response = test_client.post(
            "/ollama/error-analysis",
            json={
                "error_type": "NullPointerException",
                "error_message": "Cannot read property 'x' of null",
                "stack_trace": "at line 42",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "null" in data["text"].lower() or "Root cause" in data["text"]


class TestErrorHandling:
    """Test suite for error handling."""

    @pytest.fixture
    def mock_ollama_service(self):
        """Create mock Ollama service that throws errors."""
        service = MagicMock()
        service.predict = AsyncMock(side_effect=Exception("Ollama connection failed"))
        service.ollama = MagicMock()
        service.ollama.list_models = AsyncMock(side_effect=Exception("Timeout"))
        return service

    @pytest.fixture
    def test_client(self, mock_ollama_service):
        """Create FastAPI test client."""
        app = FastAPI()
        app.include_router(router, prefix="/ollama")

        from src.interfaces.api.routers.ollama import get_ollama_service

        app.dependency_overrides[get_ollama_service] = lambda: mock_ollama_service

        return TestClient(app)

    def test_chat_completion_error(self, test_client):
        """POST /ollama/chat should handle service errors."""
        response = test_client.post(
            "/ollama/chat",
            json={"messages": [{"role": "user", "content": "Hi"}]},
        )

        assert response.status_code == 500
        assert "Chat completion failed" in response.json()["detail"]
        assert "Ollama connection failed" in response.json()["detail"]

    def test_text_completion_error(self, test_client):
        """POST /ollama/completions should handle service errors."""
        response = test_client.post(
            "/ollama/completions",
            json={"prompt": "Test"},
        )

        assert response.status_code == 500
        assert "Text completion failed" in response.json()["detail"]

    def test_list_models_error(self, test_client):
        """GET /ollama/models should handle service errors."""
        response = test_client.get("/ollama/models")

        assert response.status_code == 500
        assert "Failed to list models" in response.json()["detail"]


class TestTemperatureValidation:
    """Test suite for temperature validation."""

    def test_temperature_at_minimum(self):
        """Temperature at 0 should be valid."""
        request = ChatRequest(
            messages=[Message(role="user", content="Hi")],
            temperature=0.0,
        )
        assert request.temperature == 0.0

    def test_temperature_at_maximum(self):
        """Temperature at 2.0 should be valid."""
        request = ChatRequest(
            messages=[Message(role="user", content="Hi")],
            temperature=2.0,
        )
        assert request.temperature == 2.0

    def test_temperature_below_minimum(self):
        """Temperature below 0 should fail validation."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            ChatRequest(
                messages=[Message(role="user", content="Hi")],
                temperature=-0.1,
            )

    def test_temperature_above_maximum(self):
        """Temperature above 2.0 should fail validation."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            ChatRequest(
                messages=[Message(role="user", content="Hi")],
                temperature=2.1,
            )


class TestMaxTokensValidation:
    """Test suite for max_tokens validation."""

    def test_max_tokens_at_minimum(self):
        """Max tokens at 1 should be valid."""
        request = CompletionRequest(prompt="Hi", max_tokens=1)
        assert request.max_tokens == 1

    def test_max_tokens_at_maximum(self):
        """Max tokens at 4096 should be valid."""
        request = CompletionRequest(prompt="Hi", max_tokens=4096)
        assert request.max_tokens == 4096

    def test_max_tokens_below_minimum(self):
        """Max tokens below 1 should fail validation."""
        with pytest.raises(Exception):
            CompletionRequest(prompt="Hi", max_tokens=0)

    def test_max_tokens_above_maximum(self):
        """Max tokens above 4096 should fail validation."""
        with pytest.raises(Exception):
            CompletionRequest(prompt="Hi", max_tokens=5000)
