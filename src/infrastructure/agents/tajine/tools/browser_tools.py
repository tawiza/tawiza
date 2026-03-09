"""TAJINE browser automation tools.

Provides browser automation capabilities for TAJINE:
- Web scraping with JavaScript rendering
- Form filling and submission
- CAPTCHA solving (via 2Captcha/AntiCaptcha)
- Screenshot capture for Agent Live panel

Uses Playwright for automation with stealth features.
"""

import os
from datetime import datetime
from typing import Any

from loguru import logger

from src.infrastructure.agents.tools.registry import (
    BaseTool,
    ToolCategory,
    ToolMetadata,
)


class BrowserActionTool(BaseTool):
    """Execute browser actions with visual feedback.

    Provides full browser automation with:
    - Navigation (with page load waiting)
    - Click actions (with element waiting)
    - Text input
    - Scrolling
    - Data extraction
    - CAPTCHA solving
    - Screenshot streaming to Agent Live panel
    """

    def __init__(self, screenshot_callback=None):
        """Initialize BrowserActionTool.

        Args:
            screenshot_callback: Optional callback for screenshot streaming.
                                 If None, uses WebSocket handler.
        """
        self._browser_agent = None
        self._external_callback = screenshot_callback
        self._task_id: str | None = None
        self.session_id: str | None = None

    def _get_browser_agent(self):
        """Lazy-load UnifiedBrowserAgent with WebSocket integration."""
        if self._browser_agent is None:
            from src.infrastructure.agents.browser import UnifiedBrowserAgent

            # Get callback from WebSocket handler or use external
            callback = self._external_callback
            if callback is None and self._task_id:
                try:
                    from src.interfaces.api.websocket.handlers import get_browser_handler
                    handler = get_browser_handler()
                    # Try to get session_id from associated agent if possible
                    session_id = getattr(self, 'session_id', None)
                    callback = handler.create_screenshot_callback(self._task_id, session_id=session_id)
                except Exception as e:
                    logger.warning(f"Could not get WebSocket callback: {e}")

            # Get CAPTCHA API key from environment
            captcha_key = os.environ.get("CAPTCHA_API_KEY")
            captcha_service = os.environ.get("CAPTCHA_SERVICE", "2captcha")

            # Force headful mode for VNC streaming if DISPLAY is available
            use_headless = os.environ.get("BROWSER_HEADLESS", "false").lower() == "true"

            self._browser_agent = UnifiedBrowserAgent(
                headless=use_headless,  # false = headful (VNC visible)
                screenshot_callback=callback,
                captcha_api_key=captcha_key,
                captcha_service=captcha_service,
            )

        return self._browser_agent

    def set_task_id(self, task_id: str) -> None:
        """Set task ID for WebSocket screenshot streaming."""
        self._task_id = task_id
        # Reset agent to pick up new task ID
        if self._browser_agent is not None:
            self._browser_agent = None

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="browser_action",
            description=(
                "Execute browser actions for web automation. Supports: "
                "navigate, click, type, scroll, extract, solve_captcha, screenshot. "
                "Actions are visible in Agent Live panel."
            ),
            category=ToolCategory.BROWSER,
            tags=["browser", "automation", "scraping", "playwright"],
            timeout=120.0,  # Browser actions can be slow
        )

    async def execute(
        self,
        action: str,
        url: str | None = None,
        selector: str | None = None,
        text: str | None = None,
        value: str | None = None,
        scroll_delta: int = 300,
        wait_for: str | None = None,
        timeout: int = 30000,
        **kwargs
    ) -> dict[str, Any]:
        """Execute a browser action.

        Args:
            action: Action type - one of:
                - "navigate": Go to URL (requires url)
                - "click": Click element (requires selector)
                - "type": Type text into element (requires selector, text)
                - "scroll": Scroll page (uses scroll_delta)
                - "extract": Extract text (optional selector)
                - "solve_captcha": Detect and solve CAPTCHA
                - "screenshot": Take screenshot
                - "start": Start browser session
                - "stop": Stop browser session
            url: URL to navigate to (for navigate action)
            selector: CSS/XPath selector for element
            text: Text to type (for type action)
            value: Alternative to text (for type action)
            scroll_delta: Pixels to scroll (positive=down, negative=up)
            wait_for: Selector to wait for after action
            timeout: Action timeout in milliseconds

        Returns:
            Dict with success status, screenshot, extracted data
        """
        logger.info(f"BrowserAction: action={action}, url={url}, selector={selector}")

        try:
            agent = self._get_browser_agent()

            # Handle session management
            if action == "start":
                if not agent.is_running:
                    await agent.start()
                    # Register with WebSocket handler
                    if self._task_id:
                        try:
                            from src.interfaces.api.websocket.handlers import get_browser_handler
                            get_browser_handler().register_agent(self._task_id, agent)
                        except Exception:
                            pass

                return {
                    "success": True,
                    "tool": self.metadata.name,
                    "action": "start",
                    "data": {"is_running": True},
                    "timestamp": datetime.now().isoformat(),
                }

            if action == "stop":
                if agent.is_running:
                    await agent.stop()
                    # Unregister from WebSocket handler
                    if self._task_id:
                        try:
                            from src.interfaces.api.websocket.handlers import get_browser_handler
                            get_browser_handler().unregister_agent(self._task_id)
                        except Exception:
                            pass

                return {
                    "success": True,
                    "tool": self.metadata.name,
                    "action": "stop",
                    "data": {"is_running": False},
                    "timestamp": datetime.now().isoformat(),
                }

            # Ensure browser is running for other actions
            if not agent.is_running:
                await agent.start()
                if self._task_id:
                    try:
                        from src.interfaces.api.websocket.handlers import get_browser_handler
                        get_browser_handler().register_agent(self._task_id, agent)
                    except Exception:
                        pass

            # Execute the action
            from src.infrastructure.agents.browser import BrowserAction, BrowserActionType

            action_map = {
                "navigate": BrowserActionType.NAVIGATE,
                "click": BrowserActionType.CLICK,
                "type": BrowserActionType.TYPE,
                "scroll": BrowserActionType.SCROLL,
                "extract": BrowserActionType.EXTRACT,
                "solve_captcha": BrowserActionType.SOLVE_CAPTCHA,
                "screenshot": BrowserActionType.SCREENSHOT,
                "wait": BrowserActionType.WAIT,
            }

            action_type = action_map.get(action.lower())
            if action_type is None:
                return {
                    "success": False,
                    "tool": self.metadata.name,
                    "error": f"Unknown action: {action}. Valid actions: {list(action_map.keys())}",
                }

            # Build action value
            action_value = url or text or value
            if action == "scroll":
                action_value = str(scroll_delta)
            elif action == "wait" and wait_for:
                action_value = str(timeout)  # Wait time in ms

            browser_action = BrowserAction(
                action_type=action_type,
                selector=selector if action_type != BrowserActionType.NAVIGATE else None,
                value=action_value,
                timeout=timeout,
            )

            result = await agent.execute_action(browser_action)

            # Wait for selector if specified
            if wait_for and result.success:
                wait_action = BrowserAction(
                    action_type=BrowserActionType.WAIT,
                    selector=wait_for,
                    timeout=timeout,
                )
                await agent.execute_action(wait_action)

            return {
                "success": result.success,
                "tool": self.metadata.name,
                "action": action,
                "data": {
                    "extracted_data": result.extracted_data,
                    "current_url": agent.current_url,
                    "duration_ms": result.duration_ms,
                    "has_screenshot": result.screenshot_b64 is not None,
                },
                "error": result.error,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"BrowserAction failed: {e}")
            return {
                "success": False,
                "tool": self.metadata.name,
                "error": str(e),
            }


class WebScrapeTool(BaseTool):
    """Scrape web pages with JavaScript rendering.

    Higher-level tool that combines browser actions for
    common scraping patterns.
    """

    def __init__(self):
        """Initialize WebScrapeTool."""
        self._browser_tool = None

    def _get_browser_tool(self) -> BrowserActionTool:
        """Lazy-load BrowserActionTool."""
        if self._browser_tool is None:
            self._browser_tool = BrowserActionTool()
        return self._browser_tool

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="web_scrape",
            description="Scrape web pages with JavaScript rendering. Handles dynamic content and pagination.",
            category=ToolCategory.BROWSER,
            tags=["browser", "scraping", "extraction"],
            timeout=180.0,
        )

    async def execute(
        self,
        url: str,
        extract_selector: str | None = None,
        wait_for: str | None = None,
        scroll_to_bottom: bool = False,
        solve_captcha: bool = False,
        **kwargs
    ) -> dict[str, Any]:
        """Scrape a web page.

        Args:
            url: URL to scrape
            extract_selector: CSS selector for data extraction
            wait_for: Wait for this selector before extracting
            scroll_to_bottom: Scroll to load lazy content
            solve_captcha: Attempt to solve CAPTCHA if detected

        Returns:
            Dict with extracted data and metadata
        """
        logger.info(f"WebScrape: url={url}")

        try:
            browser = self._get_browser_tool()

            # Navigate
            result = await browser.execute(
                action="navigate",
                url=url,
                wait_for=wait_for,
            )

            if not result["success"]:
                return result

            # Scroll to load lazy content
            if scroll_to_bottom:
                for _ in range(5):
                    await browser.execute(action="scroll", scroll_delta=800)

            # Solve CAPTCHA if needed
            if solve_captcha:
                captcha_result = await browser.execute(action="solve_captcha")
                if not captcha_result["success"] and captcha_result.get("error"):
                    logger.warning(f"CAPTCHA solving: {captcha_result.get('error')}")

            # Extract data
            result = await browser.execute(
                action="extract",
                selector=extract_selector,
            )

            return result

        except Exception as e:
            logger.error(f"WebScrape failed: {e}")
            return {
                "success": False,
                "tool": self.metadata.name,
                "error": str(e),
            }


def get_browser_tools() -> list[BaseTool]:
    """Get all browser automation tools."""
    return [
        BrowserActionTool(),
        WebScrapeTool(),
    ]
