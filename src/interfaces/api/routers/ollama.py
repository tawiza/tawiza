"""Ollama API router for direct LLM inference."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from pydantic import BaseModel, Field

from src.infrastructure.config.settings import get_settings
from src.infrastructure.ml.ollama import OllamaAdapter, OllamaInferenceService

router = APIRouter()


# Pydantic models
class Message(BaseModel):
    """Chat message."""

    role: str = Field(..., description="Role: user or assistant")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Chat completion request."""

    messages: list[Message] = Field(..., description="Chat messages")
    model: str = Field("qwen3.5:27b", description="Ollama model name")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Sampling temperature")
    stream: bool = Field(False, description="Stream response")


class CompletionRequest(BaseModel):
    """Text completion request."""

    prompt: str = Field(..., description="Input prompt")
    model: str = Field("qwen3.5:27b", description="Ollama model name")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(512, ge=1, le=4096, description="Maximum tokens to generate")


class ChatResponse(BaseModel):
    """Chat completion response."""

    id: str
    model: str
    message: str
    usage: dict = {}


class CompletionResponse(BaseModel):
    """Completion response."""

    id: str
    model: str
    text: str
    usage: dict = {}


class ModelInfo(BaseModel):
    """Model information."""

    name: str
    size: str
    parameter_count: str
    quantization: str
    family: str


class ModelsListResponse(BaseModel):
    """List of available models."""

    models: list[ModelInfo]
    total: int


class TemplateInferenceRequest(BaseModel):
    """Template-based inference request."""

    template_name: str = Field(..., description="Name of the prompt template")
    variables: dict = Field(..., description="Variables to render the template with")
    model: str = Field("qwen3.5:27b", description="Ollama model name")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(512, ge=1, le=4096, description="Maximum tokens to generate")


class ClassificationRequest(BaseModel):
    """Text classification request."""

    text: str = Field(..., description="Text to classify")
    categories: str = Field(..., description="Comma-separated list of categories")
    model: str = Field("qwen3.5:27b", description="Ollama model name")
    temperature: float = Field(
        0.3, ge=0.0, le=2.0, description="Sampling temperature (lower for classification)"
    )


class EntityExtractionRequest(BaseModel):
    """Named entity extraction request."""

    text: str = Field(..., description="Text to analyze")
    model: str = Field("qwen3.5:27b", description="Ollama model name")
    temperature: float = Field(0.3, ge=0.0, le=2.0, description="Sampling temperature")


class SummarizationRequest(BaseModel):
    """Text summarization request."""

    text: str = Field(..., description="Text to summarize")
    max_words: int = Field(100, ge=10, le=500, description="Maximum words in summary")
    model: str = Field("qwen3.5:27b", description="Ollama model name")
    temperature: float = Field(0.5, ge=0.0, le=2.0, description="Sampling temperature")


class TemplateInferenceResponse(BaseModel):
    """Template-based inference response."""

    id: str
    model: str
    text: str
    usage: dict = {}
    template_used: str
    template_variables: dict


class SentimentAnalysisRequest(BaseModel):
    """Sentiment analysis request."""

    text: str = Field(..., description="Text to analyze")
    model: str = Field("qwen3.5:27b", description="Ollama model name")
    temperature: float = Field(0.3, ge=0.0, le=2.0, description="Sampling temperature")


class QuestionAnsweringRequest(BaseModel):
    """Question answering request."""

    question: str = Field(..., description="Question to answer")
    context: str = Field(..., description="Context to use for answering")
    model: str = Field("qwen3.5:27b", description="Ollama model name")
    temperature: float = Field(0.3, ge=0.0, le=2.0, description="Sampling temperature")


class TranslationRequest(BaseModel):
    """Translation request."""

    text: str = Field(..., description="Text to translate")
    source_lang: str = Field(..., description="Source language (e.g., 'English', 'French')")
    target_lang: str = Field(..., description="Target language")
    model: str = Field("qwen3.5:27b", description="Ollama model name")
    temperature: float = Field(0.5, ge=0.0, le=2.0, description="Sampling temperature")


class CodeReviewRequest(BaseModel):
    """Code review request."""

    code: str = Field(..., description="Code to review")
    language: str = Field(..., description="Programming language (e.g., 'Python', 'JavaScript')")
    model: str = Field("qwen3.5:27b", description="Ollama model name")
    temperature: float = Field(0.3, ge=0.0, le=2.0, description="Sampling temperature")


class ErrorAnalysisRequest(BaseModel):
    """Error analysis request."""

    error_type: str = Field(..., description="Error type (e.g., 'ValueError', 'TypeError')")
    error_message: str = Field(..., description="Error message")
    stack_trace: str = Field(..., description="Stack trace")
    model: str = Field("qwen3.5:27b", description="Ollama model name")
    temperature: float = Field(0.5, ge=0.0, le=2.0, description="Sampling temperature")


# Dependency
async def get_ollama_service() -> OllamaInferenceService:
    """Get Ollama inference service instance with configuration from settings."""
    settings = get_settings()
    adapter = OllamaAdapter(
        base_url=settings.ollama.base_url,
        pool_connections=settings.ollama.pool_connections,
        pool_maxsize=settings.ollama.pool_maxsize,
    )
    service = OllamaInferenceService(adapter, default_model="qwen3.5:27b")
    return service


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Chat completion",
    description="Generate a chat completion using Ollama",
)
async def chat_completion(
    request: ChatRequest,
    service: OllamaInferenceService = Depends(get_ollama_service),
) -> ChatResponse:
    """
    Generate a chat completion.

    Args:
        request: Chat request with messages
        service: Ollama inference service

    Returns:
        Chat response with generated message
    """
    try:
        # Convert messages to dict format
        messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]

        # Make prediction
        result = await service.predict(
            model_id=request.model,
            input_data={"messages": messages},
            parameters={"temperature": request.temperature},
        )

        return ChatResponse(
            id=str(uuid4()), model=result["model"], message=result["text"], usage=result["usage"]
        )

    except Exception as e:
        logger.error(f"Chat completion failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat completion failed: {str(e)}",
        )


@router.post(
    "/completions",
    response_model=CompletionResponse,
    status_code=status.HTTP_200_OK,
    summary="Text completion",
    description="Generate a text completion using Ollama",
)
async def text_completion(
    request: CompletionRequest,
    service: OllamaInferenceService = Depends(get_ollama_service),
) -> CompletionResponse:
    """
    Generate a text completion.

    Args:
        request: Completion request with prompt
        service: Ollama inference service

    Returns:
        Completion response with generated text
    """
    try:
        # Make prediction
        result = await service.predict(
            model_id=request.model,
            input_data={"prompt": request.prompt},
            parameters={"temperature": request.temperature, "max_tokens": request.max_tokens},
        )

        return CompletionResponse(
            id=str(uuid4()), model=result["model"], text=result["text"], usage=result["usage"]
        )

    except Exception as e:
        logger.error(f"Text completion failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Text completion failed: {str(e)}",
        )


@router.get(
    "/models",
    response_model=ModelsListResponse,
    status_code=status.HTTP_200_OK,
    summary="List models",
    description="List all available Ollama models",
)
async def list_models(
    service: OllamaInferenceService = Depends(get_ollama_service),
) -> ModelsListResponse:
    """
    List all available Ollama models.

    Args:
        service: Ollama inference service

    Returns:
        List of available models
    """
    try:
        # Get models from Ollama
        models_data = await service.ollama.list_models()

        # Convert to response format
        models = []
        for m in models_data:
            details = m.get("details", {})
            # Convert size to string if it's an int
            size = m.get("size", "Unknown")
            if isinstance(size, int):
                size = str(size)
            models.append(
                ModelInfo(
                    name=m["name"],
                    size=size,
                    parameter_count=details.get("parameter_size", "Unknown"),
                    quantization=details.get("quantization_level", "Unknown"),
                    family=details.get("family", "Unknown"),
                )
            )

        return ModelsListResponse(models=models, total=len(models))

    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list models: {str(e)}",
        )


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Check Ollama service health",
)
async def health_check(
    service: OllamaInferenceService = Depends(get_ollama_service),
) -> dict:
    """
    Check Ollama service health.

    Args:
        service: Ollama inference service

    Returns:
        Health status
    """
    try:
        is_healthy = await service.ollama.health_check()

        if is_healthy:
            return {"status": "healthy", "service": "ollama", "url": service.ollama.base_url}
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Ollama service is not healthy",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Health check failed: {str(e)}"
        )


@router.post(
    "/infer-with-template",
    response_model=TemplateInferenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Inference with template",
    description="Run inference using a prompt template",
)
async def infer_with_template(
    request: TemplateInferenceRequest,
    service: OllamaInferenceService = Depends(get_ollama_service),
) -> TemplateInferenceResponse:
    """
    Run inference using a prompt template.

    This endpoint allows you to use pre-defined or custom prompt templates
    for structured inference tasks.

    Args:
        request: Template inference request
        service: Ollama inference service

    Returns:
        Inference response with template information
    """
    try:
        # Run inference with template
        result = await service.predict_with_template(
            model_id=request.model,
            template_name=request.template_name,
            template_variables=request.variables,
            parameters={"temperature": request.temperature, "max_tokens": request.max_tokens},
        )

        return TemplateInferenceResponse(
            id=str(uuid4()),
            model=result["model"],
            text=result["text"],
            usage=result["usage"],
            template_used=result["template_used"],
            template_variables=result["template_variables"],
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Template inference failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Template inference failed: {str(e)}",
        )


@router.post(
    "/classify",
    response_model=CompletionResponse,
    status_code=status.HTTP_200_OK,
    summary="Text classification",
    description="Classify text into predefined categories using templates",
)
async def classify_text(
    request: ClassificationRequest,
    service: OllamaInferenceService = Depends(get_ollama_service),
) -> CompletionResponse:
    """
    Classify text into categories.

    Uses the text_classification template if available, otherwise falls back
    to a simple prompt.

    Args:
        request: Classification request
        service: Ollama inference service

    Returns:
        Classification result
    """
    try:
        result = await service.classify_text(
            model_id=request.model,
            text=request.text,
            categories=request.categories,
            parameters={"temperature": request.temperature},
        )

        return CompletionResponse(
            id=str(uuid4()), model=result["model"], text=result["text"], usage=result["usage"]
        )

    except Exception as e:
        logger.error(f"Text classification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Text classification failed: {str(e)}",
        )


@router.post(
    "/extract-entities",
    response_model=CompletionResponse,
    status_code=status.HTTP_200_OK,
    summary="Named entity recognition",
    description="Extract named entities from text using templates",
)
async def extract_entities(
    request: EntityExtractionRequest,
    service: OllamaInferenceService = Depends(get_ollama_service),
) -> CompletionResponse:
    """
    Extract named entities from text.

    Uses the named_entity_recognition template if available, otherwise
    falls back to a simple prompt.

    Args:
        request: Entity extraction request
        service: Ollama inference service

    Returns:
        Entity extraction result
    """
    try:
        result = await service.extract_entities(
            model_id=request.model,
            text=request.text,
            parameters={"temperature": request.temperature},
        )

        return CompletionResponse(
            id=str(uuid4()), model=result["model"], text=result["text"], usage=result["usage"]
        )

    except Exception as e:
        logger.error(f"Entity extraction failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Entity extraction failed: {str(e)}",
        )


@router.post(
    "/summarize",
    response_model=CompletionResponse,
    status_code=status.HTTP_200_OK,
    summary="Text summarization",
    description="Summarize text using templates",
)
async def summarize_text(
    request: SummarizationRequest,
    service: OllamaInferenceService = Depends(get_ollama_service),
) -> CompletionResponse:
    """
    Summarize text.

    Uses the text_summarization template if available, otherwise
    falls back to a simple prompt.

    Args:
        request: Summarization request
        service: Ollama inference service

    Returns:
        Summarization result
    """
    try:
        result = await service.summarize_text(
            model_id=request.model,
            text=request.text,
            max_words=request.max_words,
            parameters={"temperature": request.temperature},
        )

        return CompletionResponse(
            id=str(uuid4()), model=result["model"], text=result["text"], usage=result["usage"]
        )

    except Exception as e:
        logger.error(f"Text summarization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Text summarization failed: {str(e)}",
        )


@router.post(
    "/sentiment",
    response_model=CompletionResponse,
    status_code=status.HTTP_200_OK,
    summary="Sentiment analysis",
    description="Analyze sentiment of text using templates",
)
async def analyze_sentiment(
    request: SentimentAnalysisRequest,
    service: OllamaInferenceService = Depends(get_ollama_service),
) -> CompletionResponse:
    """
    Analyze sentiment of text.

    Uses the sentiment_analysis template if available, otherwise
    falls back to a simple prompt.

    Args:
        request: Sentiment analysis request
        service: Ollama inference service

    Returns:
        Sentiment analysis result with sentiment, confidence, and key phrases
    """
    try:
        result = await service.analyze_sentiment(
            model_id=request.model,
            text=request.text,
            parameters={"temperature": request.temperature},
        )

        return CompletionResponse(
            id=str(uuid4()), model=result["model"], text=result["text"], usage=result["usage"]
        )

    except Exception as e:
        logger.error(f"Sentiment analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sentiment analysis failed: {str(e)}",
        )


@router.post(
    "/question-answer",
    response_model=CompletionResponse,
    status_code=status.HTTP_200_OK,
    summary="Question answering",
    description="Answer questions based on context using templates",
)
async def answer_question(
    request: QuestionAnsweringRequest,
    service: OllamaInferenceService = Depends(get_ollama_service),
) -> CompletionResponse:
    """
    Answer a question based on provided context.

    Uses the question_answering template if available, otherwise
    falls back to a simple prompt.

    Args:
        request: Question answering request
        service: Ollama inference service

    Returns:
        Question answering result
    """
    try:
        result = await service.answer_question(
            model_id=request.model,
            question=request.question,
            context=request.context,
            parameters={"temperature": request.temperature},
        )

        return CompletionResponse(
            id=str(uuid4()), model=result["model"], text=result["text"], usage=result["usage"]
        )

    except Exception as e:
        logger.error(f"Question answering failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Question answering failed: {str(e)}",
        )


@router.post(
    "/translate",
    response_model=CompletionResponse,
    status_code=status.HTTP_200_OK,
    summary="Translation",
    description="Translate text between languages using templates",
)
async def translate_text(
    request: TranslationRequest,
    service: OllamaInferenceService = Depends(get_ollama_service),
) -> CompletionResponse:
    """
    Translate text from source language to target language.

    Uses the translation template if available, otherwise
    falls back to a simple prompt.

    Args:
        request: Translation request
        service: Ollama inference service

    Returns:
        Translation result
    """
    try:
        result = await service.translate_text(
            model_id=request.model,
            text=request.text,
            source_lang=request.source_lang,
            target_lang=request.target_lang,
            parameters={"temperature": request.temperature},
        )

        return CompletionResponse(
            id=str(uuid4()), model=result["model"], text=result["text"], usage=result["usage"]
        )

    except Exception as e:
        logger.error(f"Translation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Translation failed: {str(e)}",
        )


@router.post(
    "/code-review",
    response_model=CompletionResponse,
    status_code=status.HTTP_200_OK,
    summary="Code review",
    description="Review code for bugs, security, and best practices using templates",
)
async def review_code(
    request: CodeReviewRequest,
    service: OllamaInferenceService = Depends(get_ollama_service),
) -> CompletionResponse:
    """
    Review code for bugs, security issues, performance problems, and best practices.

    Uses the code_review template if available, otherwise
    falls back to a simple prompt.

    Args:
        request: Code review request
        service: Ollama inference service

    Returns:
        Code review result with detailed analysis
    """
    try:
        result = await service.review_code(
            model_id=request.model,
            code=request.code,
            language=request.language,
            parameters={"temperature": request.temperature},
        )

        return CompletionResponse(
            id=str(uuid4()), model=result["model"], text=result["text"], usage=result["usage"]
        )

    except Exception as e:
        logger.error(f"Code review failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Code review failed: {str(e)}",
        )


@router.post(
    "/error-analysis",
    response_model=CompletionResponse,
    status_code=status.HTTP_200_OK,
    summary="Error analysis",
    description="Analyze errors and provide solutions using templates",
)
async def analyze_error(
    request: ErrorAnalysisRequest,
    service: OllamaInferenceService = Depends(get_ollama_service),
) -> CompletionResponse:
    """
    Analyze an error and provide root cause, solutions, and prevention strategies.

    Uses the error_analysis template if available, otherwise
    falls back to a simple prompt.

    Args:
        request: Error analysis request
        service: Ollama inference service

    Returns:
        Error analysis with root cause and solutions
    """
    try:
        result = await service.analyze_error(
            model_id=request.model,
            error_type=request.error_type,
            error_message=request.error_message,
            stack_trace=request.stack_trace,
            parameters={"temperature": request.temperature},
        )

        return CompletionResponse(
            id=str(uuid4()), model=result["model"], text=result["text"], usage=result["usage"]
        )

    except Exception as e:
        logger.error(f"Error analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analysis failed: {str(e)}",
        )
