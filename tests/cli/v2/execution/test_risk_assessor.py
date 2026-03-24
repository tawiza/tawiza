"""Tests for risk assessor."""

import pytest

from src.cli.v2.execution.risk_assessor import RiskAssessor, RiskLevel


class TestRiskAssessor:
    @pytest.fixture
    def assessor(self):
        return RiskAssessor()

    def test_read_operations_are_safe(self, assessor):
        """Read-only operations should be safe."""
        assert assessor.assess("files.read", {"path": "/tmp/test.txt"}) == RiskLevel.SAFE
        assert assessor.assess("files.list", {"path": "/tmp"}) == RiskLevel.SAFE

    def test_write_operations_are_moderate(self, assessor):
        """File writes are moderate risk."""
        result = assessor.assess("files.write", {"path": "/tmp/out.txt", "content": "hi"})
        assert result == RiskLevel.MODERATE

    def test_delete_operations_are_high(self, assessor):
        """Delete operations are high risk."""
        result = assessor.assess("files.delete", {"path": "/tmp/file.txt"})
        assert result == RiskLevel.HIGH

    def test_system_commands_are_high(self, assessor):
        """System command execution is high risk."""
        result = assessor.assess("system.execute", {"command": "rm -rf /"})
        assert result == RiskLevel.HIGH

    def test_api_calls_are_moderate(self, assessor):
        """External API calls are moderate risk."""
        result = assessor.assess("api.request", {"url": "https://api.example.com"})
        assert result == RiskLevel.MODERATE

    def test_browser_navigation_is_safe(self, assessor):
        """Browser navigation is safe."""
        result = assessor.assess("browser.navigate", {"url": "https://google.com"})
        assert result == RiskLevel.SAFE

    def test_browser_click_is_moderate(self, assessor):
        """Browser clicks are moderate (may trigger actions)."""
        result = assessor.assess("browser.click", {"selector": "#submit"})
        assert result == RiskLevel.MODERATE

    def test_unknown_tools_are_moderate(self, assessor):
        """Unknown tools default to moderate risk."""
        result = assessor.assess("unknown.tool", {})
        assert result == RiskLevel.MODERATE

    def test_dangerous_patterns_override_moderate(self, assessor):
        """Dangerous patterns in params should override tool category."""
        result = assessor.assess("files.write", {"content": "sudo rm -rf /"})
        assert result == RiskLevel.HIGH

    def test_dangerous_patterns_in_any_param_value(self, assessor):
        """Dangerous patterns detected in any param value."""
        result = assessor.assess("api.request", {"body": "DROP TABLE users"})
        assert result == RiskLevel.HIGH
