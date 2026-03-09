"""Adaptive progress display for different task complexities."""

from dataclasses import dataclass
from enum import Enum


class ProgressStyle(Enum):
    """Progress display styles."""
    MINIMAL = "minimal"    # Single line, quick tasks
    SUMMARY = "summary"    # Step counter + current action
    DETAILED = "detailed"  # Full reasoning + results


@dataclass
class AdaptiveProgress:
    """Adaptive progress display that scales with task complexity."""

    def render(
        self,
        style: ProgressStyle,
        message: str,
        percent: float = 0,
        current_step: int = 0,
        total_steps: int = 0,
        tool_name: str | None = None,
        tool_result: str | None = None,
        thought: str | None = None,
    ) -> str:
        """Render progress in specified style.

        Args:
            style: Display style
            message: Current status message
            percent: Completion percentage (0-100)
            current_step: Current step number
            total_steps: Total steps
            tool_name: Name of current tool
            tool_result: Result from tool (truncated)
            thought: Agent's reasoning

        Returns:
            Rendered progress string
        """
        if style == ProgressStyle.MINIMAL:
            return self._render_minimal(message, percent)
        elif style == ProgressStyle.SUMMARY:
            return self._render_summary(message, current_step, total_steps, tool_name)
        else:
            return self._render_detailed(
                message, current_step, total_steps, tool_name, tool_result, thought
            )

    def _render_minimal(self, message: str, percent: float) -> str:
        """Render minimal single-line progress."""
        bar = self.render_bar(percent, width=10)
        return f"{bar} {message}"

    def _render_summary(
        self,
        message: str,
        current_step: int,
        total_steps: int,
        tool_name: str | None,
    ) -> str:
        """Render summary progress with step info."""
        lines = []

        step_info = f"[{current_step}/{total_steps}]" if total_steps else ""
        tool_info = f"[{tool_name}]" if tool_name else ""

        lines.append(f"{step_info} {tool_info} {message}".strip())

        return "\n".join(lines)

    def _render_detailed(
        self,
        message: str,
        current_step: int,
        total_steps: int,
        tool_name: str | None,
        tool_result: str | None,
        thought: str | None,
    ) -> str:
        """Render detailed progress with reasoning."""
        lines = []

        # Step header
        step_info = f"Step {current_step}/{total_steps}" if total_steps else "Step"
        lines.append(f"─── {step_info} ───")

        # Thought/reasoning
        if thought:
            lines.append(f"Thinking: {thought[:100]}...")

        # Current action
        if tool_name:
            lines.append(f"Action: {tool_name}")

        # Result preview
        if tool_result:
            preview = tool_result[:80] + "..." if len(tool_result) > 80 else tool_result
            lines.append(f"Result: {preview}")

        return "\n".join(lines)

    def render_bar(self, percent: float, width: int = 20) -> str:
        """Render a progress bar.

        Args:
            percent: Completion percentage (0-100)
            width: Bar width in characters

        Returns:
            Progress bar string
        """
        filled = int(width * percent / 100)
        empty = width - filled
        return f"{'█' * filled}{'░' * empty}"

    def auto_select_style(self, estimated_steps: int) -> ProgressStyle:
        """Auto-select style based on task complexity.

        Args:
            estimated_steps: Estimated number of steps

        Returns:
            Appropriate ProgressStyle
        """
        if estimated_steps <= 2:
            return ProgressStyle.MINIMAL
        elif estimated_steps <= 8:
            return ProgressStyle.SUMMARY
        else:
            return ProgressStyle.DETAILED
