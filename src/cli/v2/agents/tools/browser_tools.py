"""Browser tools for the unified agent."""

from typing import Any

from loguru import logger

from src.cli.v2.agents.unified.tools import Tool, ToolCategory, ToolRegistry


def _extract_text_from_html(html: str, max_length: int = 4000) -> str:
    """Extract readable text from HTML using BeautifulSoup."""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")

        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.decompose()

        # Get text
        text = soup.get_text(separator="\n", strip=True)

        # Clean up whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        text = "\n".join(lines)

        # Truncate if needed
        if len(text) > max_length:
            text = text[:max_length] + "..."

        return text
    except Exception as e:
        logger.warning(f"HTML text extraction failed: {e}")
        return html[:max_length] if len(html) > max_length else html


def _extract_links_from_html(html: str, base_url: str = "") -> list:
    """Extract links from HTML."""
    try:
        from urllib.parse import urljoin

        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        links = []

        for a in soup.find_all("a", href=True)[:20]:  # Limit to 20 links
            href = a["href"]
            text = a.get_text(strip=True)[:100]

            # Make absolute URL
            if base_url and not href.startswith(("http://", "https://")):
                href = urljoin(base_url, href)

            if href.startswith(("http://", "https://")) and text:
                links.append({"url": href, "text": text})

        return links
    except Exception as e:
        logger.warning(f"Link extraction failed: {e}")
        return []


def _extract_title(html: str) -> str:
    """Extract page title from HTML."""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("title")
        return title_tag.get_text(strip=True) if title_tag else ""
    except Exception:
        return ""


def _extract_real_url(ddg_url: str) -> str:
    """Extract real URL from DuckDuckGo redirect URL.

    DuckDuckGo uses URLs like: //duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com
    We need to extract and decode the 'uddg' parameter.
    """
    from urllib.parse import parse_qs, unquote, urlparse

    try:
        # Handle protocol-relative URLs
        if ddg_url.startswith("//"):
            ddg_url = "https:" + ddg_url

        parsed = urlparse(ddg_url)

        # Check if it's a DuckDuckGo redirect
        if "duckduckgo.com" in parsed.netloc and "/l/" in parsed.path:
            params = parse_qs(parsed.query)
            if "uddg" in params:
                return unquote(params["uddg"][0])

        # Already a direct URL
        return ddg_url
    except Exception:
        return ddg_url


def _parse_duckduckgo_results(html: str, num_results: int = 5) -> list:
    """Parse DuckDuckGo HTML search results."""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        results = []

        # DuckDuckGo HTML results are in divs with class 'result'
        for result_div in soup.find_all("div", class_="result")[:num_results]:
            try:
                # Get title and URL
                title_link = result_div.find("a", class_="result__a")
                if not title_link:
                    continue

                title = title_link.get_text(strip=True)
                raw_url = title_link.get("href", "")

                # Extract real URL from DuckDuckGo redirect
                url = _extract_real_url(raw_url)

                # Get snippet
                snippet_div = result_div.find("a", class_="result__snippet")
                snippet = snippet_div.get_text(strip=True) if snippet_div else ""

                if title and url and url.startswith("http"):
                    results.append(
                        {
                            "title": title,
                            "url": url,
                            "snippet": snippet[:200],
                        }
                    )
            except Exception:
                continue

        return results
    except Exception as e:
        logger.warning(f"DuckDuckGo parsing failed: {e}")
        return []


def register_browser_tools(registry: ToolRegistry) -> None:
    """Register browser automation tools."""

    async def browser_navigate(url: str) -> dict[str, Any]:
        """Navigate to a URL and get page content as extracted text."""
        try:
            import httpx

            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

            async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
                response = await client.get(url, follow_redirects=True)

                # Extract text content from HTML
                text_content = _extract_text_from_html(response.text)
                links = _extract_links_from_html(response.text, str(response.url))

                return {
                    "success": True,
                    "url": str(response.url),
                    "status_code": response.status_code,
                    "text_content": text_content,
                    "links": links[:10],  # Top 10 links
                    "title": _extract_title(response.text),
                }
        except Exception as e:
            logger.error(f"Browser navigate failed: {e}")
            return {"success": False, "error": str(e)}

    async def browser_search(query: str, num_results: int = 5, **kwargs) -> dict[str, Any]:
        """Search the web using DuckDuckGo and return results.

        Note: kwargs absorbs any extra params (like 'engine') that LLM agents may send.
        """
        # Log any unexpected kwargs for debugging
        if kwargs:
            logger.debug(f"browser_search received extra kwargs (ignored): {kwargs}")
        try:
            from urllib.parse import quote_plus

            import httpx

            # Use DuckDuckGo HTML search (no API key needed)
            search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

            async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
                response = await client.get(search_url, follow_redirects=True)

                if response.status_code != 200:
                    return {"success": False, "error": f"Search returned {response.status_code}"}

                # Parse results
                results = _parse_duckduckgo_results(response.text, num_results)

                return {
                    "success": True,
                    "query": query,
                    "results": results,
                    "num_results": len(results),
                }
        except Exception as e:
            logger.error(f"Browser search failed: {e}")
            return {"success": False, "error": str(e)}

    async def browser_extract(selector: str, format: str = "text") -> dict[str, Any]:
        """Extract content from the current page using CSS selector.

        Note: This is a placeholder - full browser automation requires
        integration with the browser agent service.
        """
        try:
            # Placeholder - will integrate with BrowserAgentService when available
            return {
                "success": False,
                "error": "Browser extraction not yet implemented. Use browser.navigate for basic HTTP fetching.",
                "selector": selector,
            }
        except Exception as e:
            logger.error(f"Browser extract failed: {e}")
            return {"success": False, "error": str(e)}

    # Register tools
    registry._tools["browser.navigate"] = Tool(
        name="browser.navigate",
        func=browser_navigate,
        category=ToolCategory.BROWSER,
        description="Navigate to a URL and get extracted text content, title, and links",
    )

    registry._tools["browser.search"] = Tool(
        name="browser.search",
        func=browser_search,
        category=ToolCategory.BROWSER,
        description="Search the web using DuckDuckGo. Returns titles, URLs, and snippets",
    )

    registry._tools["browser.extract"] = Tool(
        name="browser.extract",
        func=browser_extract,
        category=ToolCategory.BROWSER,
        description="Extract content from page using CSS selector (placeholder)",
    )

    logger.debug("Registered 3 browser tools")
