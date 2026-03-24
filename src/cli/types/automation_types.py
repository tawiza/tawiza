"""Type definitions for automation.

This module provides strong typing for automation components, improving
code safety and IDE support.
"""

from enum import Enum
from typing import Literal, TypedDict


class AgentType(Enum):
    """Supported automation agents."""

    OPENMANUS = "openmanus"
    SKYVERN = "skyvern"


class TaskAction(TypedDict, total=False):
    """Structure for task actions sent to agents."""

    url: str
    action: Literal["navigate", "click", "type", "extract", "scroll", "wait"]
    element: str | None  # CSS selector
    value: str | None  # Value for type action
    timeout: int | None  # Action timeout in seconds


class AIResponse(TypedDict, total=False):
    """Parsed AI response structure."""

    action: str  # Action description
    element: str | None  # CSS selector if applicable
    value: str | None  # Value if applicable
    reason: str  # Explanation of why this action helps


class ChatMessage(TypedDict):
    """Chat message structure."""

    role: Literal["user", "assistant", "system"]
    content: str
