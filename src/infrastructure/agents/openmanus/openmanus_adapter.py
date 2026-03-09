"""OpenManus agent adapter implementation.

This adapter provides web automation using Playwright and LLM guidance.
OpenManus-style agent that can:
- Navigate web pages
- Extract data using AI
- Fill forms
- Take screenshots
- Interact with web elements
"""

import asyncio
import json
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from loguru import logger
from playwright.async_api import Browser, Page, Playwright, async_playwright

from src.application.ports.agent_ports import AgentExecutionError, AgentType, TaskStatus
from src.infrastructure.agents.base_agent import BaseAgent


class OpenManusAdapter(BaseAgent):
    """OpenManus agent adapter for web automation.

    Provides intelligent web automation using:
    - Playwright for browser control
    - BeautifulSoup for HTML parsing
    - LLM (Ollama) for intelligent decision making
    """

    def __init__(
        self,
        headless: bool = True,
        screenshots_dir: str = "/tmp/tawiza-screenshots",
        llm_client: Any | None = None
    ) -> None:
        """Initialize OpenManus adapter.

        Args:
            headless: Run browser in headless mode
            screenshots_dir: Directory for screenshots
            llm_client: Optional LLM client for AI guidance
        """
        super().__init__(AgentType.OPENMANUS)

        self.headless = headless
        self.screenshots_dir = Path(screenshots_dir)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.llm_client = llm_client

        self.playwright: Playwright | None = None
        self.browser: Browser | None = None

        logger.info(
            f"Initialized OpenManus adapter "
            f"(headless={headless}, screenshots={screenshots_dir})"
        )

    async def _ensure_browser(self) -> Browser:
        """Ensure browser is running."""
        if not self.browser:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless
            )
            logger.info("Started Chromium browser")

        return self.browser

    async def _close_browser(self) -> None:
        """Close browser if running."""
        if self.browser:
            await self.browser.close()
            self.browser = None
            logger.info("Closed browser")

        if self.playwright:
            await self.playwright.stop()
            self.playwright = None

    async def execute_task(
        self,
        task_config: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute web automation task.

        Args:
            task_config: Task configuration:
                - url: Target URL
                - action: Action type (navigate, extract, fill_form, click)
                - selectors: CSS selectors for elements
                - data: Data for actions (e.g., form fields)
                - options: Additional options

        Returns:
            Task result with extracted data and screenshots

        Example task configs:
            Navigate:
                {"url": "https://example.com", "action": "navigate"}

            Extract data:
                {
                    "url": "https://news.ycombinator.com",
                    "action": "extract",
                    "data": {
                        "target": "top 5 article titles"
                    }
                }

            Fill form:
                {
                    "url": "https://example.com/form",
                    "action": "fill_form",
                    "selectors": {
                        "name": "#name-input",
                        "email": "#email-input"
                    },
                    "data": {
                        "name": "John Doe",
                        "email": "john@example.com"
                    }
                }
        """
        task_id = self._create_task(task_config)

        try:
            self._update_task(task_id, {"status": TaskStatus.RUNNING})
            self._add_log(task_id, "Starting task execution")
            self._update_progress(task_id, 10, "Initializing browser")

            # Ensure browser is running
            browser = await self._ensure_browser()
            page = await browser.new_page()

            try:
                # Extract config
                url = task_config.get("url")
                action = task_config.get("action", "navigate")

                if not url:
                    raise AgentExecutionError("URL is required")

                # Navigate to URL
                self._update_progress(task_id, 20, f"Navigating to {url}")
                self._add_log(task_id, f"Navigating to {url}")

                # Try networkidle first, fall back to domcontentloaded for slow sites
                try:
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                except Exception as e:
                    logger.warning(f"Navigation with networkidle failed, retrying with domcontentloaded: {e}")
                    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    # Wait a bit for dynamic content
                    await page.wait_for_timeout(2000)

                # Take initial screenshot
                _screenshot_path = await self._take_screenshot(
                    page,
                    task_id,
                    "initial"
                )

                # Execute action
                self._update_progress(task_id, 40, f"Executing action: {action}")

                result = None

                if action == "navigate":
                    result = await self._action_navigate(page, task_config)

                elif action == "extract":
                    result = await self._action_extract(page, task_config, task_id)

                elif action == "fill_form":
                    result = await self._action_fill_form(page, task_config, task_id)

                elif action == "click":
                    result = await self._action_click(page, task_config, task_id)

                else:
                    raise AgentExecutionError(f"Unknown action: {action}")

                # Take final screenshot
                await self._take_screenshot(page, task_id, "final")

                # Mark as completed
                self._update_progress(task_id, 100, "Completed")
                self._update_task(task_id, {
                    "status": TaskStatus.COMPLETED,
                    "result": result
                })

                self._add_log(task_id, "Task completed successfully")

                return await self.get_task_result(task_id)

            finally:
                await page.close()

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}", exc_info=True)
            self._update_task(task_id, {
                "status": TaskStatus.FAILED,
                "error": str(e)
            })
            self._add_log(task_id, f"Task failed: {e}", level="error")

            raise AgentExecutionError(f"Task execution failed: {e}") from e

    async def _take_screenshot(
        self,
        page: Page,
        task_id: str,
        label: str
    ) -> str:
        """Take screenshot and save it."""
        filename = f"{task_id}_{label}.png"
        filepath = self.screenshots_dir / filename

        await page.screenshot(path=str(filepath), full_page=False)

        screenshot_url = f"/screenshots/{filename}"
        self._add_screenshot(task_id, screenshot_url, label)

        logger.debug(f"Saved screenshot: {filepath}")

        return screenshot_url

    async def _action_navigate(
        self,
        page: Page,
        config: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute navigate action."""
        return {
            "action": "navigate",
            "url": page.url,
            "title": await page.title(),
            "status": "success"
        }

    async def _action_extract(
        self,
        page: Page,
        config: dict[str, Any],
        task_id: str
    ) -> dict[str, Any]:
        """Extract data from page.

        Uses BeautifulSoup for parsing and optionally LLM for guidance.
        """
        self._update_progress(task_id, 50, "Extracting page content")

        # Get page HTML
        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')

        # Extract based on target
        target = config.get("data", {}).get("target", "")
        selectors = config.get("selectors", {})

        extracted_data = {}

        if selectors:
            # Extract using selectors
            for key, selector in selectors.items():
                elements = soup.select(selector)
                extracted_data[key] = [elem.get_text(strip=True) for elem in elements]

        else:
            # Extract all text
            extracted_data = {
                "title": await page.title(),
                "url": page.url,
                "text": soup.get_text(strip=True)[:1000],  # First 1000 chars
                "links": [
                    {"text": a.get_text(strip=True), "href": a.get("href")}
                    for a in soup.find_all('a', href=True)[:10]  # First 10 links
                ]
            }

        self._update_progress(task_id, 80, "Data extracted")

        return {
            "action": "extract",
            "target": target,
            "data": extracted_data,
            "status": "success"
        }

    async def _action_fill_form(
        self,
        page: Page,
        config: dict[str, Any],
        task_id: str
    ) -> dict[str, Any]:
        """Fill form with provided data."""
        selectors = config.get("selectors", {})
        data = config.get("data", {})

        filled_fields = []

        for field_name, value in data.items():
            selector = selectors.get(field_name)

            if not selector:
                logger.warning(f"No selector for field: {field_name}")
                continue

            try:
                await page.fill(selector, str(value))
                filled_fields.append(field_name)
                self._add_log(task_id, f"Filled field: {field_name}")

            except Exception as e:
                logger.error(f"Failed to fill {field_name}: {e}")
                self._add_log(
                    task_id,
                    f"Failed to fill {field_name}: {e}",
                    level="error"
                )

        # Take screenshot after filling
        await self._take_screenshot(page, task_id, "form_filled")

        # Optional: submit form
        if config.get("submit"):
            submit_selector = config.get("submit_selector", "button[type='submit']")

            try:
                await page.click(submit_selector)
                await page.wait_for_load_state("networkidle", timeout=10000)
                await self._take_screenshot(page, task_id, "form_submitted")

                return {
                    "action": "fill_form",
                    "filled_fields": filled_fields,
                    "submitted": True,
                    "status": "success"
                }

            except Exception as e:
                logger.error(f"Failed to submit form: {e}")

        return {
            "action": "fill_form",
            "filled_fields": filled_fields,
            "submitted": False,
            "status": "success"
        }

    async def _action_click(
        self,
        page: Page,
        config: dict[str, Any],
        task_id: str
    ) -> dict[str, Any]:
        """Click element."""
        selector = config.get("selector")

        if not selector:
            raise AgentExecutionError("Selector is required for click action")

        await page.click(selector)
        await page.wait_for_load_state("networkidle", timeout=10000)

        await self._take_screenshot(page, task_id, "after_click")

        return {
            "action": "click",
            "selector": selector,
            "url": page.url,
            "title": await page.title(),
            "status": "success"
        }

    async def cleanup(self) -> None:
        """Cleanup resources."""
        await self._close_browser()
        logger.info("OpenManus adapter cleaned up")

    # IAgent interface implementation
    @property
    def name(self) -> str:
        """Get agent name."""
        return f"openmanus-{id(self)}"

    async def initialize(self) -> None:
        """Initialize the agent and its resources.

        Starts the browser in preparation for task execution.
        """
        await self._ensure_browser()
        logger.info(f"OpenManus agent initialized (headless={self.headless})")

    async def health_check(self) -> bool:
        """Check if the agent is operational.

        Verifies Playwright and browser are available.

        Returns:
            True if the agent can execute tasks, False otherwise.
        """
        try:
            browser = await self._ensure_browser()
            # Try to create and close a page to verify browser works
            page = await browser.new_page()
            await page.close()
            return True
        except Exception as e:
            logger.warning(f"OpenManus health check failed: {e}")
            return False

    async def shutdown(self) -> None:
        """Release agent resources.

        Closes the browser and stops Playwright.
        """
        await self._close_browser()
        logger.info("OpenManus agent shutdown complete")


# Convenience function for quick testing
async def test_openmanus():
    """Test OpenManus adapter."""
    agent = OpenManusAdapter(headless=True)

    try:
        # Test navigation
        result = await agent.execute_task({
            "url": "https://example.com",
            "action": "navigate"
        })

        print("Navigation result:", json.dumps(result, indent=2))

        # Test extraction
        result = await agent.execute_task({
            "url": "https://example.com",
            "action": "extract",
            "data": {
                "target": "page content"
            }
        })

        print("Extraction result:", json.dumps(result, indent=2))

    finally:
        await agent.cleanup()


if __name__ == "__main__":
    asyncio.run(test_openmanus())
