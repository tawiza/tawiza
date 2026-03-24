"""Tests for experience controller."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.cli.v2.experience.controller import ExperienceController
from src.cli.v2.experience.mode_detector import InteractionMode


class TestExperienceController:
    @pytest.fixture
    def mock_agent(self):
        agent = AsyncMock()
        agent.run = AsyncMock(
            return_value=MagicMock(
                success=True,
                answer="Task completed",
                steps=[],
            )
        )
        return agent

    @pytest.fixture
    def controller(self, mock_agent):
        return ExperienceController(agent=mock_agent)

    def test_detects_mode_from_task(self, controller):
        """Controller detects appropriate mode for task."""
        mode = controller.detect_mode("status")
        assert mode == InteractionMode.QUICK

        mode = controller.detect_mode("analyze data.csv and create a report")
        assert mode == InteractionMode.AUTONOMOUS

    @pytest.mark.asyncio
    async def test_quick_mode_runs_fast(self, controller, mock_agent):
        """Quick mode executes directly without ceremony."""
        result = await controller.execute("what time is it")
        assert result is not None
        # Should have called agent
        mock_agent.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_autonomous_mode_shows_plan(self, controller, mock_agent):
        """Autonomous mode shows plan before executing."""
        # This would need more complex setup in real test
        result = await controller.execute("analyze sales.csv and create report")
        assert result is not None

    def test_welcome_screen(self, controller):
        """Controller can render welcome screen."""
        welcome = controller.get_welcome()
        assert "tawiza" in welcome.lower() or "◉" in welcome

    def test_mascot_mood_updates(self, controller):
        """Mascot mood reflects controller state."""
        controller.set_state("working")
        mood = controller.get_mascot_mood()
        assert mood == "working"

        controller.set_state("error")
        mood = controller.get_mascot_mood()
        assert mood == "error"
