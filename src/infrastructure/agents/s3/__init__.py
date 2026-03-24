"""S3-style Agent - Hybrid Browser + Desktop automation agent.

This package provides the S3Agent implementation, inspired by Agent-S3,
combining browser automation (Playwright) with desktop automation (PyAutoGUI + Vision).

The S3 Agent is designed for:
- Hybrid GUI + Code execution
- Decision between browser and desktop actions
- Vision-based UI element detection
- Desktop application control (LibreOffice, terminal, file manager, etc.)

Key Features:
- Mode decision (browser vs desktop) using LLM
- Playwright for web automation
- xdotool + Vision models for desktop automation
- SSH/VNC connection to VM-400 sandbox for isolated execution

Vision System:
- VisionClient: UI-TARS/SeeClick inspired element detection
- Uses qwen3-vl:32b for visual grounding
- Supports element finding, action suggestion, enumeration
"""

from .s3_agent import DesktopClient, S3Action, S3Agent, S3Mode, create_s3_agent
from .vision_client import (
    ElementType,
    UIElement,
    VisionAnalysis,
    VisionClient,
    create_vision_client,
)

__all__ = [
    # Agent
    "S3Agent",
    "S3Mode",
    "S3Action",
    "create_s3_agent",
    # Desktop
    "DesktopClient",
    # Vision
    "VisionClient",
    "UIElement",
    "ElementType",
    "VisionAnalysis",
    "create_vision_client",
]
