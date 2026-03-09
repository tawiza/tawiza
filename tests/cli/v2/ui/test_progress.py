"""Tests for adaptive progress display."""

import pytest

from src.cli.v2.ui.progress import AdaptiveProgress, ProgressStyle


class TestAdaptiveProgress:
    @pytest.fixture
    def progress(self):
        return AdaptiveProgress()

    def test_minimal_style_single_line(self, progress):
        """Minimal style shows single line."""
        output = progress.render(
            style=ProgressStyle.MINIMAL,
            message="Loading",
            percent=50,
        )
        assert "\n" not in output
        assert "Loading" in output or "50" in output

    def test_summary_style_with_steps(self, progress):
        """Summary style shows current step info."""
        output = progress.render(
            style=ProgressStyle.SUMMARY,
            message="Analyzing data",
            current_step=2,
            total_steps=5,
            tool_name="analyst.query",
        )
        assert "Analyzing" in output or "analyst" in output
        assert "2" in output or "5" in output

    def test_detailed_style_shows_reasoning(self, progress):
        """Detailed style shows thought/reasoning."""
        output = progress.render(
            style=ProgressStyle.DETAILED,
            message="Processing",
            current_step=1,
            total_steps=3,
            thought="I need to load the CSV first",
            tool_name="files.read",
            tool_result="Loaded 1000 rows",
        )
        assert "CSV" in output or "thought" in output.lower() or "load" in output.lower()

    def test_progress_bar_rendering(self, progress):
        """Progress bar shows visual progress."""
        output = progress.render_bar(percent=75, width=10)
        # Should have filled and empty portions
        assert "█" in output or "▓" in output or "=" in output

    def test_auto_style_selection(self, progress):
        """Style auto-selects based on complexity."""
        # Short task = minimal
        style = progress.auto_select_style(estimated_steps=1)
        assert style == ProgressStyle.MINIMAL

        # Medium task = summary
        style = progress.auto_select_style(estimated_steps=5)
        assert style == ProgressStyle.SUMMARY

        # Long task = detailed
        style = progress.auto_select_style(estimated_steps=15)
        assert style == ProgressStyle.DETAILED
