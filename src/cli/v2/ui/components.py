"""Reusable UI components for Tawiza CLI v2."""

from dataclasses import dataclass, field

from rich.console import Console

from .spinners import ProgressBar
from .theme import STATUS, THEME, footer, header


@dataclass
class StatusBar:
    """Compact status bar with indicators."""

    items: list[tuple[str, str, str]] = field(default_factory=list)
    width: int = 40

    def add(self, label: str, value: str, status: str = "ok") -> "StatusBar":
        """Add a status item (label, value, status: ok/warn/err/pending)."""
        self.items.append((label, value, status))
        return self

    def clear(self) -> "StatusBar":
        """Clear all items."""
        self.items = []
        return self

    def render(self) -> str:
        """Render the status bar."""
        lines = []
        for label, value, status in self.items:
            indicator = STATUS.get(status, STATUS["pending"])
            color = {
                "ok": THEME["success"],
                "warn": THEME["warning"],
                "err": THEME["error"],
                "pending": THEME["dim"],
            }.get(status, THEME["dim"])

            line = f"  {label:<12}{value:<20}[{color}]{indicator}[/]"
            lines.append(line)

        return "\n".join(lines)


@dataclass
class Dashboard:
    """Dashboard with metrics display."""

    title: str
    metrics: dict[str, int] = field(default_factory=dict)
    width: int = 40
    mascot_mood: str = "working"
    message: str = ""

    def set_metric(self, name: str, value: int) -> "Dashboard":
        """Set a metric value (0-100)."""
        self.metrics[name] = min(max(value, 0), 100)
        return self

    def set_message(self, message: str, mood: str = "working") -> "Dashboard":
        """Set mascot message and mood."""
        self.message = message
        self.mascot_mood = mood
        return self

    def render(self) -> str:
        """Render the dashboard."""
        lines = [header(self.title, self.width)]
        lines.append("")

        # Metrics with progress bars
        progress = ProgressBar(width=10)
        for name, value in self.metrics.items():
            bar = progress.render(value / 100)
            lines.append(f"  {name:<8}{bar}")

        if self.message:
            lines.append("")
            lines.append(f"  {self.message}")

        lines.append("")
        lines.append(footer(self.width))

        return "\n".join(lines)


@dataclass
class MessageBox:
    """Message box for success/error/info displays."""

    def success(self, title: str, detail: str = "") -> str:
        """Render success message."""
        lines = [header("success", 40)]
        lines.append("")
        lines.append(f"  [green]●[/] {title}")
        if detail:
            lines.append(f"    [dim]{detail}[/]")
        lines.append("")
        lines.append(footer(40))
        return "\n".join(lines)

    def error(self, title: str, suggestions: list[str] = None) -> str:
        """Render error message."""
        lines = [header("error", 40)]
        lines.append("")
        lines.append(f"  [red]●[/] {title}")
        if suggestions:
            lines.append("")
            for s in suggestions:
                lines.append(f"    [dim]→ {s}[/]")
        lines.append("")
        lines.append(footer(40))
        return "\n".join(lines)

    def info(self, title: str, detail: str = "") -> str:
        """Render info message."""
        lines = [header("info", 40)]
        lines.append("")
        lines.append(f"  [cyan]●[/] {title}")
        if detail:
            lines.append(f"    [dim]{detail}[/]")
        lines.append("")
        lines.append(footer(40))
        return "\n".join(lines)

    def warning(self, title: str, detail: str = "") -> str:
        """Render warning message."""
        lines = [header("warning", 40)]
        lines.append("")
        lines.append(f"  [yellow]●[/] {title}")
        if detail:
            lines.append(f"    [dim]{detail}[/]")
        lines.append("")
        lines.append(footer(40))
        return "\n".join(lines)


# Singleton instances
STATUS_BAR = StatusBar()
MESSAGE_BOX = MessageBox()


def print_welcome(console: Console = None) -> None:
    """Print welcome screen with mascot."""
    if console is None:
        console = Console()

    from .mascot import mascot_welcome
    try:
        from src.core.constants import APP_VERSION
        version = APP_VERSION
    except ImportError:
        version = "2.0"

    console.print(mascot_welcome(version), style=THEME["accent"])


def print_status(console: Console = None) -> None:
    """Print system status."""
    if console is None:
        console = Console()

    console.print(header("tawiza status", 40))

    bar = StatusBar()

    # Check system
    bar.add("system", "online", "ok")

    # Check GPU
    try:
        import subprocess
        result = subprocess.run(
            ["rocm-smi", "--showid"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            bar.add("gpu", "amd ready", "ok")
        else:
            bar.add("gpu", "not available", "warn")
    except Exception:
        bar.add("gpu", "not detected", "warn")

    # Check Ollama
    try:
        import subprocess
        result = subprocess.run(
            ["curl", "-s", "http://localhost:11434/api/tags"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            bar.add("ollama", "running", "ok")
        else:
            bar.add("ollama", "not running", "warn")
    except Exception:
        bar.add("ollama", "unavailable", "warn")

    bar.add("agents", "ready", "ok")

    console.print(bar.render())
    console.print(footer(40))
