"""Live mascot display with real-time animations."""

from dataclasses import dataclass
from enum import Enum

from .mascot import LOADING_EYES, MASCOT


class DisplayMode(Enum):
    """Mascot display modes."""

    STATUS_BAR = "status_bar"  # Single line indicator
    CONTEXTUAL = "contextual"  # Medium display with message
    FULL = "full"  # Full mascot art


# Eye symbols for each mood (for status bar)
MOOD_EYES = {
    "default": "◉◉",
    "working": "●●",
    "success": "◈◈",
    "thinking": "◐◑",
    "error": "⊗⊗",
    "loading": "◔◔",
    "waiting": "◑◐",  # Half-eyes for waiting on user
}

# Status messages for each mood
MOOD_STATUS = {
    "default": "ready",
    "working": "working",
    "success": "done",
    "thinking": "thinking",
    "error": "error",
    "loading": "loading",
    "waiting": "waiting",
}


@dataclass
class LiveMascot:
    """Live mascot with display mode support."""

    def render(
        self,
        mode: DisplayMode,
        mood: str = "default",
        message: str | None = None,
    ) -> str:
        """Render mascot in specified display mode.

        Args:
            mode: Display mode (status_bar, contextual, full)
            mood: Current mood for eye expression
            message: Optional message to display

        Returns:
            Rendered mascot string
        """
        if mode == DisplayMode.STATUS_BAR:
            return self._render_status_bar(mood)
        elif mode == DisplayMode.CONTEXTUAL:
            return self._render_contextual(mood, message)
        else:
            return self._render_full(mood, message)

    def _render_status_bar(self, mood: str) -> str:
        """Render compact status bar."""
        eyes = MOOD_EYES.get(mood, MOOD_EYES["default"])
        status = MOOD_STATUS.get(mood, "ready")
        return f"{eyes} {status}"

    def _render_contextual(self, mood: str, message: str | None) -> str:
        """Render medium contextual display."""
        eyes = MOOD_EYES.get(mood, MOOD_EYES["default"])
        lines = [
            f"  {eyes}",
            f"  ╰─ {message or MOOD_STATUS.get(mood, 'ready')}",
        ]
        return "\n".join(lines)

    def _render_full(self, mood: str, message: str | None) -> str:
        """Render full mascot art."""
        art_lines = MASCOT.get_art(mood)
        if message:
            art_lines.append("")
            art_lines.append(f"                    {message}")
        return "\n".join(art_lines)

    def get_loading_frame(self, frame_index: int) -> str:
        """Get a specific loading animation frame.

        Args:
            frame_index: Index into the loading animation

        Returns:
            Eye symbol for this frame
        """
        idx = frame_index % len(LOADING_EYES)
        eye = LOADING_EYES[idx]
        return f"{eye}{eye}"

    def get_eyes(self, mood: str) -> str:
        """Get eye symbols for a mood.

        Args:
            mood: The mood name

        Returns:
            Eye symbol pair
        """
        return MOOD_EYES.get(mood, MOOD_EYES["default"])
