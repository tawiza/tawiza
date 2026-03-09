"""
UnifiedBrowserAgent - Playwright-based browser automation with screenshot streaming.

This agent provides visible browser automation for TAJINE, streaming screenshots
to the Agent Live panel instead of requiring VNC.
"""

import asyncio
import base64
import contextlib
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class BrowserActionType(Enum):
    """Types of browser actions."""
    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    SCROLL = "scroll"
    SCREENSHOT = "screenshot"
    WAIT = "wait"
    EXTRACT = "extract"
    SOLVE_CAPTCHA = "solve_captcha"


@dataclass
class BrowserAction:
    """A browser action to execute."""
    action_type: BrowserActionType
    selector: str | None = None
    value: str | None = None
    timeout: int = 30000
    metadata: dict = field(default_factory=dict)


@dataclass
class ActionResult:
    """Result of a browser action."""
    success: bool
    action_type: BrowserActionType
    screenshot_b64: str | None = None
    extracted_data: Any | None = None
    error: str | None = None
    duration_ms: int = 0


class CaptchaSolver:
    """CAPTCHA solving integration for 2Captcha/AntiCaptcha."""

    def __init__(self, api_key: str | None = None, service: str = "2captcha"):
        self.api_key = api_key
        self.service = service
        self._solver = None

    async def solve_recaptcha(self, site_key: str, page_url: str) -> str | None:
        """Solve reCAPTCHA v2 and return the solution token."""
        if not self.api_key:
            logger.warning("No CAPTCHA API key configured")
            return None

        try:
            if self.service == "2captcha":
                return await self._solve_2captcha(site_key, page_url)
            elif self.service == "anticaptcha":
                return await self._solve_anticaptcha(site_key, page_url)
            else:
                logger.error(f"Unknown CAPTCHA service: {self.service}")
                return None
        except Exception as e:
            logger.error(f"CAPTCHA solving failed: {e}")
            return None

    async def _solve_2captcha(self, site_key: str, page_url: str) -> str | None:
        """Solve using 2Captcha API."""
        import httpx

        # Submit CAPTCHA
        async with httpx.AsyncClient() as client:
            submit_resp = await client.post(
                "https://2captcha.com/in.php",
                data={
                    "key": self.api_key,
                    "method": "userrecaptcha",
                    "googlekey": site_key,
                    "pageurl": page_url,
                    "json": 1
                }
            )
            result = submit_resp.json()
            if result.get("status") != 1:
                logger.error(f"2Captcha submit failed: {result}")
                return None

            captcha_id = result["request"]

            # Poll for solution
            for _ in range(60):  # Max 2 minutes
                await asyncio.sleep(2)
                check_resp = await client.get(
                    "https://2captcha.com/res.php",
                    params={
                        "key": self.api_key,
                        "action": "get",
                        "id": captcha_id,
                        "json": 1
                    }
                )
                result = check_resp.json()
                if result.get("status") == 1:
                    return result["request"]
                elif result.get("request") != "CAPCHA_NOT_READY":
                    logger.error(f"2Captcha error: {result}")
                    return None

            return None

    async def _solve_anticaptcha(self, site_key: str, page_url: str) -> str | None:
        """Solve using AntiCaptcha API."""
        import httpx

        async with httpx.AsyncClient() as client:
            # Create task
            create_resp = await client.post(
                "https://api.anti-captcha.com/createTask",
                json={
                    "clientKey": self.api_key,
                    "task": {
                        "type": "RecaptchaV2TaskProxyless",
                        "websiteURL": page_url,
                        "websiteKey": site_key
                    }
                }
            )
            result = create_resp.json()
            if result.get("errorId") != 0:
                logger.error(f"AntiCaptcha create failed: {result}")
                return None

            task_id = result["taskId"]

            # Poll for solution
            for _ in range(60):
                await asyncio.sleep(2)
                check_resp = await client.post(
                    "https://api.anti-captcha.com/getTaskResult",
                    json={
                        "clientKey": self.api_key,
                        "taskId": task_id
                    }
                )
                result = check_resp.json()
                if result.get("status") == "ready":
                    return result["solution"]["gRecaptchaResponse"]
                elif result.get("errorId") != 0:
                    logger.error(f"AntiCaptcha error: {result}")
                    return None

            return None


class UnifiedBrowserAgent:
    """
    Playwright-based browser agent with screenshot streaming.

    Instead of VNC, this agent:
    1. Uses Playwright for browser automation
    2. Takes screenshots after each action
    3. Streams screenshots to frontend via callback
    """

    def __init__(
        self,
        headless: bool = True,
        screenshot_callback: Callable[[str, str], None] | None = None,
        captcha_api_key: str | None = None,
        captcha_service: str = "2captcha"
    ):
        """
        Initialize browser agent.

        Args:
            headless: Run browser in headless mode
            screenshot_callback: Called with (action_name, base64_screenshot) after each action
            captcha_api_key: API key for CAPTCHA solving service
            captcha_service: "2captcha" or "anticaptcha"
        """
        self.headless = headless
        self.screenshot_callback = screenshot_callback
        self.captcha_solver = CaptchaSolver(captcha_api_key, captcha_service)

        self._browser = None
        self._context = None
        self._page = None
        self._playwright = None

    async def start(self) -> None:
        """Start the browser."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError("playwright not installed. Run: pip install playwright && playwright install chromium")

        # For WebSocket screenshot streaming, headless mode is preferred
        # Only use headful mode if DISPLAY is explicitly available and valid
        if not self.headless:
            display = os.getenv("DISPLAY")
            if display:
                # Check if X server is available
                import subprocess
                try:
                    result = subprocess.run(
                        ["xdpyinfo", "-display", display],
                        capture_output=True,
                        timeout=2
                    )
                    if result.returncode != 0:
                        logger.warning(f"DISPLAY={display} not available, falling back to headless mode")
                        self.headless = True
                    else:
                        logger.info(f"Using DISPLAY={display} for visible browser")
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    logger.warning("X server check failed, falling back to headless mode")
                    self.headless = True
            else:
                logger.info("No DISPLAY available, using headless mode with WebSocket screenshot streaming")
                self.headless = True

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-gpu" if self.headless else "--enable-gpu"
            ]
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self._page = await self._context.new_page()

        # Anti-detection scripts
        await self._inject_stealth_scripts()

        logger.info("Browser started successfully")

    async def stop(self) -> None:
        """Stop the browser."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

        self._browser = None
        self._context = None
        self._page = None
        self._playwright = None

        logger.info("Browser stopped")

    async def _inject_stealth_scripts(self) -> None:
        """Inject anti-detection scripts."""
        await self._page.add_init_script("""
            // Hide webdriver flag
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['fr-FR', 'fr', 'en-US', 'en']
            });

            // Mock chrome runtime
            window.chrome = {
                runtime: {}
            };
        """)

    async def execute_action(self, action: BrowserAction) -> ActionResult:
        """Execute a browser action and return result with screenshot."""
        if not self._page:
            return ActionResult(
                success=False,
                action_type=action.action_type,
                error="Browser not started. Call start() first."
            )

        start_time = datetime.now()

        try:
            result = await self._execute_action_internal(action)

            # Take screenshot after action
            screenshot_b64 = await self._take_screenshot()
            result.screenshot_b64 = screenshot_b64

            # Notify callback
            if self.screenshot_callback and screenshot_b64:
                self.screenshot_callback(action.action_type.value, screenshot_b64, self._page.url)

            result.duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            return result

        except Exception as e:
            logger.error(f"Action {action.action_type} failed: {e}")

            # Still try to get screenshot on error
            screenshot_b64 = None
            with contextlib.suppress(Exception):
                screenshot_b64 = await self._take_screenshot()

            # Notify callback even on error
            if self.screenshot_callback and screenshot_b64:
                self.screenshot_callback(action.action_type.value, screenshot_b64, getattr(self._page, 'url', None))

    async def _execute_action_internal(self, action: BrowserAction) -> ActionResult:
        """Internal action execution without screenshot handling."""

        if action.action_type == BrowserActionType.NAVIGATE:
            await self._page.goto(action.value, wait_until="domcontentloaded", timeout=action.timeout)
            return ActionResult(success=True, action_type=action.action_type)

        elif action.action_type == BrowserActionType.CLICK:
            await self._page.click(action.selector, timeout=action.timeout)
            return ActionResult(success=True, action_type=action.action_type)

        elif action.action_type == BrowserActionType.TYPE:
            await self._page.fill(action.selector, action.value, timeout=action.timeout)
            return ActionResult(success=True, action_type=action.action_type)

        elif action.action_type == BrowserActionType.SCROLL:
            delta = int(action.value) if action.value else 300
            await self._page.mouse.wheel(0, delta)
            await asyncio.sleep(0.5)  # Wait for scroll animation
            return ActionResult(success=True, action_type=action.action_type)

        elif action.action_type == BrowserActionType.SCREENSHOT:
            # Just take screenshot, handled by wrapper
            return ActionResult(success=True, action_type=action.action_type)

        elif action.action_type == BrowserActionType.WAIT:
            if action.selector:
                await self._page.wait_for_selector(action.selector, timeout=action.timeout)
            else:
                await asyncio.sleep(float(action.value) / 1000 if action.value else 1)
            return ActionResult(success=True, action_type=action.action_type)

        elif action.action_type == BrowserActionType.EXTRACT:
            if action.selector:
                elements = await self._page.query_selector_all(action.selector)
                data = []
                for el in elements:
                    text = await el.text_content()
                    data.append(text.strip() if text else "")
                return ActionResult(success=True, action_type=action.action_type, extracted_data=data)
            else:
                # Extract full page text
                text = await self._page.inner_text("body")
                return ActionResult(success=True, action_type=action.action_type, extracted_data=text)

        elif action.action_type == BrowserActionType.SOLVE_CAPTCHA:
            solved = await self._solve_captcha()
            return ActionResult(success=solved, action_type=action.action_type)

        else:
            return ActionResult(
                success=False,
                action_type=action.action_type,
                error=f"Unknown action type: {action.action_type}"
            )

    async def _take_screenshot(self) -> str | None:
        """Take a screenshot and return as base64."""
        try:
            screenshot_bytes = await self._page.screenshot(type="png")
            return base64.b64encode(screenshot_bytes).decode("utf-8")
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return None

    async def _solve_captcha(self) -> bool:
        """Detect and solve CAPTCHA on current page."""
        # Check for reCAPTCHA
        recaptcha = await self._page.query_selector('iframe[src*="recaptcha"]')
        if not recaptcha:
            recaptcha = await self._page.query_selector('.g-recaptcha')

        if not recaptcha:
            logger.info("No CAPTCHA detected on page")
            return True

        # Get site key
        site_key = await self._page.evaluate("""
            () => {
                const el = document.querySelector('.g-recaptcha');
                return el ? el.getAttribute('data-sitekey') : null;
            }
        """)

        if not site_key:
            logger.error("Could not find reCAPTCHA site key")
            return False

        # Solve CAPTCHA
        page_url = self._page.url
        solution = await self.captcha_solver.solve_recaptcha(site_key, page_url)

        if not solution:
            logger.error("CAPTCHA solving failed")
            return False

        # Inject solution using .value (safe, not innerHTML)
        # g-recaptcha-response is a textarea, so we use .value
        await self._page.evaluate("""
            (solution) => {
                const responseField = document.getElementById('g-recaptcha-response');
                if (responseField) {
                    responseField.value = solution;
                }
                // Also try to trigger callback if exists
                if (typeof ___grecaptcha_cfg !== 'undefined') {
                    const clients = ___grecaptcha_cfg.clients;
                    if (clients) {
                        Object.keys(clients).forEach(key => {
                            const client = clients[key];
                            if (client && client.callback) {
                                client.callback(solution);
                            }
                        });
                    }
                }
            }
        """, solution)

        logger.info("CAPTCHA solved and injected")
        return True

    async def execute_task(
        self,
        task: str,
        actions: list[BrowserAction]
    ) -> list[ActionResult]:
        """
        Execute a sequence of browser actions.

        Args:
            task: Description of the task (for logging)
            actions: List of actions to execute

        Returns:
            List of action results
        """
        logger.info(f"Starting browser task: {task}")
        results = []

        for i, action in enumerate(actions):
            logger.info(f"Executing action {i+1}/{len(actions)}: {action.action_type.value}")
            result = await self.execute_action(action)
            results.append(result)

            if not result.success:
                logger.warning(f"Action failed: {result.error}")
                # Continue with remaining actions unless critical
                if action.action_type in [BrowserActionType.NAVIGATE]:
                    break

        logger.info(f"Task completed: {sum(r.success for r in results)}/{len(results)} actions succeeded")
        return results

    # Convenience methods
    async def navigate(self, url: str) -> ActionResult:
        """Navigate to URL."""
        return await self.execute_action(BrowserAction(
            action_type=BrowserActionType.NAVIGATE,
            value=url
        ))

    async def click(self, selector: str) -> ActionResult:
        """Click an element."""
        return await self.execute_action(BrowserAction(
            action_type=BrowserActionType.CLICK,
            selector=selector
        ))

    async def type_text(self, selector: str, text: str) -> ActionResult:
        """Type text into an element."""
        return await self.execute_action(BrowserAction(
            action_type=BrowserActionType.TYPE,
            selector=selector,
            value=text
        ))

    async def extract(self, selector: str | None = None) -> ActionResult:
        """Extract text from page or specific elements."""
        return await self.execute_action(BrowserAction(
            action_type=BrowserActionType.EXTRACT,
            selector=selector
        ))

    async def screenshot(self) -> ActionResult:
        """Take a screenshot."""
        return await self.execute_action(BrowserAction(
            action_type=BrowserActionType.SCREENSHOT
        ))

    @property
    def current_url(self) -> str | None:
        """Get current page URL."""
        return self._page.url if self._page else None

    @property
    def is_running(self) -> bool:
        """Check if browser is running."""
        return self._browser is not None


# Export for TAJINE integration
__all__ = [
    "UnifiedBrowserAgent",
    "BrowserAction",
    "BrowserActionType",
    "ActionResult",
    "CaptchaSolver"
]
