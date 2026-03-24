"""Tests for live mascot display."""

import pytest

from src.cli.v2.ui.mascot_live import DisplayMode, LiveMascot


class TestLiveMascot:
    @pytest.fixture
    def mascot(self):
        return LiveMascot()

    def test_status_bar_mode(self, mascot):
        """Status bar shows compact mascot."""
        output = mascot.render(DisplayMode.STATUS_BAR, mood="default")
        # Should be single line
        assert "\n" not in output
        assert "ready" in output.lower() or "◉" in output

    def test_contextual_mode(self, mascot):
        """Contextual mode shows medium mascot with message."""
        output = mascot.render(DisplayMode.CONTEXTUAL, mood="working", message="Analyzing...")
        assert "Analyzing" in output
        # Should have multiple lines but not full art
        lines = output.split("\n")
        assert 1 < len(lines) < 12

    def test_full_mode(self, mascot):
        """Full mode shows complete mascot art."""
        output = mascot.render(DisplayMode.FULL, mood="thinking")
        lines = output.split("\n")
        # Full mascot is 12 lines
        assert len(lines) >= 12

    def test_mood_changes_eyes(self, mascot):
        """Different moods show different eye symbols."""
        default = mascot.render(DisplayMode.STATUS_BAR, mood="default")
        error = mascot.render(DisplayMode.STATUS_BAR, mood="error")
        assert default != error

    def test_loading_animation_frames(self, mascot):
        """Loading mood cycles through animation frames."""
        frame1 = mascot.get_loading_frame(0)
        frame2 = mascot.get_loading_frame(1)
        assert frame1 != frame2
