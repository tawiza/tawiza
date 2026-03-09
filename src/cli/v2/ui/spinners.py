"""Spinners and animations for Tawiza CLI v2."""

from contextlib import contextmanager

try:
    from yaspin import yaspin
    from yaspin.spinners import Spinners
    YASPIN_AVAILABLE = True
except ImportError:
    YASPIN_AVAILABLE = False


# Wave spinner frames
WAVE_FRAMES: list[str] = [
    "▁▂▃▄▅▆▇█▇▆▅▄▃▂▁",
    "▂▃▄▅▆▇█▇▆▅▄▃▂▁▁",
    "▃▄▅▆▇█▇▆▅▄▃▂▁▁▂",
    "▄▅▆▇█▇▆▅▄▃▂▁▁▂▃",
    "▅▆▇█▇▆▅▄▃▂▁▁▂▃▄",
    "▆▇█▇▆▅▄▃▂▁▁▂▃▄▅",
    "▇█▇▆▅▄▃▂▁▁▂▃▄▅▆",
    "█▇▆▅▄▃▂▁▁▂▃▄▅▆▇",
    "▇▆▅▄▃▂▁▁▂▃▄▅▆▇█",
    "▆▅▄▃▂▁▁▂▃▄▅▆▇█▇",
    "▅▄▃▂▁▁▂▃▄▅▆▇█▇▆",
    "▄▃▂▁▁▂▃▄▅▆▇█▇▆▅",
    "▃▂▁▁▂▃▄▅▆▇█▇▆▅▄",
    "▂▁▁▂▃▄▅▆▇█▇▆▅▄▃",
    "▁▁▂▃▄▅▆▇█▇▆▅▄▃▂",
]


class WaveSpinner:
    """Wave spinner animation."""

    def __init__(self):
        self.frames = WAVE_FRAMES
        self.current_index = 0

    def next(self) -> str:
        """Get next frame."""
        frame = self.frames[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.frames)
        return frame

    def reset(self) -> None:
        """Reset to first frame."""
        self.current_index = 0


# Pre-configured wave spinner
wave_spinner = WaveSpinner()


@contextmanager
def create_spinner(text: str = "Processing...", spinner_type: str = "dots"):
    """Create a spinner context manager.

    Args:
        text: Text to display next to spinner
        spinner_type: Type of spinner (dots, line, arc, wave)

    Yields:
        Spinner instance (yaspin if available, else simple)
    """
    if YASPIN_AVAILABLE:
        if spinner_type == "wave":
            # Custom wave spinner
            sp = yaspin(text=text)
            sp._frames = WAVE_FRAMES
        elif spinner_type == "dots":
            sp = yaspin(Spinners.dots, text=text)
        elif spinner_type == "line":
            sp = yaspin(Spinners.line, text=text)
        elif spinner_type == "arc":
            sp = yaspin(Spinners.arc, text=text)
        else:
            sp = yaspin(text=text)

        sp.start()
        try:
            yield sp
        finally:
            sp.stop()
    else:
        # Fallback without yaspin
        from rich.console import Console
        console = Console()
        console.print(f"[cyan]⠋[/] {text}")
        try:
            yield None
        finally:
            pass


class ProgressBar:
    """Simple progress bar."""

    def __init__(self, width: int = 20):
        self.width = width
        self.filled_char = "█"
        self.empty_char = "░"

    def render(self, progress: float) -> str:
        """Render progress bar (0.0 to 1.0)."""
        progress = min(max(progress, 0), 1)
        filled = int(self.width * progress)
        empty = self.width - filled
        percentage = int(progress * 100)
        return f"{self.filled_char * filled}{self.empty_char * empty} {percentage}%"


# Pre-configured progress bar
progress_bar = ProgressBar()
