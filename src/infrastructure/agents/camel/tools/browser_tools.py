"""Camel AI Tools wrappers for browser automation (OpenManus).

Wraps OpenManus browser capabilities as Camel FunctionTools.
"""

import asyncio

from camel.toolkits import FunctionTool
from loguru import logger


def browser_navigate(url: str) -> dict:
    """Navigate to a URL and get page information.

    Args:
        url: The URL to navigate to

    Returns:
        Dictionary with:
        - url: Final URL (after redirects)
        - title: Page title
        - status: Success or error status
    """
    from src.infrastructure.agents.openmanus.openmanus_adapter import OpenManusAdapter

    async def _navigate():
        adapter = OpenManusAdapter(headless=True)
        try:
            result = await adapter.execute_task({"url": url, "action": "navigate"})
            return result.get("result", {})
        finally:
            await adapter.cleanup()

    return asyncio.run(_navigate())


def browser_extract(
    url: str, selectors: dict[str, str] | None = None, target: str | None = None
) -> dict:
    """Extract data from a web page.

    Args:
        url: The URL to extract data from
        selectors: Optional CSS selectors mapping (e.g., {"titles": "h1", "links": "a"})
        target: Description of what to extract (used for AI-guided extraction)

    Returns:
        Dictionary with:
        - title: Page title
        - url: Page URL
        - data: Extracted data (depends on selectors or general extraction)
        - text: Page text content (first 1000 chars if no selectors)
        - links: First 10 links on the page
    """
    from src.infrastructure.agents.openmanus.openmanus_adapter import OpenManusAdapter

    async def _extract():
        adapter = OpenManusAdapter(headless=True)
        try:
            config = {
                "url": url,
                "action": "extract",
                "data": {"target": target or "page content"},
            }
            if selectors:
                config["selectors"] = selectors

            result = await adapter.execute_task(config)
            return result.get("result", {})
        finally:
            await adapter.cleanup()

    return asyncio.run(_extract())


def browser_fill_form(
    url: str,
    selectors: dict[str, str],
    data: dict[str, str],
    submit: bool = False,
    submit_selector: str | None = None,
) -> dict:
    """Fill a web form with data.

    Args:
        url: The URL of the form
        selectors: CSS selectors for form fields (e.g., {"name": "#name-input"})
        data: Field values to fill (e.g., {"name": "John Doe"})
        submit: Whether to submit the form after filling
        submit_selector: CSS selector for submit button (default: button[type='submit'])

    Returns:
        Dictionary with:
        - filled_fields: List of fields that were filled
        - submitted: Whether the form was submitted
        - status: Success or error
    """
    from src.infrastructure.agents.openmanus.openmanus_adapter import OpenManusAdapter

    async def _fill():
        adapter = OpenManusAdapter(headless=True)
        try:
            config = {
                "url": url,
                "action": "fill_form",
                "selectors": selectors,
                "data": data,
                "submit": submit,
            }
            if submit_selector:
                config["submit_selector"] = submit_selector

            result = await adapter.execute_task(config)
            return result.get("result", {})
        finally:
            await adapter.cleanup()

    return asyncio.run(_fill())


def browser_click(url: str, selector: str) -> dict:
    """Click an element on a web page.

    Args:
        url: The URL of the page
        selector: CSS selector for the element to click

    Returns:
        Dictionary with:
        - url: URL after click (may have changed)
        - title: Page title after click
        - status: Success or error
    """
    from src.infrastructure.agents.openmanus.openmanus_adapter import OpenManusAdapter

    async def _click():
        adapter = OpenManusAdapter(headless=True)
        try:
            result = await adapter.execute_task(
                {
                    "url": url,
                    "action": "click",
                    "selector": selector,
                }
            )
            return result.get("result", {})
        finally:
            await adapter.cleanup()

    return asyncio.run(_click())


def browser_search(query: str, engine: str = "duckduckgo") -> dict:
    """Search the web and return results.

    Args:
        query: Search query
        engine: Search engine to use ('duckduckgo', 'google')

    Returns:
        Dictionary with:
        - results: List of search results with title, url, snippet
        - query: Original query
    """
    from src.cli.v2.agents.tools import register_all_tools
    from src.cli.v2.agents.unified.tools import ToolRegistry

    async def _search():
        registry = ToolRegistry()
        register_all_tools(registry)
        return await registry.execute(
            "browser.search",
            {
                "query": query,
                "engine": engine,
            },
        )

    return asyncio.run(_search())


# ============================================================================
# TOOL REGISTRATION
# ============================================================================


def get_browser_tools() -> list[FunctionTool]:
    """Get all browser automation tools as Camel FunctionTools.

    Returns:
        List of FunctionTool instances ready for use with Camel agents
    """
    tools = [
        FunctionTool(browser_navigate),
        FunctionTool(browser_extract),
        FunctionTool(browser_fill_form),
        FunctionTool(browser_click),
        FunctionTool(browser_search),
    ]

    logger.debug(f"Registered {len(tools)} browser tools for Camel AI")
    return tools


# Convenience exports
BROWSER_TOOLS = get_browser_tools()
