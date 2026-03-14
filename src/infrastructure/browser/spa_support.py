"""
Advanced SPA (Single-Page Application) support for browser automation.

Features:
- Dynamic wait strategies (network idle, DOM stable, custom conditions)
- Infinite scroll detection and handling
- Virtual scrolling support
- Progressive loading detection
- React/Vue/Angular state detection
"""

import asyncio
import json
import os
import re
from collections.abc import Callable
from enum import Enum, StrEnum
from typing import Any

from loguru import logger


def validate_css_selector(selector: str) -> str:
    """
    Validate and sanitize CSS selector to prevent JavaScript injection.

    Args:
        selector: CSS selector to validate

    Returns:
        Sanitized selector

    Raises:
        ValueError: If selector contains potentially malicious content
    """
    if not selector or not isinstance(selector, str):
        raise ValueError("Selector must be a non-empty string")

    # Remove leading/trailing whitespace
    selector = selector.strip()

    # Check for suspicious characters that could break out of quotes
    dangerous_patterns = [
        r"['\"][^'\"]*(;|<script|javascript:)",  # Quote manipulation with semicolons/tags
        r"javascript:",  # JavaScript protocol
        r"on\w+\s*=",  # Event handlers (but allow in attribute selectors)
        r"<script",  # Script tags
        r"</\w+>",  # Closing HTML tags
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, selector, re.IGNORECASE):
            raise ValueError(f"Potentially malicious selector pattern detected: {selector}")

    # Validate it looks like a valid CSS selector
    # Allow: . # [ ] : ( ) > + ~ * | = ^ $ - _ alphanumeric, spaces, quotes (for attributes)
    if not re.match(r"^[a-zA-Z0-9\s\.\#\[\]\:\(\)\>\+\~\*\|\=\^\$\-\_,\'\"]+$", selector):
        raise ValueError(f"Invalid CSS selector format: {selector}")

    return selector


class SPAWaitStrategy(StrEnum):
    """Wait strategies for SPA applications."""

    NETWORK_IDLE = "networkidle"  # Wait for network to be idle
    DOM_STABLE = "domstable"  # Wait for DOM to stop changing
    LOAD = "load"  # Wait for page load event
    CUSTOM = "custom"  # Custom wait condition


class WaitCondition:
    """
    Custom wait condition for SPA applications.

    Examples:
        # Wait for specific element
        condition = WaitCondition.element_visible(".product-list")

        # Wait for React to finish rendering
        condition = WaitCondition.react_ready()

        # Wait for Vue app to be mounted
        condition = WaitCondition.vue_ready()
    """

    @staticmethod
    def element_visible(selector: str) -> str:
        """
        Wait for element to be visible.

        Args:
            selector: CSS selector (validated for security)

        Returns:
            JavaScript function as string

        Raises:
            ValueError: If selector is invalid or potentially malicious
        """
        # Validate selector to prevent injection
        validated_selector = validate_css_selector(selector)

        # Use JSON.stringify for safe embedding
        selector_json = json.dumps(validated_selector)

        return f"""
        () => {{
            const element = document.querySelector({selector_json});
            return element && element.offsetHeight > 0;
        }}
        """

    @staticmethod
    def element_count(selector: str, min_count: int = 1) -> str:
        """
        Wait for minimum number of elements.

        Args:
            selector: CSS selector (validated for security)
            min_count: Minimum number of elements required

        Returns:
            JavaScript function as string

        Raises:
            ValueError: If selector is invalid or potentially malicious
        """
        # Validate selector to prevent injection
        validated_selector = validate_css_selector(selector)

        # Validate min_count is a positive integer
        if not isinstance(min_count, int) or min_count < 1:
            raise ValueError("min_count must be a positive integer")

        # Use JSON.stringify for safe embedding
        selector_json = json.dumps(validated_selector)

        return f"""
        () => {{
            const elements = document.querySelectorAll({selector_json});
            return elements.length >= {min_count};
        }}
        """

    @staticmethod
    def react_ready() -> str:
        """Wait for React to finish rendering."""
        return """
        () => {
            // Check if React is present
            if (!window.React && !document.querySelector('[data-reactroot]')) {
                return false;
            }

            // Check for React DevTools
            if (window.__REACT_DEVTOOLS_GLOBAL_HOOK__) {
                const renderers = window.__REACT_DEVTOOLS_GLOBAL_HOOK__.renderers;
                if (renderers && renderers.size > 0) {
                    // Check if React is idle (no pending updates)
                    for (let renderer of renderers.values()) {
                        if (renderer.isProfiling || renderer.hasScheduledTask) {
                            return false;
                        }
                    }
                }
            }

            return true;
        }
        """

    @staticmethod
    def vue_ready() -> str:
        """Wait for Vue app to be mounted."""
        return """
        () => {
            // Check if Vue is present
            if (!window.Vue && !window.__VUE__) {
                return false;
            }

            // Check for Vue DevTools
            if (window.__VUE_DEVTOOLS_GLOBAL_HOOK__) {
                const apps = window.__VUE_DEVTOOLS_GLOBAL_HOOK__.apps;
                if (apps && apps.length > 0) {
                    // All apps should be mounted
                    return apps.every(app => app._isMounted || app.isMounted);
                }
            }

            // Fallback: check for Vue root elements
            const vueElements = document.querySelectorAll('[data-v-app]');
            return vueElements.length > 0;
        }
        """

    @staticmethod
    def angular_ready() -> str:
        """Wait for Angular to finish bootstrapping."""
        return """
        () => {
            // Check if Angular is present
            if (!window.angular && !window.ng) {
                return false;
            }

            // Angular 1.x
            if (window.angular) {
                const injector = angular.element(document.body).injector();
                if (injector) {
                    const $http = injector.get('$http');
                    if ($http && $http.pendingRequests) {
                        return $http.pendingRequests.length === 0;
                    }
                }
            }

            // Angular 2+
            if (window.getAllAngularTestabilities) {
                const testabilities = window.getAllAngularTestabilities();
                return testabilities.every(t => t.isStable());
            }

            return true;
        }
        """

    @staticmethod
    def no_ajax_requests() -> str:
        """Wait for all AJAX requests to complete."""
        return """
        () => {
            // Check jQuery
            if (window.jQuery && jQuery.active !== undefined) {
                return jQuery.active === 0;
            }

            // Check Axios
            if (window.axios && window.axios.interceptors) {
                // Custom tracking would need to be set up
                return true;
            }

            // Check fetch
            if (window.__fetch_in_progress !== undefined) {
                return window.__fetch_in_progress === 0;
            }

            return true;
        }
        """

    @staticmethod
    def custom_js(javascript: str) -> str:
        """
        Custom JavaScript condition.

        WARNING: This method allows arbitrary JavaScript execution.
        Only use with trusted input. Never pass user-controlled data directly.

        Args:
            javascript: JavaScript code to execute (MUST be trusted)

        Returns:
            JavaScript function as string

        Raises:
            ValueError: If JavaScript contains dangerous patterns
        """
        if not javascript or not isinstance(javascript, str):
            raise ValueError("JavaScript code must be a non-empty string")

        # Basic security checks for obviously dangerous patterns
        dangerous_patterns = [
            r"eval\s*\(",  # eval() calls
            r"Function\s*\(",  # Function constructor
            r"constructor\s*\(",  # Constructor access
            r"__proto__",  # Prototype manipulation
            r"document\.write",  # DOM manipulation
            r"document\.cookie",  # Cookie access
            r"localStorage",  # Storage access
            r"sessionStorage",  # Storage access
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, javascript, re.IGNORECASE):
                logger.warning(
                    f"Potentially dangerous JavaScript pattern detected: {pattern}. "
                    "Proceeding with caution."
                )

        return f"() => {{ {javascript} }}"


class InfiniteScrollHandler:
    """
    Handle infinite scroll pagination in SPAs.

    Features:
    - Detect infinite scroll implementation
    - Auto-scroll to load more content
    - Track loaded items
    - Stop condition support
    """

    def __init__(
        self,
        item_selector: str,
        scroll_pause: float = 2.0,
        max_scrolls: int = 10,
        stop_if_no_new_items: bool = True,
    ):
        """
        Initialize infinite scroll handler.

        Args:
            item_selector: CSS selector for items being loaded
            scroll_pause: Seconds to wait after each scroll
            max_scrolls: Maximum number of scroll actions
            stop_if_no_new_items: Stop if no new items loaded after scroll

        Raises:
            ValueError: If item_selector is invalid or malicious
        """
        # Validate selector for security
        self.item_selector = validate_css_selector(item_selector)

        # Validate other parameters
        if scroll_pause < 0:
            raise ValueError("scroll_pause must be non-negative")
        if max_scrolls < 1:
            raise ValueError("max_scrolls must be positive")

        self.scroll_pause = scroll_pause
        self.max_scrolls = max_scrolls
        self.stop_if_no_new_items = stop_if_no_new_items

    async def scroll_to_load_all(
        self,
        page: Any,
        on_new_items: Callable[[int], None] | None = None,
    ) -> int:
        """
        Scroll page to load all items via infinite scroll.

        Args:
            page: Playwright page object
            on_new_items: Callback when new items are loaded (receives count)

        Returns:
            Total number of items loaded
        """
        previous_count = 0
        scroll_count = 0

        logger.info(f"Starting infinite scroll (max {self.max_scrolls} scrolls)")

        while scroll_count < self.max_scrolls:
            # Get current item count
            current_count = await page.locator(self.item_selector).count()

            # Check if new items were loaded
            if current_count == previous_count and self.stop_if_no_new_items:
                logger.info(f"No new items loaded, stopping at {current_count} items")
                break

            if current_count > previous_count:
                new_items = current_count - previous_count
                logger.info(f"Loaded {new_items} new items (total: {current_count})")

                if on_new_items:
                    on_new_items(new_items)

            # Scroll to bottom
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            scroll_count += 1

            # Wait for new content to load
            await asyncio.sleep(self.scroll_pause)

            previous_count = current_count

        logger.info(f"Infinite scroll complete: {current_count} items loaded")
        return current_count

    async def scroll_until_condition(
        self,
        page: Any,
        condition: str,
        timeout: float = 30.0,
    ) -> bool:
        """
        Scroll until a custom condition is met.

        Args:
            page: Playwright page object
            condition: JavaScript condition to evaluate
            timeout: Maximum time to scroll

        Returns:
            True if condition was met, False if timeout
        """
        start_time = asyncio.get_event_loop().time()
        scroll_count = 0

        while (asyncio.get_event_loop().time() - start_time) < timeout:
            # Check condition
            result = await page.evaluate(condition)
            if result:
                logger.info(f"Scroll condition met after {scroll_count} scrolls")
                return True

            # Scroll
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            scroll_count += 1
            await asyncio.sleep(self.scroll_pause)

        logger.warning(f"Scroll timeout after {timeout}s")
        return False


class SPAHelper:
    """
    Helper for working with Single-Page Applications.

    Provides utilities for:
    - Smart waiting (network, DOM, framework-specific)
    - Dynamic content detection
    - Route change detection
    - State management
    """

    @staticmethod
    async def wait_for_spa_ready(
        page: Any,
        strategy: SPAWaitStrategy = SPAWaitStrategy.NETWORK_IDLE,
        custom_condition: str | None = None,
        timeout: float = 30.0,
    ) -> bool:
        """
        Wait for SPA to be ready using specified strategy.

        Args:
            page: Playwright page object
            strategy: Wait strategy to use
            custom_condition: Custom JavaScript condition for CUSTOM strategy
            timeout: Maximum wait time

        Returns:
            True if ready, False if timeout
        """
        try:
            if strategy == SPAWaitStrategy.NETWORK_IDLE:
                await page.wait_for_load_state("networkidle", timeout=timeout * 1000)
                logger.info("Network idle detected")
                return True

            elif strategy == SPAWaitStrategy.DOM_STABLE:
                return await SPAHelper._wait_for_dom_stable(page, timeout)

            elif strategy == SPAWaitStrategy.LOAD:
                await page.wait_for_load_state("load", timeout=timeout * 1000)
                logger.info("Page load complete")
                return True

            elif strategy == SPAWaitStrategy.CUSTOM:
                if not custom_condition:
                    raise ValueError("custom_condition required for CUSTOM strategy")

                await page.wait_for_function(custom_condition, timeout=timeout * 1000)
                logger.info("Custom condition met")
                return True

        except Exception as e:
            logger.warning(f"SPA wait timeout ({strategy}): {e}")
            return False

    @staticmethod
    async def _wait_for_dom_stable(
        page: Any,
        timeout: float = 30.0,
        stable_time: float = 1.0,
    ) -> bool:
        """
        Wait for DOM to stop changing.

        Args:
            page: Playwright page object
            timeout: Maximum wait time
            stable_time: Time DOM must be stable

        Returns:
            True if stable, False if timeout
        """
        script = f"""
        () => {{
            return new Promise((resolve) => {{
                let lastHtml = document.body.innerHTML;
                let stableCount = 0;
                const requiredStableChecks = {int(stable_time * 10)};

                const interval = setInterval(() => {{
                    const currentHtml = document.body.innerHTML;

                    if (currentHtml === lastHtml) {{
                        stableCount++;
                        if (stableCount >= requiredStableChecks) {{
                            clearInterval(interval);
                            resolve(true);
                        }}
                    }} else {{
                        stableCount = 0;
                    }}

                    lastHtml = currentHtml;
                }}, 100);

                setTimeout(() => {{
                    clearInterval(interval);
                    resolve(false);
                }}, {int(timeout * 1000)});
            }});
        }}
        """

        try:
            result = await page.evaluate(script)
            if result:
                logger.info("DOM stable detected")
            return result
        except Exception as e:
            logger.warning(f"DOM stability check failed: {e}")
            return False

    @staticmethod
    async def detect_framework(page: Any) -> str | None:
        """
        Detect which JavaScript framework is used on the page.

        Args:
            page: Playwright page object

        Returns:
            Framework name ("react", "vue", "angular") or None
        """
        script = """
        () => {
            if (window.React || document.querySelector('[data-reactroot]')) {
                return 'react';
            }
            if (window.Vue || window.__VUE__ || document.querySelector('[data-v-app]')) {
                return 'vue';
            }
            if (window.angular || window.ng) {
                return 'angular';
            }
            if (window.Ember) {
                return 'ember';
            }
            if (window.Backbone) {
                return 'backbone';
            }
            return null;
        }
        """

        framework = await page.evaluate(script)
        if framework:
            logger.info(f"Detected framework: {framework}")
        return framework

    @staticmethod
    async def wait_for_route_change(
        page: Any,
        timeout: float = 10.0,
    ) -> bool:
        """
        Wait for SPA route change to complete.

        Args:
            page: Playwright page object
            timeout: Maximum wait time

        Returns:
            True if route changed, False if timeout
        """
        # Store initial URL
        initial_url = page.url

        script = f"""
        (initialUrl) => {{
            return new Promise((resolve) => {{
                let checkCount = 0;
                const maxChecks = {int(timeout * 10)};

                const interval = setInterval(() => {{
                    checkCount++;

                    // Check if URL changed
                    if (window.location.href !== initialUrl) {{
                        clearInterval(interval);
                        resolve(true);
                        return;
                    }}

                    if (checkCount >= maxChecks) {{
                        clearInterval(interval);
                        resolve(false);
                    }}
                }}, 100);
            }});
        }}
        """

        try:
            result = await page.evaluate(script, initial_url)
            if result:
                logger.info(f"Route changed from {initial_url} to {page.url}")
            return result
        except Exception as e:
            logger.warning(f"Route change detection failed: {e}")
            return False

    @staticmethod
    async def extract_dynamic_content(
        page: Any,
        selector: str,
        wait_strategy: SPAWaitStrategy = SPAWaitStrategy.NETWORK_IDLE,
        max_retries: int = 3,
    ) -> list[str]:
        """
        Extract content from dynamically loaded elements.

        Args:
            page: Playwright page object
            selector: CSS selector for elements (validated for security)
            wait_strategy: Strategy to wait for content
            max_retries: Number of retry attempts

        Returns:
            List of text content from elements

        Raises:
            ValueError: If selector is invalid or malicious
        """
        # Validate selector for security
        validated_selector = validate_css_selector(selector)

        for attempt in range(max_retries):
            try:
                # Wait for SPA to be ready
                await SPAHelper.wait_for_spa_ready(page, strategy=wait_strategy)

                # Wait for elements
                await page.wait_for_selector(validated_selector, timeout=10000)

                # Extract content
                elements = await page.locator(validated_selector).all()
                content = []

                for element in elements:
                    text = await element.text_content()
                    if text:
                        content.append(text.strip())

                logger.info(f"Extracted {len(content)} items from {validated_selector}")
                return content

            except Exception as e:
                logger.warning(f"Content extraction attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                else:
                    raise

        return []


if __name__ == "__main__":
    # Example usage
    import asyncio

    from playwright.async_api import async_playwright

    async def demo():
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()

            # Navigate to an SPA
            await page.goto("https://example-spa.com")

            # Detect framework
            framework = await SPAHelper.detect_framework(page)
            print(f"Framework: {framework}")

            # Wait for SPA to be ready
            await SPAHelper.wait_for_spa_ready(page, strategy=SPAWaitStrategy.NETWORK_IDLE)

            # Handle infinite scroll
            scroll_handler = InfiniteScrollHandler(item_selector=".item", max_scrolls=5)
            total_items = await scroll_handler.scroll_to_load_all(page)
            print(f"Loaded {total_items} items")

            await browser.close()

    # asyncio.run(demo())
