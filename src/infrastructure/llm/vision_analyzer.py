"""Vision analysis service using LLM vision models."""

from typing import Any

from loguru import logger


class VisionAnalyzer:
    """Service for analyzing images using vision-capable LLMs.

    Provides high-level methods for common vision tasks like
    screenshot analysis and company information extraction.

    Example:
        analyzer = VisionAnalyzer(provider=adaptive_provider)
        result = await analyzer.analyze_screenshot(
            image_bytes=screenshot,
            prompt="What company is shown on this website?",
        )
    """

    COMPANY_EXTRACTION_PROMPT = """Analyze this screenshot and extract company information.
Return a JSON object with the following fields if found:
- name: Company name
- sector: Industry/sector
- description: Brief description
- contact: Contact information if visible
- services: List of services/products mentioned

Only include fields that are clearly visible in the image."""

    def __init__(self, provider: Any):
        """Initialize with an LLM provider.

        Args:
            provider: LLM provider with generate() method supporting images
        """
        self._provider = provider

    async def analyze_screenshot(
        self,
        image_bytes: bytes,
        prompt: str,
        system: str | None = None,
    ) -> str:
        """Analyze a screenshot with a custom prompt.

        Args:
            image_bytes: Raw image bytes (PNG, JPEG, etc.)
            prompt: Question or instruction for analysis
            system: Optional system prompt

        Returns:
            LLM analysis result
        """
        logger.debug(f"Analyzing screenshot with prompt: {prompt[:50]}...")

        return await self._provider.generate(
            prompt=prompt,
            system=system,
            images=[image_bytes],
        )

    async def extract_company_info(
        self,
        image_bytes: bytes,
        additional_context: str | None = None,
    ) -> str:
        """Extract company information from a screenshot.

        Uses a specialized prompt for company data extraction.

        Args:
            image_bytes: Screenshot bytes
            additional_context: Extra context to add to the prompt

        Returns:
            JSON string with extracted company information
        """
        prompt = self.COMPANY_EXTRACTION_PROMPT
        if additional_context:
            prompt = f"{prompt}\n\nAdditional context: {additional_context}"

        logger.debug("Extracting company info from screenshot")

        return await self._provider.generate(
            prompt=prompt,
            system="You are an expert at extracting structured data from images. "
            "Always respond with valid JSON.",
            images=[image_bytes],
        )

    async def compare_screenshots(
        self,
        image1_bytes: bytes,
        image2_bytes: bytes,
        comparison_prompt: str | None = None,
    ) -> str:
        """Compare two screenshots.

        Args:
            image1_bytes: First screenshot
            image2_bytes: Second screenshot
            comparison_prompt: Custom comparison instructions

        Returns:
            Comparison analysis
        """
        prompt = comparison_prompt or (
            "Compare these two screenshots. "
            "Identify similarities and differences in content, layout, and information."
        )

        logger.debug("Comparing two screenshots")

        return await self._provider.generate(
            prompt=prompt,
            images=[image1_bytes, image2_bytes],
        )
