"""LLM infrastructure for Tawiza."""

from .adaptive_provider import AdaptiveLLMProvider
from .factory import create_debate_system_with_llm, create_vision_analyzer
from .hybrid_router import (
    HybridLLMRouter,
    OumiClient,
    RoutingDecision,
    TaskComplexity,
    TaskComplexityAnalyzer,
)
from .multi_provider import (
    CAMELModelBackend,
    ChatMessage,
    LLMResponse,
    MultiProviderLLM,
    ProviderConfig,
    ProviderType,
    create_default_multi_provider,
)
from .ollama_client import OllamaClient
from .vision_analyzer import VisionAnalyzer

__all__ = [
    # Ollama
    "OllamaClient",
    "AdaptiveLLMProvider",
    "VisionAnalyzer",
    # Factory
    "create_debate_system_with_llm",
    "create_vision_analyzer",
    # Multi-provider
    "MultiProviderLLM",
    "ProviderType",
    "ProviderConfig",
    "ChatMessage",
    "LLMResponse",
    "CAMELModelBackend",
    "create_default_multi_provider",
    # Hybrid router
    "HybridLLMRouter",
    "TaskComplexity",
    "TaskComplexityAnalyzer",
    "RoutingDecision",
    "OumiClient",
]
