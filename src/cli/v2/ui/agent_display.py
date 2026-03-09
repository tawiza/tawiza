"""Animated Agent Display - Centered mascot with progress bar and scrolling thoughts."""

import asyncio
import contextlib
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.text import Text


class AgentMood(Enum):
    """Agent mood states."""
    IDLE = "idle"
    THINKING = "thinking"
    WORKING = "working"
    SUCCESS = "success"
    ERROR = "error"


# Eye animations by mood
EYES = {
    AgentMood.IDLE: ["◉", "◉"],
    AgentMood.THINKING: ["◌", "◔", "◑", "◕", "●", "◕", "◑", "◔"],
    AgentMood.WORKING: ["◌", "◔", "◑", "◕", "●", "◕", "◑", "◔"],
    AgentMood.SUCCESS: ["◈", "◈"],
    AgentMood.ERROR: ["⊗", "⊗"],
}

MOUTHS = {
    AgentMood.IDLE: ".==.",
    AgentMood.THINKING: ".~~.",
    AgentMood.WORKING: ".==.",
    AgentMood.SUCCESS: ".^^.",
    AgentMood.ERROR: ".XX.",
}

BARS = "▁▂▃▄▅▆▇█"


def get_mascot_art(eyes: str, mouth: str, bar1: str, bar2: str) -> str:
    """Generate mascot ASCII art with current state."""
    return f"""[cyan]           _..-- `.`.   `.  `.  `.      --.._
          /    ___________\\   \\   \\______    \\
          |   |.-----------`.  `.  `.---.|   |
          |`. |'  \\`.        \\   \\   \\  '|   |
          |`. |'   \\ `-._     `.  `.  `.'|   |
         /|   |'    `-._{eyes})\\  /({eyes}\\   \\   \\|   |\\
       .' |   |'  `.     .'  '.  `.  `.  `.  | `.
      /  .|   |'    `.  (_{mouth}_)   \\   \\   \\ |.  \\
    .' .' |   |'      _.-======-._  `.  `.  `. `. `.
   /  /   |   |'    .'   |{bar1}||{bar2}|   `.  \\   \\   \\  \\  \\
  / .'    |`. |'   /_.-'========`-._\\  `.  `-._`._`. \\
 ( '      |`. |'._______________________.'\\      _.) ` )[/cyan]"""


@dataclass
class AgentState:
    """Current state of the agent display."""
    mood: AgentMood = AgentMood.IDLE
    thought: str = ""
    action: str | None = None
    progress: float = 0.0
    step: int = 0
    total_steps: int = 0
    elapsed: float = 0.0
    model: str = "qwen3.5:27b"
    frame: int = 0


class AgentDisplay:
    """Animated agent display manager."""

    def __init__(self, console: Console | None = None):
        self.console = console or Console()
        self.state = AgentState()
        self._live: Live | None = None
        self._running = False
        self._animation_task: asyncio.Task | None = None

    def _get_eyes(self) -> str:
        """Get current eye character based on mood and frame."""
        eye_frames = EYES[self.state.mood]
        if len(eye_frames) > 1:
            return f"[yellow]{eye_frames[self.state.frame % len(eye_frames)]}[/yellow]"
        return f"[yellow]{eye_frames[0]}[/yellow]"

    def _get_bars(self) -> tuple[str, str]:
        """Get animated bar characters."""
        bar1 = BARS[self.state.frame % len(BARS)]
        bar2 = BARS[(self.state.frame + 4) % len(BARS)]
        return bar1, bar2

    def _build_progress_bar(self, width: int = 40) -> Text:
        """Build progress bar with percentage."""
        filled = int(width * self.state.progress)
        empty = width - filled

        bar = Text()
        bar.append("[")
        bar.append("█" * filled, style="green")
        bar.append("░" * empty, style="dim")
        bar.append(f"] {int(self.state.progress * 100)}%")
        return bar

    def _build_display(self) -> Group:
        """Build the complete display."""
        parts = []

        # Header
        header = Text("◆ Tawiza Agent", style="bold magenta", justify="center")
        parts.append(Align.center(header))
        parts.append(Text(""))

        # Mascot
        eyes = self._get_eyes()
        mouth = MOUTHS[self.state.mood]
        bar1, bar2 = self._get_bars()
        mascot = get_mascot_art(eyes, mouth, bar1, bar2)
        parts.append(Align.center(Text.from_markup(mascot)))
        parts.append(Text(""))

        # Thought line
        if self.state.thought:
            thought_style = {
                AgentMood.THINKING: "yellow",
                AgentMood.WORKING: "cyan",
                AgentMood.SUCCESS: "green",
                AgentMood.ERROR: "red",
            }.get(self.state.mood, "white")

            thought_text = Text()
            thought_text.append("💭 ", style="dim")
            thought_text.append(self.state.thought, style=thought_style)
            parts.append(Align.center(thought_text))
            parts.append(Text(""))

        # Action line (if any)
        if self.state.action:
            action_text = Text()
            action_text.append("⚡ ", style="cyan")
            action_text.append(self.state.action, style="cyan bold")
            parts.append(Align.center(action_text))
            parts.append(Text(""))

        # Progress bar
        parts.append(Align.center(self._build_progress_bar()))
        parts.append(Text(""))

        # Footer
        step_info = f"Step {self.state.step}/{self.state.total_steps}" if self.state.total_steps else "..."
        footer = Text(f"{step_info} • {self.state.elapsed:.1f}s • {self.state.model}", style="dim")
        parts.append(Align.center(footer))

        return Group(*parts)

    async def _animate(self):
        """Animation loop."""
        while self._running:
            self.state.frame += 1
            if self._live:
                self._live.update(self._build_display())
            await asyncio.sleep(0.12)

    async def start(self):
        """Start the animated display."""
        self._running = True
        self._live = Live(
            self._build_display(),
            console=self.console,
            refresh_per_second=10,
            transient=False,
        )
        self._live.start()
        self._animation_task = asyncio.create_task(self._animate())

    async def stop(self):
        """Stop the animated display."""
        self._running = False
        if self._animation_task:
            self._animation_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._animation_task
        if self._live:
            self._live.stop()

    def update(
        self,
        mood: AgentMood | None = None,
        thought: str | None = None,
        action: str | None = None,
        progress: float | None = None,
        step: int | None = None,
        total_steps: int | None = None,
        elapsed: float | None = None,
    ):
        """Update display state."""
        if mood is not None:
            self.state.mood = mood
        if thought is not None:
            self.state.thought = thought
        if action is not None:
            self.state.action = action
        if progress is not None:
            self.state.progress = progress
        if step is not None:
            self.state.step = step
        if total_steps is not None:
            self.state.total_steps = total_steps
        if elapsed is not None:
            self.state.elapsed = elapsed

    def show_result(self, result: str, success: bool = True):
        """Show final result panel."""
        if self._live:
            self._live.stop()

        style = "green" if success else "red"
        icon = "✓" if success else "✗"

        result_panel = Panel(
            Align.center(Text(result, style="bold")),
            title=f"[{style}]{icon} Résultat[/{style}]",
            border_style=style,
            padding=(1, 2),
        )
        self.console.print("")
        self.console.print(Align.center(result_panel))


# Convenience function for simple usage
async def run_with_display(
    console: Console,
    model: str,
    task_fn: Callable,
) -> any:
    """Run a task with animated display."""
    display = AgentDisplay(console)
    display.state.model = model

    try:
        await display.start()
        result = await task_fn(display)
        return result
    finally:
        await display.stop()
