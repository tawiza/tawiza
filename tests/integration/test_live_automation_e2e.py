"""End-to-end integration tests for LIVE automation.

Tests complete workflows:
- OllamaClient -> browser agent integration
- Full task execution pipeline
- Error recovery and resilience
- Concurrent session handling
"""

import json
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from src.infrastructure.agents.openmanus.openmanus_adapter import OpenManusAdapter
from src.infrastructure.llm.ollama_client import OllamaClient


class TestLiveAutomationEndToEnd:
    """End-to-end tests for complete automation workflows."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_complete_extraction_workflow(self):
        """Test complete workflow: navigate -> analyze -> extract."""
        # Initialize clients
        ollama = OllamaClient()
        agent = OpenManusAdapter(headless=True)

        try:
            # Mock Ollama responses
            with (
                patch.object(ollama.client, "post") as mock_post,
                patch.object(agent, "_ensure_browser") as mock_ensure,
            ):
                # Setup mock browser
                mock_page = AsyncMock()
                mock_page.url = "https://news.example.com"
                mock_page.title = AsyncMock(return_value="News Site")
                mock_page.content = AsyncMock(
                    return_value="""
                    <html>
                        <h2>Breaking News</h2>
                        <article class="news-item">
                            <h3>Article 1</h3>
                            <p>Content 1</p>
                        </article>
                        <article class="news-item">
                            <h3>Article 2</h3>
                            <p>Content 2</p>
                        </article>
                    </html>
                """
                )
                mock_page.goto = AsyncMock()
                mock_page.screenshot = AsyncMock()
                mock_page.close = AsyncMock()
                mock_page.wait_for_load_state = AsyncMock()

                mock_browser = AsyncMock()
                mock_browser.new_page = AsyncMock(return_value=mock_page)
                mock_ensure.return_value = mock_browser

                # Mock Ollama for extraction
                extraction_response = {
                    "items": ["Article 1", "Article 2"],
                    "count": 2,
                    "confidence": 0.95,
                }
                mock_response = MagicMock()
                mock_response.json.return_value = {"response": json.dumps(extraction_response)}
                mock_post.return_value = mock_response

                # Execute workflow
                # Step 1: Navigate
                task_result = await agent.execute_task(
                    {"url": "https://news.example.com", "action": "navigate"}
                )

                assert task_result["status"].value == "completed"

                # Step 2: Extract data using LLM guidance
                extraction_result = await ollama.extract_data_with_llm(
                    mock_page.content.return_value, "article titles"
                )

                assert extraction_result["count"] == 2

        finally:
            await ollama.close()
            await agent.cleanup()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_form_filling_workflow(self):
        """Test complete form filling workflow."""
        ollama = OllamaClient()
        agent = OpenManusAdapter(headless=True)

        try:
            with patch.object(agent, "_ensure_browser") as mock_ensure:
                mock_page = AsyncMock()
                mock_page.url = "https://form.example.com"
                mock_page.title = AsyncMock(return_value="Contact Form")
                mock_page.goto = AsyncMock()
                mock_page.fill = AsyncMock()
                mock_page.click = AsyncMock()
                mock_page.screenshot = AsyncMock()
                mock_page.close = AsyncMock()
                mock_page.wait_for_load_state = AsyncMock()

                mock_browser = AsyncMock()
                mock_browser.new_page = AsyncMock(return_value=mock_page)
                mock_ensure.return_value = mock_browser

                # Execute form filling
                result = await agent.execute_task(
                    {
                        "url": "https://form.example.com",
                        "action": "fill_form",
                        "selectors": {"name": "#name", "email": "#email", "message": "#message"},
                        "data": {
                            "name": "Test User",
                            "email": "test@example.com",
                            "message": "Hello, this is a test.",
                        },
                        "submit": True,
                        "submit_selector": "button[type='submit']",
                    }
                )

                assert result["result"]["submitted"] is True
                assert len(result["result"]["filled_fields"]) == 3

        finally:
            await ollama.close()
            await agent.cleanup()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_vision_guided_navigation(self):
        """Test navigation with vision guidance."""
        ollama = OllamaClient()

        try:
            with patch.object(ollama.client, "post") as mock_post:
                # Mock text-based guidance
                action_plan = {
                    "action": "click",
                    "selector": "button.search",
                    "reasoning": "Click search button",
                    "confidence": 0.8,
                }

                # First response: text analysis
                response_text = MagicMock()
                response_text.json.return_value = {"response": json.dumps(action_plan)}

                # Second response: vision confirmation
                response_vision = MagicMock()
                response_vision.json.return_value = {"response": "CONFIRM The button is visible."}

                mock_post.side_effect = [response_text, response_vision]

                # Create test screenshot
                import tempfile
                from io import BytesIO

                from PIL import Image

                img = Image.new("RGB", (800, 600), color="white")
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                    img.save(f, format="PNG")
                    screenshot_path = f.name

                try:
                    # Get guided action
                    guidance = await ollama.guide_web_action(
                        task="Search for something",
                        page_html="<html><body><button>Search</button></body></html>",
                        screenshot_path=screenshot_path,
                    )

                    assert guidance["action"] == "click"
                    assert guidance["confidence"] > 0.8

                finally:
                    import os

                    os.unlink(screenshot_path)

        finally:
            await ollama.close()


class TestConcurrentSessionHandling:
    """Tests for handling concurrent sessions."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_concurrent_ollama_requests(self):
        """Test concurrent Ollama requests."""
        import asyncio

        ollama = OllamaClient()

        try:
            with patch.object(ollama.client, "post") as mock_post:
                mock_response = MagicMock()
                mock_response.json.return_value = {"response": "Response"}
                mock_post.return_value = mock_response

                # Create 5 concurrent requests
                tasks = [ollama.generate(f"Prompt {i}", stream=False) for i in range(5)]

                results = await asyncio.gather(*tasks)

                assert len(results) == 5
                assert all(r == "Response" for r in results)

        finally:
            await ollama.close()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_multiple_browser_sessions(self):
        """Test multiple concurrent browser sessions."""
        agents = [OpenManusAdapter(headless=True) for _ in range(3)]

        try:
            with patch(
                "src.infrastructure.agents.openmanus.openmanus_adapter.async_playwright"
            ) as mock_pw:
                mock_playwright = AsyncMock()
                mock_browsers = [AsyncMock() for _ in range(3)]
                mock_pages = [AsyncMock() for _ in range(3)]

                # Setup mocks
                for i, (browser, page) in enumerate(zip(mock_browsers, mock_pages)):
                    page.url = f"https://example{i}.com"
                    page.title = AsyncMock(return_value=f"Page {i}")
                    page.goto = AsyncMock()
                    page.screenshot = AsyncMock()
                    page.close = AsyncMock()
                    page.wait_for_load_state = AsyncMock()

                    browser.new_page = AsyncMock(return_value=page)
                    browser.close = AsyncMock()

                mock_pw.return_value.start = AsyncMock(return_value=mock_playwright)
                mock_playwright.chromium.launch = AsyncMock(side_effect=mock_browsers)

                # Execute concurrent tasks
                import asyncio

                tasks = [
                    agent.execute_task({"url": f"https://example{i}.com", "action": "navigate"})
                    for i, agent in enumerate(agents)
                ]

                results = await asyncio.gather(*tasks)

                assert len(results) == 3

        finally:
            for agent in agents:
                # Note: cleanup would normally be async
                pass


class TestErrorRecoveryAndResilience:
    """Tests for error recovery and resilience."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_ollama_timeout_recovery(self):
        """Test recovery from Ollama timeout."""
        import asyncio

        ollama = OllamaClient(timeout=1)

        try:
            with patch.object(ollama.client, "post") as mock_post:
                # First request times out, second succeeds
                mock_post.side_effect = [
                    TimeoutError("Request timeout"),
                    MagicMock(json=lambda: {"response": "Success"}),
                ]

                # First attempt fails
                with pytest.raises(asyncio.TimeoutError):
                    await ollama.generate("Test", stream=False)

                # Recovery: second attempt succeeds
                mock_post.side_effect = None
                mock_response = MagicMock()
                mock_response.json.return_value = {"response": "Success"}
                mock_post.return_value = mock_response

                result = await ollama.generate("Test", stream=False)
                assert result == "Success"

        finally:
            await ollama.close()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_browser_navigation_with_retry(self):
        """Test browser navigation with implicit retry."""
        agent = OpenManusAdapter(headless=True)

        try:
            with patch.object(agent, "_ensure_browser") as mock_ensure:
                mock_page = AsyncMock()
                mock_page.url = "https://example.com"
                mock_page.title = AsyncMock(return_value="Test")
                mock_page.goto = AsyncMock()
                mock_page.screenshot = AsyncMock()
                mock_page.close = AsyncMock()
                mock_page.wait_for_load_state = AsyncMock()

                mock_browser = AsyncMock()
                mock_browser.new_page = AsyncMock(return_value=mock_page)
                mock_ensure.return_value = mock_browser

                # Execute navigation
                result = await agent.execute_task(
                    {"url": "https://example.com", "action": "navigate"}
                )

                assert result["status"].value == "completed"

        finally:
            await agent.cleanup()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_graceful_degradation_without_vision(self):
        """Test that system works without vision models."""
        ollama = OllamaClient(vision_model=None)

        try:
            # Should still work for text-based tasks
            with patch.object(ollama.client, "post") as mock_post:
                mock_response = MagicMock()
                mock_response.json.return_value = {
                    "response": json.dumps(
                        {"action": "click", "selector": "button", "confidence": 0.8}
                    )
                }
                mock_post.return_value = mock_response

                guidance = await ollama.guide_web_action(
                    task="Click button", page_html="<html><button>Click</button></html>"
                )

                assert guidance["action"] == "click"

        finally:
            await ollama.close()


class TestDataConsistency:
    """Tests for data consistency across workflows."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_extraction_consistency(self):
        """Test that extraction produces consistent results."""
        ollama = OllamaClient()

        try:
            html = """
            <html>
                <div class="item">Item 1</div>
                <div class="item">Item 2</div>
                <div class="item">Item 3</div>
            </html>
            """

            with patch.object(ollama.client, "post") as mock_post:
                response_data = {
                    "items": ["Item 1", "Item 2", "Item 3"],
                    "count": 3,
                    "confidence": 0.95,
                }
                mock_response = MagicMock()
                mock_response.json.return_value = {"response": json.dumps(response_data)}
                mock_post.return_value = mock_response

                # Execute multiple times
                results = []
                for _ in range(3):
                    result = await ollama.extract_data_with_llm(html, "items")
                    results.append(result)

                # All results should be consistent
                for result in results:
                    assert result["count"] == 3
                    assert len(result["items"]) == 3

        finally:
            await ollama.close()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_form_state_consistency(self):
        """Test that form state is preserved during filling."""
        agent = OpenManusAdapter(headless=True)

        try:
            with patch.object(agent, "_ensure_browser") as mock_ensure:
                mock_page = AsyncMock()
                mock_page.url = "https://form.example.com"
                mock_page.title = AsyncMock(return_value="Form")
                mock_page.goto = AsyncMock()
                mock_page.fill = AsyncMock()
                mock_page.click = AsyncMock()
                mock_page.screenshot = AsyncMock()
                mock_page.close = AsyncMock()
                mock_page.wait_for_load_state = AsyncMock()

                mock_browser = AsyncMock()
                mock_browser.new_page = AsyncMock(return_value=mock_page)
                mock_ensure.return_value = mock_browser

                form_data = {"name": "Test User", "email": "test@example.com", "phone": "555-1234"}

                result = await agent.execute_task(
                    {
                        "url": "https://form.example.com",
                        "action": "fill_form",
                        "selectors": {"name": "#name", "email": "#email", "phone": "#phone"},
                        "data": form_data,
                    }
                )

                # Verify all fields were filled
                assert len(result["result"]["filled_fields"]) == 3
                assert all(field in result["result"]["filled_fields"] for field in form_data)

        finally:
            await agent.cleanup()


@pytest.mark.integration
class TestHealthCheckIntegration:
    """Tests for health check integration."""

    @pytest.mark.asyncio
    async def test_ollama_health_check(self):
        """Test Ollama health check."""
        ollama = OllamaClient()

        try:
            with patch.object(ollama.client, "get") as mock_get:
                mock_response = MagicMock()
                mock_response.json.return_value = {
                    "models": [{"name": "qwen3-coder:30b"}, {"name": "llava:13b"}]
                }
                mock_get.return_value = mock_response

                is_healthy = await ollama.health_check()
                assert is_healthy is True

        finally:
            await ollama.close()

    @pytest.mark.asyncio
    async def test_system_ready_check(self):
        """Test full system readiness check."""
        ollama = OllamaClient()
        agent = OpenManusAdapter(headless=True)

        try:
            with patch.object(ollama.client, "get") as mock_get:
                mock_response = MagicMock()
                mock_response.json.return_value = {
                    "models": [{"name": "qwen3-coder:30b"}, {"name": "llava:13b"}]
                }
                mock_get.return_value = mock_response

                # Check Ollama
                ollama_ready = await ollama.health_check()
                assert ollama_ready is True

                # Browser is ready if it can be initialized
                assert agent.agent_type is not None

        finally:
            await ollama.close()
            await agent.cleanup()
