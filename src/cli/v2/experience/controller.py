"""Experience controller - orchestrates the unified UX."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from src.cli.v2.ui.mascot_live import DisplayMode, LiveMascot

from .mode_detector import InteractionMode, ModeDetector
from .result_presenter import ResultPresenter
from .smart_prompt import SmartPrompt


@dataclass
class ExecutionResult:
    """Result of task execution."""
    success: bool
    output: Any
    mode_used: InteractionMode
    steps_taken: int = 0
    error: str | None = None


class ExperienceController:
    """Orchestrates the unified CLI experience.

    Coordinates mode detection, agent execution, mascot display,
    and result presentation.
    """

    STATE_MOODS = {
        "idle": "default",
        "working": "working",
        "thinking": "thinking",
        "success": "success",
        "error": "error",
        "waiting": "waiting",
    }

    def __init__(
        self,
        agent: Any = None,
        on_progress: Callable | None = None,
    ):
        """Initialize the experience controller.

        Args:
            agent: The unified agent to use for execution
            on_progress: Optional callback for progress updates
        """
        self.agent = agent
        self.on_progress = on_progress

        self.mode_detector = ModeDetector()
        self.smart_prompt = SmartPrompt()
        self.result_presenter = ResultPresenter()
        self.mascot = LiveMascot()

        self._state = "idle"

    def detect_mode(self, task: str) -> InteractionMode:
        """Detect the appropriate mode for a task.

        Args:
            task: The user's task description

        Returns:
            Detected InteractionMode
        """
        result = self.mode_detector.detect(task)
        return result.mode

    async def execute(
        self,
        task: str,
        data: str | None = None,
        force_mode: InteractionMode | None = None,
    ) -> ExecutionResult:
        """Execute a task using the appropriate mode.

        Args:
            task: Task description
            data: Optional data file path
            force_mode: Override auto-detected mode

        Returns:
            ExecutionResult with output
        """
        # Detect or use forced mode
        mode = force_mode or self.detect_mode(task)

        self.set_state("thinking")

        try:
            # Execute via agent
            if self.agent:
                result = await self.agent.run(task=task, data=data)

                self.set_state("success" if result.success else "error")

                # Store result for chaining
                self.result_presenter.store_result("last", result.answer)
                self.smart_prompt.add_recent_task(task)

                return ExecutionResult(
                    success=result.success,
                    output=result.answer,
                    mode_used=mode,
                    steps_taken=len(result.steps) if result.steps else 0,
                    error=getattr(result, "error", None),
                )
            else:
                self.set_state("error")
                return ExecutionResult(
                    success=False,
                    output=None,
                    mode_used=mode,
                    error="No agent configured",
                )

        except Exception as e:
            self.set_state("error")
            return ExecutionResult(
                success=False,
                output=None,
                mode_used=mode,
                error=str(e),
            )

    def get_welcome(self, version: str = "2.0") -> str:
        """Get the welcome screen.

        Args:
            version: Version to display

        Returns:
            Welcome screen string
        """
        return self.smart_prompt.render_welcome(version)

    def set_state(self, state: str) -> None:
        """Set the controller state.

        Args:
            state: New state (idle, working, thinking, success, error, waiting)
        """
        self._state = state

    def get_state(self) -> str:
        """Get current state.

        Returns:
            Current state string
        """
        return self._state

    def get_mascot_mood(self) -> str:
        """Get mascot mood for current state.

        Returns:
            Mood string for mascot
        """
        return self.STATE_MOODS.get(self._state, "default")

    def render_mascot(self, display_mode: DisplayMode = DisplayMode.STATUS_BAR) -> str:
        """Render mascot in current mood.

        Args:
            display_mode: How to display the mascot

        Returns:
            Rendered mascot string
        """
        return self.mascot.render(display_mode, mood=self.get_mascot_mood())
