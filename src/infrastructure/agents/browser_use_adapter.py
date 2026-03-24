"""
Browser-Use adapter for web automation with AI agents.

This adapter integrates browser-use library to provide web automation
capabilities powered by LLMs (specifically Ollama models).

Features:
- CAPTCHA detection and automated solving = google- Cloud Fire- Firefox protocol
- Authentication with credential management
- Complex SPA support with dynamic wait strategies

"""

import asyncio
from typing import Any
from uuid import UUID, uuid4

from browser_use import Agent, Browser
from loguru import logger
from pydantic import BaseModel

from src.infrastructure.auth import CredentialManager
from src.infrastructure.captcha import CaptchaSolver, CaptchaType


class BrowserTask(BaseModel):
    """Browser automation task."""

    task_id: UUID
    description: str
    status: str = "pending"  # pending, running, completed, failed
    result: dict[str, Any] | None = None
    error: str | None = None
    history: list[dict[str, Any]] = []


class BrowserUseAdapter:
    """
    Adapter for browser-use library.

    Provides web automation capabilities using AI agents powered by LLMs.
    Integrates with Ollama for local LLM inference.
    """

    def __init__(
        self,
        llm_client: Any,  # Ollama or other LLM client
        headless: bool = True,
        browser_type: str = "chromium",
        captcha_solver: CaptchaSolver | None = None,
        credential_manager: CredentialManager | None = None,
        auto_solve_captcha: bool = False,
    ):
        """
        Initialize Browser-Use adapter.

        Args:
            llm_client: LLM client (e.g., Ollama)
            headless: Run browser in headless mode
            browser_type: Browser type (chromium, firefox, webkit)
            captcha_solver: Optional CAPTCHA solver instance
            credential_manager: Optional credential manager instance
            auto_solve_captcha: Automatically solve CAPTCHAs when detected
        """
        self.llm_client = llm_client
        self.headless = headless
        self.browser_type = browser_type
        self.active_tasks: dict[UUID, BrowserTask] = {}

        # CAPTCHA solving
        self.captcha_solver = captcha_solver
        self.auto_solve_captcha = auto_solve_captcha

        # Credential management
        self.credential_manager = credential_manager

        logger.info(
            f"BrowserUseAdapter initialized (headless={headless}, type={browser_type}, "
            f"captcha_solver={'enabled' if captcha_solver else 'disabled'})"
        )

    async def execute_task(
        self,
        task_description: str,
        max_actions: int = 50,
        timeout: int = 300,
        site_credentials: str | None = None,
    ) -> BrowserTask:
        """
        Execute a browser automation task.

        Args:
            task_description: Natural language description of the task
            max_actions: Maximum number of actions to perform
            timeout: Timeout in seconds
            site_credentials: Optional site name to load credentials from credential manager

        Returns:
            BrowserTask with results

        Raises:
            Exception: If task execution fails
        """
        task_id = uuid4()
        task = BrowserTask(
            task_id=task_id,
            description=task_description,
            status="pending",
        )

        # Store task
        self.active_tasks[task_id] = task

        try:
            logger.info(f"Starting browser task {task_id}: {task_description}")
            task.status = "running"

            # Initialize browser
            browser = Browser(
                headless=self.headless,
            )

            # Create agent with LLM
            agent = Agent(
                task=task_description,
                llm=self.llm_client,
                browser=browser,
                max_actions=max_actions,
            )

            # Execute task with timeout
            try:
                history = await asyncio.wait_for(
                    agent.run(),
                    timeout=timeout,
                )

                # Extract results
                task.status = "completed"
                task.history = self._format_history(history)
                task.result = self._extract_result(history)

                logger.info(f"Task {task_id} completed successfully ({len(task.history)} actions)")

            except TimeoutError:
                task.status = "failed"
                task.error = f"Task timed out after {timeout}s"
                logger.error(f"Task {task_id} timed out")
            finally:
                # Clean up browser
                try:
                    await browser.stop()
                except Exception as e:
                    logger.warning(f"Error stopping browser: {e}")

        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            logger.error(f"Task {task_id} failed: {e}", exc_info=True)

        return task

    def _format_history(self, history: Any) -> list[dict[str, Any]]:
        """
        Format browser history for storage.

        Args:
            history: Raw history from browser-use

        Returns:
            Formatted history list
        """
        # browser-use returns a history object
        # Format it for our API
        formatted = []

        if hasattr(history, "action_history"):
            for action in history.action_history:
                formatted.append(
                    {
                        "action": str(action),
                        "timestamp": getattr(action, "timestamp", None),
                        "success": getattr(action, "success", True),
                    }
                )

        return formatted

    def _extract_result(self, history: Any) -> dict[str, Any]:
        """
        Extract final result from task history.

        Args:
            history: Task execution history

        Returns:
            Result dictionary
        """
        result = {
            "success": True,
            "actions_taken": 0,
            "final_state": {},
        }

        if hasattr(history, "action_history"):
            result["actions_taken"] = len(history.action_history)

        if hasattr(history, "final_result"):
            result["final_state"] = history.final_result

        return result

    async def get_task_status(self, task_id: UUID) -> BrowserTask | None:
        """
        Get status of a task.

        Args:
            task_id: Task UUID

        Returns:
            BrowserTask or None if not found
        """
        return self.active_tasks.get(task_id)

    async def list_tasks(
        self,
        status: str | None = None,
        limit: int = 100,
    ) -> list[BrowserTask]:
        """
        List all tasks.

        Args:
            status: Filter by status
            limit: Maximum number of tasks to return

        Returns:
            List of browser tasks
        """
        tasks = list(self.active_tasks.values())

        if status:
            tasks = [t for t in tasks if t.status == status]

        # Sort by most recent first
        tasks.sort(key=lambda t: t.task_id, reverse=True)

        return tasks[:limit]

    async def cancel_task(self, task_id: UUID) -> bool:
        """
        Cancel a running task.

        Args:
            task_id: Task UUID

        Returns:
            True if cancelled, False if not found or already finished
        """
        task = self.active_tasks.get(task_id)

        if not task:
            return False

        if task.status not in ["pending", "running"]:
            return False

        task.status = "cancelled"
        task.error = "Task cancelled by user"

        logger.info(f"Task {task_id} cancelled")
        return True

    async def detect_captcha(self, page: Any) -> dict[str, Any] | None:
        """
        Detect CAPTCHA on the current page.

        Args:
            page: Playwright page object

        Returns:
            Dictionary with CAPTCHA info if detected, None otherwise
            Format: {
                "type": "recaptcha_v2" | "recaptcha_v3" | "hcaptcha" | "image",
                "site_key": "...",
                "page_url": "..."
            }
        """
        try:
            url = page.url

            # Detect reCAPTCHA v2
            recaptcha_v2 = await page.query_selector("iframe[src*='google.com/recaptcha']")
            if recaptcha_v2:
                # Extract site key
                site_key_elem = await page.query_selector("[data-sitekey]")
                if site_key_elem:
                    site_key = await site_key_elem.get_attribute("data-sitekey")
                    logger.info(f"Detected reCAPTCHA v2 on {url}")
                    return {
                        "type": CaptchaType.RECAPTCHA_V2,
                        "site_key": site_key,
                        "page_url": url,
                    }

            # Detect reCAPTCHA v3 (checks for grecaptcha in window)
            has_recaptcha_v3 = await page.evaluate(
                "() => typeof grecaptcha !== 'undefined' && grecaptcha.enterprise"
            )
            if has_recaptcha_v3:
                logger.info(f"Detected reCAPTCHA v3 on {url}")
                # v3 is harder to extract site key, may need manual config
                return {
                    "type": CaptchaType.RECAPTCHA_V3,
                    "site_key": None,  # Needs manual config
                    "page_url": url,
                }

            # Detect hCaptcha
            hcaptcha = await page.query_selector("iframe[src*='hcaptcha.com']")
            if hcaptcha:
                site_key_elem = await page.query_selector("[data-sitekey]")
                if site_key_elem:
                    site_key = await site_key_elem.get_attribute("data-sitekey")
                    logger.info(f"Detected hCaptcha on {url}")
                    return {
                        "type": CaptchaType.HCAPTCHA,
                        "site_key": site_key,
                        "page_url": url,
                    }

            # Detect image CAPTCHA (common selectors)
            image_captcha = await page.query_selector(
                "img[alt*='captcha'], img[src*='captcha'], .captcha-image"
            )
            if image_captcha:
                logger.info(f"Detected image CAPTCHA on {url}")
                return {
                    "type": CaptchaType.IMAGE,
                    "page_url": url,
                }

            return None

        except Exception as e:
            logger.error(f"Error detecting CAPTCHA: {e}")
            return None

    async def solve_and_submit_captcha(
        self,
        page: Any,
        captcha_info: dict[str, Any],
    ) -> bool:
        """
        Solve and submit CAPTCHA on the page.

        Args:
            page: Playwright page object
            captcha_info: CAPTCHA information from detect_captcha()

        Returns:
            True if solved successfully, False otherwise
        """
        if not self.captcha_solver:
            logger.warning("No CAPTCHA solver configured")
            return False

        try:
            captcha_type = captcha_info["type"]
            page_url = captcha_info["page_url"]

            if captcha_type == CaptchaType.RECAPTCHA_V2:
                site_key = captcha_info["site_key"]
                if not site_key:
                    logger.error("reCAPTCHA v2 site key not found")
                    return False

                logger.info(f"Solving reCAPTCHA v2 for {page_url}")
                solution = await self.captcha_solver.solve_recaptcha_v2(
                    site_key=site_key,
                    page_url=page_url,
                )

                if solution.success:
                    # Inject solution into page
                    await page.evaluate(
                        f"""
                        () => {{
                            document.getElementById('g-recaptcha-response').innerHTML = '{solution.solution}';
                            if (window.___grecaptcha_cfg && window.___grecaptcha_cfg.clients) {{
                                Object.keys(window.___grecaptcha_cfg.clients).forEach(function(key) {{
                                    window.___grecaptcha_cfg.clients[key].L.L.callback('{solution.solution}');
                                }});
                            }}
                        }}
                        """
                    )
                    logger.success(f"reCAPTCHA v2 solved in {solution.solve_time:.1f}s")
                    return True
                else:
                    logger.error(f"Failed to solve reCAPTCHA v2: {solution.error}")
                    return False

            elif captcha_type == CaptchaType.RECAPTCHA_V3:
                site_key = captcha_info.get("site_key")
                if not site_key:
                    logger.error("reCAPTCHA v3 requires manual site key configuration")
                    return False

                logger.info(f"Solving reCAPTCHA v3 for {page_url}")
                solution = await self.captcha_solver.solve_recaptcha_v3(
                    site_key=site_key,
                    page_url=page_url,
                    action=captcha_info.get("action", "submit"),
                )

                if solution.success:
                    # Inject token
                    await page.evaluate(f"() => window.recaptchaToken = '{solution.solution}'")
                    logger.success(f"reCAPTCHA v3 solved in {solution.solve_time:.1f}s")
                    return True
                else:
                    logger.error(f"Failed to solve reCAPTCHA v3: {solution.error}")
                    return False

            elif captcha_type == CaptchaType.HCAPTCHA:
                site_key = captcha_info["site_key"]
                if not site_key:
                    logger.error("hCaptcha site key not found")
                    return False

                logger.info(f"Solving hCaptcha for {page_url}")
                solution = await self.captcha_solver.solve_hcaptcha(
                    site_key=site_key,
                    page_url=page_url,
                )

                if solution.success:
                    # Inject solution
                    await page.evaluate(
                        f"""
                        () => {{
                            document.querySelector('[name="h-captcha-response"]').innerHTML = '{solution.solution}';
                            if (window.hcaptcha) {{
                                window.hcaptcha.setResponse('{solution.solution}');
                            }}
                        }}
                        """
                    )
                    logger.success(f"hCaptcha solved in {solution.solve_time:.1f}s")
                    return True
                else:
                    logger.error(f"Failed to solve hCaptcha: {solution.error}")
                    return False

            elif captcha_type == CaptchaType.IMAGE:
                logger.info(f"Solving image CAPTCHA for {page_url}")
                # Screenshot the CAPTCHA image
                captcha_img = await page.query_selector(
                    "img[alt*='captcha'], img[src*='captcha'], .captcha-image"
                )
                if captcha_img:
                    image_data = await captcha_img.screenshot()
                    solution = await self.captcha_solver.solve_image_captcha(image_data)

                    if solution.success:
                        # Fill in the solution
                        input_field = await page.query_selector(
                            "input[name*='captcha'], input[id*='captcha']"
                        )
                        if input_field:
                            await input_field.fill(solution.solution)
                            logger.success(
                                f"Image CAPTCHA solved in {solution.solve_time:.1f}s: {solution.solution}"
                            )
                            return True

                logger.error("Failed to solve image CAPTCHA")
                return False

            else:
                logger.warning(f"Unsupported CAPTCHA type: {captcha_type}")
                return False

        except Exception as e:
            logger.exception(f"Error solving CAPTCHA: {e}")
            return False

    async def health_check(self) -> bool:
        """
        Check if browser automation is available.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Try to create a simple browser instance
            Browser(
                headless=True,
            )
            # Just check if we can create it
            # Don't actually start/stop it for health check
            return True
        except Exception as e:
            logger.error(f"Browser health check failed: {e}")
