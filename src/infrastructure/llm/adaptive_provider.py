"""Adaptive LLM Provider that switches between text and vision models."""

import base64
from typing import Any

from loguru import logger

from src.domain.debate.agents import LLMProvider


class AdaptiveLLMProvider(LLMProvider):
    """LLM Provider that automatically selects text or vision model.

    Uses text model (faster) for text-only prompts.
    Switches to vision model when images are provided.

    Example:
        provider = AdaptiveLLMProvider(
            client=ollama_client,
            text_model="qwen3.5:27b",
            vision_model="qwen3-vl:32b",
        )

        # Text-only (uses qwen3.5:27b)
        response = await provider.generate("Summarize this data")

        # With image (uses qwen3-vl:32b)
        response = await provider.generate("Describe", images=[screenshot_bytes])
    """

    def __init__(
        self,
        client: Any,
        text_model: str = "qwen3.5:27b",
        vision_model: str = "qwen3-vl:32b",
    ):
        """Initialize adaptive provider.

        Args:
            client: OllamaClient instance
            text_model: Model for text-only generation
            vision_model: Model for vision tasks
        """
        self._client = client
        self._text_model = text_model
        self._vision_model = vision_model

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        images: list[bytes] | None = None,
    ) -> str:
        """Generate response, auto-selecting model based on input.

        Args:
            prompt: The user prompt
            system: Optional system prompt
            images: Optional list of image bytes for vision analysis

        Returns:
            Generated text response
        """
        if images:
            return await self._generate_with_vision(prompt, system, images)
        else:
            return await self._generate_text(prompt, system)

    async def _generate_text(self, prompt: str, system: str | None) -> str:
        """Generate using text model."""
        logger.debug(f"Using text model: {self._text_model}")
        return await self._client.generate(
            prompt=prompt,
            model=self._text_model,
            system=system,
            temperature=0.7,
        )

    async def _generate_with_vision(
        self,
        prompt: str,
        system: str | None,
        images: list[bytes],
    ) -> str:
        """Generate using vision model with images."""
        logger.debug(f"Using vision model: {self._vision_model}")

        # Encode images to base64
        images_b64 = [base64.b64encode(img).decode("utf-8") for img in images]

        # Build payload for vision model
        payload = {
            "model": self._vision_model,
            "prompt": prompt,
            "images": images_b64,
            "stream": False,
            "options": {"temperature": 0.3},
        }

        if system:
            payload["system"] = system

        # Use raw client post for vision
        response = await self._client.client.post(
            f"{self._client.base_url}/api/generate",
            json=payload,
        )
        response.raise_for_status()
        return response.json().get("response", "")
