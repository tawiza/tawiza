"""Default configuration values for CLI automation.

This module centralizes all configuration constants, following the
Single Responsibility Principle and making it easy to modify defaults.
"""

import os
from dataclasses import dataclass

# API Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")


@dataclass(frozen=True)
class AutomationDefaults:
    """Default configuration for automation sessions."""

    # Model configuration
    model: str = "qwen3.5:27b"
    vision_model: str = "qwen3-vl:8b"

    # Automation limits
    max_actions: int = 5
    max_conversation_history: int = 10

    # Timeouts (seconds)
    page_load_timeout: int = 30
    ai_response_timeout: int = 60
    health_check_timeout: int = 5

    # Browser configuration
    headless: bool = True
    viewport_width: int = 1280
    viewport_height: int = 720

    # Display configuration
    enable_rich_display: bool = True
    enable_streaming: bool = True
    show_timestamps: bool = False


# Singleton instance
defaults = AutomationDefaults()
