"""Factory functions for creating LLM-enabled components."""

from src.domain.debate import DebateMode, DebateSystem
from src.infrastructure.llm.adaptive_provider import AdaptiveLLMProvider
from src.infrastructure.llm.ollama_client import OllamaClient
from src.infrastructure.llm.vision_analyzer import VisionAnalyzer


def create_debate_system_with_llm(
    text_model: str = "qwen3.5:27b",
    vision_model: str = "qwen3-vl:32b",
    mode: DebateMode = DebateMode.EXTENDED,
    ollama_url: str = "http://localhost:11434",
) -> DebateSystem:
    """Create a DebateSystem with LLM support.

    This factory function creates a fully configured debate system
    with LLM-enabled agents for intelligent data validation.

    Args:
        text_model: Model for text generation (default: qwen3.5:27b)
        vision_model: Model for vision tasks (default: qwen3-vl:32b)
        mode: Debate mode (STANDARD or EXTENDED)
        ollama_url: Ollama API URL

    Returns:
        Configured DebateSystem with LLM-enabled agents

    Example:
        debate = create_debate_system_with_llm()
        result = await debate.validate("Company Name", data)
    """
    # Create Ollama client
    client = OllamaClient(
        base_url=ollama_url,
        model=text_model,
        vision_model=vision_model,
    )

    # Create adaptive provider
    provider = AdaptiveLLMProvider(
        client=client,
        text_model=text_model,
        vision_model=vision_model,
    )

    # Create debate system with LLM
    return DebateSystem(mode=mode, llm=provider)


def create_vision_analyzer(
    vision_model: str = "qwen3-vl:32b",
    ollama_url: str = "http://localhost:11434",
) -> VisionAnalyzer:
    """Create a VisionAnalyzer instance.

    Factory function for creating a vision analyzer
    for screenshot and image analysis.

    Args:
        vision_model: Model for vision tasks
        ollama_url: Ollama API URL

    Returns:
        Configured VisionAnalyzer

    Example:
        analyzer = create_vision_analyzer()
        result = await analyzer.analyze_screenshot(image_bytes, "Describe this")
    """
    client = OllamaClient(
        base_url=ollama_url,
        vision_model=vision_model,
    )

    provider = AdaptiveLLMProvider(
        client=client,
        text_model=vision_model,  # Vision model for all calls
        vision_model=vision_model,
    )

    return VisionAnalyzer(provider=provider)
