"""Browser PiP (Picture-in-Picture) streaming for MCP.

Provides real-time browser screenshots during web scraping operations.
Sends base64-encoded screenshots via MCP notifications.
"""

import base64
import json

from mcp.server.fastmcp import Context, FastMCP

# Global state for browser streaming
_browser_state = {
    "streaming": False,
    "page": None,
    "browser": None,
    "context": None,
    "interval_ms": 500,
}


def register_browser_tools(mcp: FastMCP) -> None:
    """Register browser PiP tools on the MCP server."""

    @mcp.tool()
    async def browser_start_stream(
        url: str | None = None,
        interval_ms: int = 500,
        ctx: Context = None,
    ) -> str:
        """Démarre le streaming live du navigateur (Picture-in-Picture).

        Lance un navigateur headless et capture des screenshots à intervalle régulier.
        Les screenshots sont envoyés via les notifications MCP.

        Args:
            url: URL initiale à charger (optionnel)
            interval_ms: Intervalle entre captures (défaut: 500ms)

        Returns:
            Status du streaming
        """
        global _browser_state

        if _browser_state["streaming"]:
            return json.dumps({
                "success": False,
                "error": "Stream already active",
                "message": "Use browser_stop_stream to stop current stream",
            })

        try:
            from playwright.async_api import async_playwright

            if ctx:
                ctx.info("[Browser] Starting Playwright...")
                ctx.report_progress(0, 100, "Launching browser...")

            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            )
            page = await context.new_page()

            _browser_state["browser"] = browser
            _browser_state["context"] = context
            _browser_state["page"] = page
            _browser_state["streaming"] = True
            _browser_state["interval_ms"] = interval_ms
            _browser_state["playwright"] = playwright

            if ctx:
                ctx.report_progress(50, 100, "Browser launched")

            # Navigate to URL if provided
            if url:
                if ctx:
                    ctx.info(f"[Browser] Navigating to: {url}")
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                if ctx:
                    ctx.info(f"[Browser] Page loaded: {page.title()}")

            if ctx:
                ctx.report_progress(100, 100, "✓ Stream started")

            return json.dumps({
                "success": True,
                "message": "Browser stream started",
                "url": url or "about:blank",
                "interval_ms": interval_ms,
                "viewport": {"width": 1280, "height": 720},
            })

        except ImportError:
            return json.dumps({
                "success": False,
                "error": "Playwright not installed",
                "message": "Run: pip install playwright && playwright install chromium",
            })
        except Exception as e:
            _browser_state["streaming"] = False
            return json.dumps({
                "success": False,
                "error": str(e),
            })

    @mcp.tool()
    async def browser_stop_stream(ctx: Context = None) -> str:
        """Arrête le streaming live du navigateur.

        Ferme le navigateur et libère les ressources.

        Returns:
            Status de l'arrêt
        """
        global _browser_state

        if not _browser_state["streaming"]:
            return json.dumps({
                "success": False,
                "error": "No stream active",
            })

        try:
            if ctx:
                ctx.info("[Browser] Stopping stream...")

            if _browser_state["page"]:
                await _browser_state["page"].close()
            if _browser_state["context"]:
                await _browser_state["context"].close()
            if _browser_state["browser"]:
                await _browser_state["browser"].close()
            if _browser_state.get("playwright"):
                await _browser_state["playwright"].stop()

            _browser_state["streaming"] = False
            _browser_state["page"] = None
            _browser_state["browser"] = None
            _browser_state["context"] = None
            _browser_state["playwright"] = None

            if ctx:
                ctx.info("[Browser] Stream stopped")

            return json.dumps({
                "success": True,
                "message": "Browser stream stopped",
            })

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e),
            })

    @mcp.tool()
    async def browser_screenshot(ctx: Context = None) -> str:
        """Capture un screenshot du navigateur actif.

        Retourne une image base64 de l'état actuel du navigateur.

        Returns:
            Screenshot en base64 + métadonnées
        """
        global _browser_state

        if not _browser_state["streaming"] or not _browser_state["page"]:
            return json.dumps({
                "success": False,
                "error": "No browser stream active",
                "message": "Start stream with browser_start_stream first",
            })

        try:
            page = _browser_state["page"]

            # Capture screenshot
            screenshot_bytes = await page.screenshot(type="png")
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

            # Get page info
            url = page.url
            title = await page.title()

            if ctx:
                ctx.info(f"[Browser] Screenshot: {url}")

            return json.dumps({
                "success": True,
                "url": url,
                "title": title,
                "image_base64": screenshot_b64,
                "format": "png",
                "viewport": {"width": 1280, "height": 720},
            })

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e),
            })

    @mcp.tool()
    async def browser_navigate(
        url: str,
        wait_for: str = "domcontentloaded",
        ctx: Context = None,
    ) -> str:
        """Navigue vers une URL dans le navigateur actif.

        Args:
            url: URL de destination
            wait_for: Event à attendre (load, domcontentloaded, networkidle)

        Returns:
            Status de la navigation + screenshot
        """
        global _browser_state

        if not _browser_state["streaming"] or not _browser_state["page"]:
            return json.dumps({
                "success": False,
                "error": "No browser stream active",
            })

        try:
            page = _browser_state["page"]

            if ctx:
                ctx.info(f"[Browser] Navigating to: {url}")
                ctx.report_progress(0, 100, f"Loading: {url}")

            await page.goto(url, wait_until=wait_for, timeout=30000)

            title = await page.title()

            if ctx:
                ctx.info(f"[Browser] Loaded: {title}")
                ctx.report_progress(100, 100, f"✓ {title}")

            # Capture screenshot
            screenshot_bytes = await page.screenshot(type="png")
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

            return json.dumps({
                "success": True,
                "url": page.url,
                "title": title,
                "image_base64": screenshot_b64,
            })

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e),
                "url": url,
            })

    @mcp.tool()
    async def browser_click(
        selector: str,
        ctx: Context = None,
    ) -> str:
        """Clique sur un élément dans le navigateur.

        Args:
            selector: Sélecteur CSS ou XPath de l'élément

        Returns:
            Status du clic + screenshot après action
        """
        global _browser_state

        if not _browser_state["streaming"] or not _browser_state["page"]:
            return json.dumps({
                "success": False,
                "error": "No browser stream active",
            })

        try:
            page = _browser_state["page"]

            if ctx:
                ctx.info(f"[Browser] Clicking: {selector}")

            await page.click(selector, timeout=10000)
            await page.wait_for_load_state("domcontentloaded")

            # Capture screenshot after click
            screenshot_bytes = await page.screenshot(type="png")
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

            if ctx:
                ctx.info(f"[Browser] Clicked: {selector}")

            return json.dumps({
                "success": True,
                "action": "click",
                "selector": selector,
                "url": page.url,
                "image_base64": screenshot_b64,
            })

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e),
                "selector": selector,
            })

    @mcp.tool()
    async def browser_extract(
        selector: str,
        attribute: str | None = None,
        ctx: Context = None,
    ) -> str:
        """Extrait du contenu d'éléments dans le navigateur.

        Args:
            selector: Sélecteur CSS des éléments
            attribute: Attribut à extraire (optionnel, sinon text_content)

        Returns:
            Liste des contenus extraits
        """
        global _browser_state

        if not _browser_state["streaming"] or not _browser_state["page"]:
            return json.dumps({
                "success": False,
                "error": "No browser stream active",
            })

        try:
            page = _browser_state["page"]

            if ctx:
                ctx.info(f"[Browser] Extracting: {selector}")

            elements = await page.query_selector_all(selector)
            results = []

            for el in elements:
                if attribute:
                    value = await el.get_attribute(attribute)
                else:
                    value = await el.text_content()
                if value:
                    results.append(value.strip())

            if ctx:
                ctx.info(f"[Browser] Extracted {len(results)} items")

            return json.dumps({
                "success": True,
                "selector": selector,
                "attribute": attribute,
                "count": len(results),
                "results": results[:100],  # Limit to 100 items
            })

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e),
                "selector": selector,
            })

    @mcp.tool()
    async def browser_scrape_page(
        url: str,
        extract_links: bool = True,
        extract_emails: bool = True,
        extract_phones: bool = True,
        ctx: Context = None,
    ) -> str:
        """Scrape une page web et extrait des informations structurées.

        Charge la page, capture un screenshot, et extrait liens/emails/téléphones.

        Args:
            url: URL à scraper
            extract_links: Extraire les liens (défaut: True)
            extract_emails: Extraire les emails (défaut: True)
            extract_phones: Extraire les numéros de téléphone (défaut: True)

        Returns:
            Données extraites + screenshot
        """
        global _browser_state

        # Start browser if not already running
        if not _browser_state["streaming"]:
            start_result = await browser_start_stream(url=url, ctx=ctx)
            start_data = json.loads(start_result)
            if not start_data.get("success"):
                return start_result
        else:
            # Navigate to URL
            nav_result = await browser_navigate(url=url, ctx=ctx)
            nav_data = json.loads(nav_result)
            if not nav_data.get("success"):
                return nav_result

        try:
            page = _browser_state["page"]
            result = {
                "success": True,
                "url": page.url,
                "title": await page.title(),
            }

            if ctx:
                ctx.report_progress(30, 100, "Extracting content...")

            # Extract links
            if extract_links:
                links = await page.evaluate("""
                    () => Array.from(document.querySelectorAll('a[href]'))
                        .map(a => ({text: a.innerText.trim(), href: a.href}))
                        .filter(l => l.text && l.href.startsWith('http'))
                        .slice(0, 50)
                """)
                result["links"] = links
                if ctx:
                    ctx.info(f"[Browser] Found {len(links)} links")

            # Extract emails
            if extract_emails:
                import re
                html = await page.content()
                emails = list(set(re.findall(
                    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
                    html
                )))
                result["emails"] = emails[:20]
                if ctx:
                    ctx.info(f"[Browser] Found {len(emails)} emails")

            # Extract phones
            if extract_phones:
                import re
                html = await page.content()
                # French phone patterns
                phones = list(set(re.findall(
                    r'(?:\+33|0)[1-9](?:[\s.-]?\d{2}){4}',
                    html
                )))
                result["phones"] = phones[:20]
                if ctx:
                    ctx.info(f"[Browser] Found {len(phones)} phones")

            if ctx:
                ctx.report_progress(80, 100, "Capturing screenshot...")

            # Capture screenshot
            screenshot_bytes = await page.screenshot(type="png")
            result["image_base64"] = base64.b64encode(screenshot_bytes).decode("utf-8")

            if ctx:
                ctx.report_progress(100, 100, "✓ Scrape complete")

            return json.dumps(result, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e),
                "url": url,
            })

    # Register browser resource for live view
    @mcp.resource("tawiza://browser/status")
    def get_browser_status() -> str:
        """Get current browser stream status."""
        return json.dumps({
            "streaming": _browser_state["streaming"],
            "url": _browser_state["page"].url if _browser_state["page"] else None,
            "interval_ms": _browser_state["interval_ms"],
        })
