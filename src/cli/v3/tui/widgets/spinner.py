"""Spinner Widget - Animated loading indicators."""

from textual.reactive import reactive
from textual.timer import Timer
from textual.widget import Widget


class Spinner(Widget):
    """Animated spinner for loading states.

    Supports multiple spinner styles:
    - dots: Braille dots animation
    - line: Line rotation
    - circle: Circle drawing
    - bounce: Bouncing bar
    - pulse: Pulsing dot
    """

    DEFAULT_CSS = """
    Spinner {
        width: auto;
        height: 1;
        padding: 0;
    }

    Spinner.large {
        height: 3;
    }
    """

    # Spinner animation frames
    SPINNERS = {
        "dots": ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
        "line": ["─", "\\", "│", "/"],
        "circle": ["◐", "◓", "◑", "◒"],
        "bounce": ["⠁", "⠂", "⠄", "⠂"],
        "pulse": ["●", "◐", "○", "◑"],
        "arrow": ["←", "↖", "↑", "↗", "→", "↘", "↓", "↙"],
        "box": ["▖", "▘", "▝", "▗"],
        "flip": ["_", "_", "_", "-", "`", "`", "'", "´", "-", "_", "_", "_"],
        "grow": ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█", "▇", "▆", "▅", "▄", "▃", "▂"],
        "thinking": ["🤔", "💭", "💡", "✨"],
    }

    is_spinning = reactive(False)
    frame = reactive(0)

    def __init__(
        self, style: str = "dots", text: str = "", color: str = "cyan", speed: float = 0.1, **kwargs
    ):
        super().__init__(**kwargs)
        self._style = style
        self._text = text
        self._color = color
        self._speed = speed
        self._frames = self.SPINNERS.get(style, self.SPINNERS["dots"])
        self._timer: Timer | None = None

    def render(self) -> str:
        """Render the spinner."""
        if not self.is_spinning:
            return ""

        frame_char = self._frames[self.frame % len(self._frames)]

        if self._text:
            return f"[{self._color}]{frame_char}[/] {self._text}"
        else:
            return f"[{self._color}]{frame_char}[/]"

    def start(self, text: str = "") -> None:
        """Start the spinner animation."""
        if text:
            self._text = text
        self.is_spinning = True
        self._timer = self.set_interval(self._speed, self._advance_frame)
        self.refresh()

    def stop(self) -> None:
        """Stop the spinner animation."""
        self.is_spinning = False
        if self._timer:
            self._timer.stop()
            self._timer = None
        self.refresh()

    def update_text(self, text: str) -> None:
        """Update the spinner text while running."""
        self._text = text
        self.refresh()

    def _advance_frame(self) -> None:
        """Advance to the next animation frame."""
        self.frame = (self.frame + 1) % len(self._frames)
        self.refresh()


class LoadingBar(Widget):
    """Animated loading bar with progress."""

    DEFAULT_CSS = """
    LoadingBar {
        width: 100%;
        height: 1;
        padding: 0 1;
    }
    """

    BLOCKS = " ▏▎▍▌▋▊▉█"

    progress = reactive(0.0)
    is_indeterminate = reactive(False)

    def __init__(
        self,
        width: int = 20,
        color: str = "cyan",
        label: str = "",
        show_percent: bool = True,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._width = width
        self._color = color
        self._label = label
        self._show_percent = show_percent
        self._pulse_pos = 0
        self._timer: Timer | None = None

    def render(self) -> str:
        """Render the loading bar."""
        if self.is_indeterminate:
            return self._render_indeterminate()

        # Calculate filled blocks
        filled = int(self.progress / 100 * self._width * 8)
        full_blocks = filled // 8
        partial = filled % 8

        # Build bar
        bar = "█" * full_blocks
        if partial > 0 and full_blocks < self._width:
            bar += self.BLOCKS[partial]
        bar += " " * (self._width - len(bar))

        # Format
        parts = []
        if self._label:
            parts.append(f"[bold]{self._label}[/]")
        parts.append(f"[{self._color}]{bar}[/]")
        if self._show_percent:
            parts.append(f"[bold]{self.progress:.0f}%[/]")

        return " ".join(parts)

    def _render_indeterminate(self) -> str:
        """Render indeterminate (pulsing) mode."""
        bar = list(" " * self._width)

        # Draw pulse (3 chars wide)
        for i in range(3):
            pos = (self._pulse_pos + i) % self._width
            intensity = 8 - abs(i - 1) * 3
            bar[pos] = self.BLOCKS[max(0, min(8, intensity))]

        bar_str = "".join(bar)

        parts = []
        if self._label:
            parts.append(f"[bold]{self._label}[/]")
        parts.append(f"[{self._color}]{bar_str}[/]")

        return " ".join(parts)

    def set_progress(self, value: float) -> None:
        """Set the progress (0-100)."""
        self.progress = max(0, min(100, value))
        self.refresh()

    def start_indeterminate(self, label: str = "Loading...") -> None:
        """Start indeterminate (pulsing) mode."""
        self._label = label
        self.is_indeterminate = True
        self._timer = self.set_interval(0.1, self._pulse)
        self.refresh()

    def stop_indeterminate(self) -> None:
        """Stop indeterminate mode."""
        self.is_indeterminate = False
        if self._timer:
            self._timer.stop()
            self._timer = None
        self.refresh()

    def _pulse(self) -> None:
        """Advance the pulse position."""
        self._pulse_pos = (self._pulse_pos + 1) % self._width
        self.refresh()


class ThinkingIndicator(Widget):
    """Animated "thinking" indicator with status text."""

    DEFAULT_CSS = """
    ThinkingIndicator {
        width: 100%;
        height: 3;
        padding: 1;
        background: $surface-lighten-1;
        border-left: thick $accent;
    }
    """

    THINKING_FRAMES = [
        "Thinking",
        "Thinking.",
        "Thinking..",
        "Thinking...",
    ]

    is_active = reactive(False)
    status = reactive("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._frame = 0
        self._timer: Timer | None = None

    def render(self) -> str:
        """Render the thinking indicator."""
        if not self.is_active:
            return ""

        thinking_text = self.THINKING_FRAMES[self._frame % len(self.THINKING_FRAMES)]
        spinner = Spinner.SPINNERS["dots"][self._frame % len(Spinner.SPINNERS["dots"])]

        lines = [f"[cyan]{spinner}[/] [bold]{thinking_text}[/]"]

        if self.status:
            lines.append(f"[dim]{self.status}[/]")

        return "\n".join(lines)

    def start(self, status: str = "") -> None:
        """Start the thinking animation."""
        self.status = status
        self.is_active = True
        self._timer = self.set_interval(0.3, self._advance_frame)
        self.refresh()

    def stop(self) -> None:
        """Stop the thinking animation."""
        self.is_active = False
        if self._timer:
            self._timer.stop()
            self._timer = None
        self.refresh()

    def update_status(self, status: str) -> None:
        """Update the status text."""
        self.status = status
        self.refresh()

    def _advance_frame(self) -> None:
        """Advance animation frame."""
        self._frame += 1
        self.refresh()


class TaskProgress(Widget):
    """Progress indicator for multi-step tasks."""

    DEFAULT_CSS = """
    TaskProgress {
        width: 100%;
        height: auto;
        padding: 1;
        background: $surface;
        border: round $primary;
    }
    """

    current_step = reactive(0)
    total_steps = reactive(1)

    def __init__(self, steps: list | None = None, **kwargs):
        super().__init__(**kwargs)
        self._steps = steps or ["Processing..."]
        self.total_steps = len(self._steps)

    def render(self) -> str:
        """Render the task progress."""
        lines = []

        for i, step in enumerate(self._steps):
            if i < self.current_step:
                # Completed
                lines.append(f"[green]✓[/] {step}")
            elif i == self.current_step:
                # Current
                frame = Spinner.SPINNERS["dots"][0]
                lines.append(f"[cyan]{frame}[/] [bold]{step}[/]")
            else:
                # Pending
                lines.append(f"[dim]○ {step}[/]")

        # Progress bar
        pct = (self.current_step / self.total_steps) * 100 if self.total_steps > 0 else 0
        bar_width = 20
        filled = int(pct / 100 * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        lines.append(f"\n[cyan]{bar}[/] {pct:.0f}%")

        return "\n".join(lines)

    def advance(self) -> None:
        """Advance to the next step."""
        if self.current_step < self.total_steps:
            self.current_step += 1
            self.refresh()

    def complete(self) -> None:
        """Mark all steps as complete."""
        self.current_step = self.total_steps
        self.refresh()

    def reset(self) -> None:
        """Reset progress."""
        self.current_step = 0
        self.refresh()

    def set_step(self, step: int) -> None:
        """Set the current step."""
        self.current_step = max(0, min(step, self.total_steps))
        self.refresh()
