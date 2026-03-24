"""Tests for unified agent models."""

import pytest

from src.cli.v2.agents.unified.models import AgentResult, AgentStep, Observation, ToolCall


class TestToolCall:
    def test_create_tool_call(self):
        tool = ToolCall(name="browser.navigate", params={"url": "https://example.com"})
        assert tool.name == "browser.navigate"
        assert tool.params["url"] == "https://example.com"

    def test_tool_call_to_dict(self):
        tool = ToolCall(name="finish", params={"answer": "Done"})
        d = tool.model_dump()
        assert d["name"] == "finish"


class TestObservation:
    def test_create_observation(self):
        obs = Observation(tool_name="browser.navigate", result={"status": "ok"}, success=True)
        assert obs.tool_name == "browser.navigate"
        assert obs.success is True


class TestAgentStep:
    def test_create_step(self):
        tool = ToolCall(name="test", params={})
        obs = Observation(tool_name="test", result={}, success=True)
        step = AgentStep(thought="I need to test", tool_call=tool, observation=obs)
        assert step.thought == "I need to test"


class TestAgentResult:
    def test_success_result(self):
        result = AgentResult(success=True, answer="Hello", steps=[], duration_seconds=1.5)
        assert result.success is True
        assert result.answer == "Hello"

    def test_failure_result(self):
        result = AgentResult(success=False, error="Max steps", steps=[], duration_seconds=5.0)
        assert result.success is False
        assert result.error == "Max steps"
