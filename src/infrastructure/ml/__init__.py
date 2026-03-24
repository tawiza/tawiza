"""Machine Learning infrastructure module.

Provides ML infrastructure components including:
- Ollama integration for local LLM inference
- MLflow for experiment tracking
- vLLM for high-performance inference
- Fine-tuning with LLaMA-Factory
- Active learning pipelines
"""


# Lazy imports to avoid circular dependencies
def get_ollama_adapter():
    """Get OllamaAdapter instance."""
    from src.infrastructure.ml.ollama.ollama_adapter import OllamaAdapter

    return OllamaAdapter


def get_ollama_client():
    """Get OllamaClient instance."""
    from src.infrastructure.ml.ollama.ollama_client import OllamaClient

    return OllamaClient


def get_ollama_inference_service():
    """Get OllamaInferenceService class."""
    from src.infrastructure.ml.ollama.ollama_inference_service import OllamaInferenceService

    return OllamaInferenceService


def create_debate_system_with_llm(*args, **kwargs):
    """Create a debate system with LLM backend."""
    from src.infrastructure.ml.ollama.ollama_adapter import OllamaAdapter

    # Factory function for debate system
    return OllamaAdapter(*args, **kwargs)


__all__ = [
    "get_ollama_adapter",
    "get_ollama_client",
    "get_ollama_inference_service",
    "create_debate_system_with_llm",
]
