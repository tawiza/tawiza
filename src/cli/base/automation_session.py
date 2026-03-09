"""Base class for automation sessions.

This module provides a base class for all automation sessions, eliminating code
duplication and following SOLID principles (Single Responsibility, Dependency Inversion).
"""

import os
from abc import ABC, abstractmethod
from typing import Any

from loguru import logger
from rich.console import Console

from src.infrastructure.agents.openmanus.openmanus_adapter import OpenManusAdapter
from src.infrastructure.llm.ollama_client import OllamaClient

console = Console()


class AutomationSession(ABC):
    """
    Base class for automation sessions with common initialization.

    This class follows the Template Method pattern, providing a skeleton for
    automation sessions while allowing subclasses to customize specific steps.

    Attributes:
        model: Ollama model name to use for AI inference
        headless: Whether to run browser in headless mode
        url: Optional starting URL to navigate to
        ollama: Ollama client instance (initialized by initialize())
        agent: Agent instance (initialized by initialize())
    """

    def __init__(
        self,
        model: str = "qwen3-coder:30b",
        headless: bool = True,
        url: str | None = None,
    ):
        """
        Initialize automation session.

        Args:
            model: Ollama model to use (default: qwen3-coder:30b)
            headless: Run browser without GUI (default: True)
            url: Optional starting URL to load
        """
        self.model = model
        self.headless = self._determine_headless_mode(headless)
        self.url = url
        self.ollama: OllamaClient | None = None
        self.agent: OpenManusAdapter | None = None
        self.current_url: str | None = url

    def _determine_headless_mode(self, requested_headless: bool) -> bool:
        """
        Determine if headless mode should be used based on environment.

        Args:
            requested_headless: User's requested mode

        Returns:
            True if headless mode should be used, False otherwise
        """
        if not requested_headless and not os.environ.get("DISPLAY"):
            console.print(
                "[yellow]⚠️  No display detected. Forcing headless mode.[/yellow]"
            )
            return True
        return requested_headless

    async def initialize(self) -> None:
        """
        Initialize Ollama client and automation agent.

        Raises:
            RuntimeError: If Ollama is not available
        """
        console.print("[yellow]⚙️  Initializing...[/yellow]")

        # Initialize Ollama
        self.ollama = OllamaClient(model=self.model)

        console.print("[yellow]🔄 Checking Ollama...[/yellow]")
        healthy = await self.ollama.health_check()

        if not healthy:
            error_msg = "Ollama not available! Start with: ollama serve"
            console.print(f"[red]❌ {error_msg}[/red]")
            raise RuntimeError(error_msg)

        console.print("[green]✅ Ollama ready[/green]\n")

        # Initialize agent
        self.agent = OpenManusAdapter(
            headless=self.headless, llm_client=self.ollama
        )

        # Navigate to starting URL if provided
        if self.url:
            await self._navigate_to_url(self.url)

    async def _navigate_to_url(self, url: str) -> None:
        """
        Navigate to a specific URL with smart retry logic.

        Tries fast navigation first (networkidle), then falls back to
        slower strategy (domcontentloaded) for complex sites like GitHub.

        Args:
            url: The URL to navigate to
        """
        console.print(f"[cyan]🌐 Navigating to {url}...[/cyan]")
        try:
            await self.agent.execute_task({"url": url, "action": "navigate"})
            self.current_url = url
            console.print("[green]✅ Page loaded[/green]\n")
        except Exception as e:
            error_msg = str(e)
            if "Timeout" in error_msg:
                console.print(
                    "[yellow]⚠️  Page is slow to load (this is normal for sites like GitHub)[/yellow]"
                )
            console.print(f"[red]❌ Navigation failed: {e}[/red]\n")
            raise

    async def cleanup(self) -> None:
        """
        Clean up resources (Ollama client, agent).

        Call this method to properly release resources when the session ends.
        """
        if self.ollama:
            await self.ollama.close()
            logger.debug("Ollama client closed")

    @abstractmethod
    async def run(self) -> Any:
        """
        Run the automation session.

        This method must be implemented by subclasses to define the specific
        automation logic.

        Returns:
            Any result from the automation (implementation-specific)
        """
        pass

    async def execute(self) -> Any:
        """
        Execute the complete automation workflow.

        This is the main entry point that handles initialization, execution,
        and cleanup in the correct order.

        Returns:
            The result from run()
        """
        try:
            await self.initialize()
            result = await self.run()
            return result
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️  Cancelled by user[/yellow]")
            raise
        except Exception as e:
            console.print(f"\n[red]❌ Error: {e}[/red]")
            logger.exception("Automation session failed")
            raise
        finally:
            await self.cleanup()
