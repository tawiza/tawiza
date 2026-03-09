"""API calling tools for the unified agent."""

from typing import Any

from loguru import logger

from src.cli.v2.agents.unified.tools import Tool, ToolCategory, ToolRegistry


def register_api_tools(registry: ToolRegistry) -> None:
    """Register API tools."""

    async def api_fetch(
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: str | None = None,
    ) -> dict[str, Any]:
        """Fetch data from an API endpoint.

        Args:
            url: The API endpoint URL
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            headers: Optional HTTP headers as dict
            body: Optional request body for POST/PUT

        Returns:
            Dict with success, status_code, headers, and body
        """
        try:
            import httpx

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.request(
                    method=method.upper(),
                    url=url,
                    headers=headers or {},
                    content=body,
                )

                # Try to parse as JSON
                try:
                    response_body = response.json()
                except:
                    response_body = response.text[:5000]  # Truncate text responses

                return {
                    "success": True,
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response_body,
                }
        except Exception as e:
            logger.error(f"API fetch failed: {e}")
            return {"success": False, "error": str(e)}

    # Register tool
    registry._tools["api.fetch"] = Tool(
        name="api.fetch",
        func=api_fetch,
        category=ToolCategory.API,
        description="Make HTTP request to an API endpoint",
    )

    logger.debug("Registered 1 API tool")
