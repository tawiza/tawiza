"""Skyvern agent adapter implementation.

Skyvern is a production-ready web automation agent using computer vision + LLM.
This is a stub implementation that can be replaced with actual Skyvern SDK.

For now, it wraps the OpenManus implementation with Skyvern branding.
"""

from typing import Any

from loguru import logger

from src.application.ports.agent_ports import AgentType
from src.infrastructure.agents.openmanus.openmanus_adapter import OpenManusAdapter


class SkyvernAdapter(OpenManusAdapter):
    """Skyvern agent adapter.

    Currently wraps OpenManus adapter.
    Can be replaced with actual Skyvern SDK when available.

    Skyvern provides:
    - Vision-based element detection (no fragile CSS selectors)
    - Multi-agent architecture (Vision → Planning → Execution)
    - Production-ready workflows
    - Advanced error handling
    """

    def __init__(
        self,
        headless: bool = True,
        screenshots_dir: str = "/tmp/tawiza-skyvern-screenshots",
        llm_client: Any | None = None,
        use_vision: bool = False,
    ) -> None:
        """Initialize Skyvern adapter.

        Args:
            headless: Run browser in headless mode
            screenshots_dir: Directory for screenshots
            llm_client: LLM client for AI guidance
            use_vision: Enable vision-based element detection (future)
        """
        # Call parent but override agent type
        super().__init__(headless=headless, screenshots_dir=screenshots_dir, llm_client=llm_client)

        # Override agent type
        self.agent_type = AgentType.SKYVERN
        self.use_vision = use_vision

        logger.info(f"Initialized Skyvern adapter (vision_mode={use_vision}, headless={headless})")

        logger.warning(
            "Using OpenManus-based Skyvern stub. Install Skyvern SDK for full functionality."
        )

    async def execute_task(self, task_config: dict[str, Any]) -> dict[str, Any]:
        """Execute task using Skyvern.

        Currently delegates to OpenManus implementation.
        Will use Skyvern SDK when available.
        """
        logger.debug(f"Executing Skyvern task: {task_config.get('action')}")

        # For now, use parent OpenManus implementation
        result = await super().execute_task(task_config)

        # Add Skyvern metadata
        result["agent"] = "skyvern"
        result["vision_enabled"] = self.use_vision

        return result

    @property
    def name(self) -> str:
        """Get agent name."""
        return f"skyvern-{id(self)}"

    async def health_check(self) -> bool:
        """Check if Skyvern is operational.

        Currently checks browser availability.
        Will check Skyvern API when SDK is installed.

        Returns:
            True if operational, False otherwise.
        """
        # Check parent browser availability
        browser_ok = await super().health_check()

        # Future: Add Skyvern SDK check
        # if SKYVERN_SDK_AVAILABLE:
        #     skyvern_ok = await self.client.health_check()
        #     return browser_ok and skyvern_ok

        return browser_ok


# Note: To use real Skyvern SDK:
#
# pip install skyvern
#
# from skyvern import Skyvern
#
# class SkyvernAdapter(BaseAgent):
#     def __init__(self, api_key: str):
#         self.client = Skyvern(api_key=api_key)
#
#     async def execute_task(self, task_config):
#         result = await self.client.run_task(
#             url=task_config["url"],
#             prompt=task_config.get("prompt"),
#             data_extraction_schema=task_config.get("schema")
#         )
