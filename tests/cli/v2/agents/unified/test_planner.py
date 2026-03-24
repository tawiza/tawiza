"""Tests for the ReAct planner."""

import json
from unittest.mock import AsyncMock, Mock

import pytest

from src.cli.v2.agents.unified.models import ToolCall
from src.cli.v2.agents.unified.planner import PlanResult, ReActPlanner


class TestReActPlanner:
    """Test suite for ReActPlanner."""

    @pytest.fixture
    def mock_ollama(self):
        """Create a mock Ollama client."""
        client = Mock()
        client.chat = AsyncMock()
        return client

    @pytest.fixture
    def planner(self, mock_ollama):
        """Create a planner instance."""
        return ReActPlanner(ollama_client=mock_ollama, model="qwen2.5-coder:7b")

    @pytest.mark.asyncio
    async def test_plan_next_action_simple(self, planner, mock_ollama):
        """Test planning a simple action."""
        # Mock LLM response
        mock_ollama.chat.return_value = {
            "message": {
                "content": json.dumps(
                    {
                        "thought": "I need to search for information",
                        "tool": "browser.search",
                        "params": {"query": "test query"},
                    }
                )
            }
        }

        result = await planner.plan_next_action(
            task="Search for test query",
            history=[],
            tools_description="browser.search(query: str): Search the web",
            context={},
        )

        assert isinstance(result, PlanResult)
        assert result.thought == "I need to search for information"
        assert result.tool_call.name == "browser.search"
        assert result.tool_call.params == {"query": "test query"}

    @pytest.mark.asyncio
    async def test_plan_next_action_with_markdown(self, planner, mock_ollama):
        """Test parsing response with markdown code blocks."""
        # Mock LLM response with markdown
        mock_ollama.chat.return_value = {
            "message": {
                "content": """```json
{
  "thought": "Let me navigate to the page",
  "tool": "browser.navigate",
  "params": {"url": "https://example.com"}
}
```"""
            }
        }

        result = await planner.plan_next_action(
            task="Navigate to example.com",
            history=[],
            tools_description="browser.navigate(url: str): Navigate to URL",
            context={},
        )

        assert result.thought == "Let me navigate to the page"
        assert result.tool_call.name == "browser.navigate"
        assert result.tool_call.params == {"url": "https://example.com"}

    @pytest.mark.asyncio
    async def test_plan_next_action_finish(self, planner, mock_ollama):
        """Test planning a finish action."""
        mock_ollama.chat.return_value = {
            "message": {
                "content": json.dumps(
                    {
                        "thought": "Task is complete",
                        "tool": "finish",
                        "params": {"answer": "The answer is 42"},
                    }
                )
            }
        }

        result = await planner.plan_next_action(
            task="Find the answer", history=[], tools_description="", context={}
        )

        assert result.tool_call.name == "finish"
        assert result.tool_call.params == {"answer": "The answer is 42"}

    @pytest.mark.asyncio
    async def test_format_history(self, planner):
        """Test history formatting."""
        history = [
            {
                "thought": "I should search",
                "tool_call": ToolCall(name="browser.search", params={"query": "test"}),
                "observation": {"result": "Found results"},
            }
        ]

        formatted = planner._format_history(history)

        assert "I should search" in formatted
        assert "browser.search" in formatted
        assert "Found results" in formatted

    @pytest.mark.asyncio
    async def test_format_context(self, planner):
        """Test context formatting."""
        context = {"current_url": "https://example.com", "user_data": {"name": "Test User"}}

        formatted = planner._format_context(context)

        assert "current_url" in formatted
        assert "https://example.com" in formatted

    @pytest.mark.asyncio
    async def test_parse_response_invalid_json(self, planner, mock_ollama):
        """Test handling of invalid JSON response."""
        mock_ollama.chat.return_value = {"message": {"content": "This is not valid JSON at all"}}

        result = await planner.plan_next_action(
            task="Test task", history=[], tools_description="", context={}
        )

        # Should have graceful fallback
        assert result.thought is not None
        assert result.tool_call is not None

    @pytest.mark.asyncio
    async def test_parse_response_error_explanation(self, planner, mock_ollama):
        """Test fallback when LLM explains an error instead of JSON."""
        mock_ollama.chat.return_value = {
            "message": {
                "content": "The error indicates a limitation in the execution environment. Unable to proceed."
            }
        }

        result = await planner.plan_next_action(
            task="Test task", history=[], tools_description="", context={}
        )

        # Should detect error keywords and finish gracefully
        assert result.tool_call.name == "finish"
        assert (
            "limitation" in result.tool_call.params.get("answer", "").lower()
            or "error" in result.tool_call.params.get("answer", "").lower()
        )

    @pytest.mark.asyncio
    async def test_parse_response_partial_json(self, planner, mock_ollama):
        """Test fallback when JSON is malformed but has extractable fields."""
        mock_ollama.chat.return_value = {
            "message": {
                "content": '{"thought": "I need to search", "tool": "browser.search" some garbage here'
            }
        }

        result = await planner.plan_next_action(
            task="Test task", history=[], tools_description="", context={}
        )

        # Should extract what it can from partial JSON
        assert result.tool_call.name == "browser.search"
        assert "search" in result.thought.lower()
