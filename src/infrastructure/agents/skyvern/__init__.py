"""Skyvern - Production-ready web automation with computer vision.

Skyvern uses computer vision + LLM for robust web automation:
- Vision-based element detection (no fragile CSS selectors)
- Multi-agent architecture (Vision → Planning → Execution)
- Production-ready workflows with retry logic
- Advanced error handling and recovery

Note: Currently uses OpenManus as backend. Install Skyvern SDK
for full vision capabilities: pip install skyvern
"""

from src.infrastructure.agents.skyvern.skyvern_adapter import SkyvernAdapter

__all__ = [
    "SkyvernAdapter",
]
