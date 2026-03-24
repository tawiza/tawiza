"""Tests for smart prompt."""

from pathlib import Path

import pytest

from src.cli.v2.experience.smart_prompt import SmartPrompt


class TestSmartPrompt:
    @pytest.fixture
    def prompt(self):
        return SmartPrompt()

    def test_welcome_includes_mascot(self, prompt):
        """Welcome screen includes mascot."""
        output = prompt.render_welcome()
        # Should have mascot eyes or art
        assert "◉" in output or "tawiza" in output.lower()

    def test_welcome_includes_status(self, prompt):
        """Welcome includes basic status indicators."""
        output = prompt.render_welcome()
        # Should mention system readiness
        assert "ready" in output.lower() or "online" in output.lower() or "●" in output

    def test_context_detection_python_project(self, prompt, tmp_path):
        """Detects Python project and suggests relevant actions."""
        (tmp_path / "main.py").write_text("print('hello')")
        (tmp_path / "requirements.txt").write_text("requests")

        context = prompt.detect_context(tmp_path)
        assert "python" in context.project_type.lower()

    def test_context_detection_data_files(self, prompt, tmp_path):
        """Detects data files and suggests analysis."""
        (tmp_path / "data.csv").write_text("a,b\n1,2")

        context = prompt.detect_context(tmp_path)
        assert "csv" in [f.suffix for f in context.data_files] or len(context.data_files) > 0

    def test_suggestions_based_on_context(self, prompt, tmp_path):
        """Generates suggestions based on detected context."""
        (tmp_path / "app.py").write_text("# Python app")

        context = prompt.detect_context(tmp_path)
        suggestions = prompt.get_suggestions(context)

        assert len(suggestions) >= 1
        assert any("code" in s.lower() or "run" in s.lower() for s in suggestions)

    def test_recent_tasks_shown(self, prompt):
        """Shows recent tasks if available."""
        prompt.add_recent_task("analyze sales.csv")
        prompt.add_recent_task("fix auth bug")

        output = prompt.render_welcome()
        assert "sales" in output or "auth" in output or "Recent" in output
