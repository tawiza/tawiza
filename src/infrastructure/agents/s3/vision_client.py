"""Vision client for S3 Agent - UI element detection using Qwen3-VL.

This module provides vision capabilities for the S3 Agent, inspired by UI-TARS
and SeeClick approaches for GUI element detection and interaction.

Features:
- Screenshot analysis for UI element detection
- Click point prediction (x, y coordinates)
- Bounding box extraction for UI elements
- OCR-like text extraction from screenshots
- Action suggestion based on visual context
"""

import asyncio
import base64
import json
import os
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import httpx
from loguru import logger


class ElementType(Enum):
    """Types of UI elements that can be detected."""

    BUTTON = "button"
    TEXT_FIELD = "text_field"
    LINK = "link"
    ICON = "icon"
    MENU = "menu"
    CHECKBOX = "checkbox"
    DROPDOWN = "dropdown"
    IMAGE = "image"
    TEXT = "text"
    WINDOW = "window"
    UNKNOWN = "unknown"


@dataclass
class UIElement:
    """Represents a detected UI element."""

    element_type: ElementType
    text: str
    x: int
    y: int
    width: int | None = None
    height: int | None = None
    confidence: float = 0.0

    @property
    def center(self) -> tuple[int, int]:
        """Get center point of element."""
        if self.width and self.height:
            return (self.x + self.width // 2, self.y + self.height // 2)
        return (self.x, self.y)

    @property
    def bbox(self) -> tuple[int, int, int, int] | None:
        """Get bounding box (left, top, right, bottom)."""
        if self.width and self.height:
            return (self.x, self.y, self.x + self.width, self.y + self.height)
        return None


@dataclass
class VisionAnalysis:
    """Result of vision analysis."""

    elements: list[UIElement]
    suggested_action: str | None = None
    action_target: UIElement | None = None
    action_coordinates: tuple[int, int] | None = None
    reasoning: str = ""
    raw_response: str = ""


class VisionClient:
    """
    Vision client for UI element detection using Qwen3-VL.

    Uses prompting strategies inspired by UI-TARS for:
    - Grounding: Finding specific elements by description
    - Action prediction: Suggesting next action based on task
    - Element enumeration: Listing all interactive elements
    """

    # System prompts for different vision tasks
    GROUNDING_PROMPT = """You are a GUI element detector. Find the element in the screenshot.

RESPOND ONLY WITH JSON, no other text:
{"found": true, "element": {"type": "button", "text": "label", "x": 100, "y": 50}, "confidence": 0.9}

Or if not found:
{"found": false, "element": null, "confidence": 0.0}

Rules:
- x and y are CENTER coordinates in pixels (image is 1920x1080)
- x=0 is left, y=0 is top
- type: button, text_field, link, icon, menu, checkbox, dropdown, text
- ONLY output JSON, nothing else"""

    ACTION_PROMPT = """You are a GUI automation assistant. Analyze the screenshot and suggest the next action to accomplish the task.

Output format (JSON):
{
    "thought": "reasoning about what to do",
    "action": "click|double_click|right_click|type|scroll|drag|hotkey|wait",
    "target": {
        "x": click_x_coordinate,
        "y": click_y_coordinate,
        "description": "what element to interact with"
    },
    "value": "text to type or hotkey like 'ctrl+s' (if applicable)",
    "confidence": 0.0-1.0
}

Important:
- Only suggest ONE action at a time
- Coordinates must be precise pixel positions
- For typing, the target should be a text field that's already focused or will be clicked"""

    ENUMERATE_PROMPT = """You are a GUI element enumerator. List ALL interactive elements visible in the screenshot.

Output format (JSON):
{
    "elements": [
        {
            "type": "button|text_field|link|icon|menu|checkbox|dropdown",
            "text": "visible text or aria-label",
            "x": center_x,
            "y": center_y,
            "width": estimated_width,
            "height": estimated_height
        }
    ],
    "window_title": "main window title if visible",
    "application": "detected application name"
}

Focus on:
- Clickable buttons and icons
- Text input fields
- Menu items and dropdowns
- Links and navigation elements
Skip decorative elements and static text."""

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        model: str = "qwen3-vl:32b",
        timeout: int = 120,
        screen_width: int = 1920,
        screen_height: int = 1080,
    ):
        """
        Initialize vision client.

        Args:
            ollama_url: Ollama API URL
            model: Vision model to use (default: qwen3-vl:32b)
            timeout: Request timeout in seconds
            screen_width: Expected screen width for coordinate normalization
            screen_height: Expected screen height for coordinate normalization
        """
        self.ollama_url = ollama_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.screen_width = screen_width
        self.screen_height = screen_height

        self.client = httpx.AsyncClient(timeout=timeout)
        logger.info(f"VisionClient initialized (model={model})")

    async def _analyze_image(
        self,
        image_path: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> str:
        """
        Send image to vision model for analysis.

        Args:
            image_path: Path to screenshot image
            system_prompt: System prompt defining the task
            user_prompt: User query/instruction
            temperature: Sampling temperature (lower = more consistent)

        Returns:
            Model response text
        """
        # Read and encode image
        image_data = Path(image_path).read_bytes()
        image_b64 = base64.b64encode(image_data).decode("utf-8")

        # Prepare messages for chat endpoint
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt, "images": [image_b64]},
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        logger.debug(f"Sending vision request to {self.model}...")

        response = await self.client.post(
            f"{self.ollama_url}/api/chat",
            json=payload,
        )
        response.raise_for_status()

        result = response.json()
        return result.get("message", {}).get("content", "")

    def _parse_json_response(self, response: str) -> dict[str, Any]:
        """Extract JSON from model response."""
        # Try to find JSON block
        json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find raw JSON object
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning(f"Failed to parse JSON from response: {response[:200]}...")
        return {}

    def _normalize_coordinates(
        self,
        x: int,
        y: int,
        from_width: int = 1000,
        from_height: int = 1000,
    ) -> tuple[int, int]:
        """
        Normalize coordinates from model output to screen coordinates.

        Some models output coordinates in 0-1000 range, others in actual pixels.
        This method handles the conversion.
        """
        # If coordinates seem to be in 0-1000 range, scale them
        if x <= 1000 and y <= 1000 and from_width == 1000:
            x = int(x * self.screen_width / from_width)
            y = int(y * self.screen_height / from_height)

        # Clamp to screen bounds
        x = max(0, min(x, self.screen_width - 1))
        y = max(0, min(y, self.screen_height - 1))

        return (x, y)

    async def find_element(
        self,
        screenshot_path: str,
        element_description: str,
    ) -> UIElement | None:
        """
        Find a specific UI element by description.

        Args:
            screenshot_path: Path to screenshot
            element_description: Text description of element to find

        Returns:
            UIElement if found, None otherwise
        """
        user_prompt = f"Find this element: {element_description}"

        response = await self._analyze_image(
            screenshot_path,
            self.GROUNDING_PROMPT,
            user_prompt,
        )

        data = self._parse_json_response(response)

        if not data.get("found", False):
            logger.info(f"Element not found: {element_description}")
            return None

        element_data = data.get("element", {})

        # Parse element type
        type_str = element_data.get("type", "unknown").lower()
        try:
            element_type = ElementType(type_str)
        except ValueError:
            element_type = ElementType.UNKNOWN

        # Get coordinates
        x = element_data.get("x", 0)
        y = element_data.get("y", 0)
        x, y = self._normalize_coordinates(x, y)

        return UIElement(
            element_type=element_type,
            text=element_data.get("text", element_description),
            x=x,
            y=y,
            width=element_data.get("width"),
            height=element_data.get("height"),
            confidence=data.get("confidence", 0.5),
        )

    async def suggest_action(
        self,
        screenshot_path: str,
        task: str,
        context: str = "",
    ) -> VisionAnalysis:
        """
        Analyze screenshot and suggest next action for task.

        Args:
            screenshot_path: Path to screenshot
            task: User's task/goal
            context: Additional context (previous actions, etc.)

        Returns:
            VisionAnalysis with suggested action
        """
        user_prompt = f"Task: {task}"
        if context:
            user_prompt += f"\n\nContext: {context}"

        response = await self._analyze_image(
            screenshot_path,
            self.ACTION_PROMPT,
            user_prompt,
        )

        data = self._parse_json_response(response)

        # Extract action target
        target_data = data.get("target", {})
        target_x = target_data.get("x", 0)
        target_y = target_data.get("y", 0)

        if target_x or target_y:
            target_x, target_y = self._normalize_coordinates(target_x, target_y)
            action_coords = (target_x, target_y)

            action_target = UIElement(
                element_type=ElementType.UNKNOWN,
                text=target_data.get("description", ""),
                x=target_x,
                y=target_y,
                confidence=data.get("confidence", 0.5),
            )
        else:
            action_coords = None
            action_target = None

        return VisionAnalysis(
            elements=[],
            suggested_action=data.get("action"),
            action_target=action_target,
            action_coordinates=action_coords,
            reasoning=data.get("thought", ""),
            raw_response=response,
        )

    async def enumerate_elements(
        self,
        screenshot_path: str,
    ) -> VisionAnalysis:
        """
        List all interactive elements in screenshot.

        Args:
            screenshot_path: Path to screenshot

        Returns:
            VisionAnalysis with list of elements
        """
        response = await self._analyze_image(
            screenshot_path,
            self.ENUMERATE_PROMPT,
            "List all interactive elements in this screenshot.",
        )

        data = self._parse_json_response(response)

        elements = []
        for elem_data in data.get("elements", []):
            type_str = elem_data.get("type", "unknown").lower()
            try:
                element_type = ElementType(type_str)
            except ValueError:
                element_type = ElementType.UNKNOWN

            x = elem_data.get("x", 0)
            y = elem_data.get("y", 0)
            x, y = self._normalize_coordinates(x, y)

            elements.append(
                UIElement(
                    element_type=element_type,
                    text=elem_data.get("text", ""),
                    x=x,
                    y=y,
                    width=elem_data.get("width"),
                    height=elem_data.get("height"),
                )
            )

        return VisionAnalysis(
            elements=elements,
            reasoning=f"Found {len(elements)} interactive elements",
            raw_response=response,
        )

    async def click_element_by_text(
        self,
        screenshot_path: str,
        text: str,
    ) -> tuple[int, int] | None:
        """
        Convenience method: Find element by text and return click coordinates.

        Args:
            screenshot_path: Path to screenshot
            text: Text of element to click

        Returns:
            (x, y) coordinates to click, or None if not found
        """
        element = await self.find_element(screenshot_path, f"element with text '{text}'")
        if element:
            return element.center
        return None

    async def health_check(self) -> bool:
        """Check if vision model is available."""
        try:
            response = await self.client.get(f"{self.ollama_url}/api/tags")
            response.raise_for_status()

            models = response.json().get("models", [])
            model_names = [m["name"] for m in models]

            if self.model in model_names:
                logger.info(f"Vision model {self.model} is available")
                return True
            else:
                logger.warning(f"Vision model {self.model} not found. Available: {model_names}")
                return False

        except Exception as e:
            logger.error(f"Vision health check failed: {e}")
            return False

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


# Factory function
def create_vision_client(
    ollama_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    model: str = "llava:13b",  # Lighter vision model available on sandbox VM
) -> VisionClient:
    """Create a VisionClient instance.

    By default connects to sandbox VM Ollama (with GPU) for faster inference.

    Args:
        ollama_url: Ollama API URL (default: localhost)
        model: Vision model (default: llava:13b, available on sandbox VM)

    Returns:
        Configured VisionClient
    """
    return VisionClient(ollama_url=ollama_url, model=model)


# Test function
async def test_vision_client():
    """Test vision client with a screenshot."""
    client = create_vision_client()

    # Health check
    healthy = await client.health_check()
    print(f"Vision client healthy: {healthy}")

    if healthy:
        # Test with sandbox VM screenshot if available
        test_screenshot = "/tmp/sandbox_desktop.png"
        if Path(test_screenshot).exists():
            print("\nEnumerating elements...")
            analysis = await client.enumerate_elements(test_screenshot)
            print(f"Found {len(analysis.elements)} elements:")
            for elem in analysis.elements[:5]:
                print(f"  - {elem.element_type.value}: '{elem.text}' at ({elem.x}, {elem.y})")

            print("\nFinding 'Applications' menu...")
            element = await client.find_element(test_screenshot, "Applications menu")
            if element:
                print(f"Found at: ({element.x}, {element.y})")
        else:
            print(f"Test screenshot not found: {test_screenshot}")

    await client.close()


if __name__ == "__main__":
    asyncio.run(test_vision_client())
