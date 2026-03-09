"""Action Timeline widget for displaying task steps."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from textual.containers import ScrollableContainer, Vertical
from textual.message import Message
from textual.widgets import Static


class StepStatus(Enum):
    """Status of a timeline step."""
    PENDING = "pending"
    CURRENT = "current"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TimelineStep:
    """A single step in the timeline."""
    step_id: str
    name: str
    status: StepStatus = StepStatus.PENDING
    timestamp: datetime | None = None
    duration_seconds: float | None = None
    has_screenshot: bool = False
    error: str | None = None


class TimelineStepWidget(Static):
    """Widget for a single timeline step."""

    DEFAULT_CSS = """
    TimelineStepWidget {
        height: 2;
        padding: 0 1;
    }

    TimelineStepWidget.current {
        background: $surface-lighten-1;
    }

    TimelineStepWidget:hover {
        background: $surface-lighten-2;
    }
    """

    def __init__(self, step: TimelineStep, is_last: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.step = step
        self.is_last = is_last
        if step.status == StepStatus.CURRENT:
            self.add_class("current")

    def render(self) -> str:
        """Render the timeline step."""
        # Status icon and connector
        icons = {
            StepStatus.PENDING: "[dim]○[/]",
            StepStatus.CURRENT: "[cyan bold]◉[/]",
            StepStatus.COMPLETED: "[green]●[/]",
            StepStatus.FAILED: "[red]✗[/]",
            StepStatus.SKIPPED: "[dim]○[/]",
        }
        icon = icons.get(self.step.status, "○")

        # Connector line
        connector = "│" if not self.is_last else " "
        if self.step.status == StepStatus.CURRENT:
            connector = f"[cyan]{connector}[/]"
        elif self.step.status == StepStatus.COMPLETED:
            connector = f"[green]{connector}[/]"
        else:
            connector = f"[dim]{connector}[/]"

        # Time
        time_str = ""
        if self.step.timestamp:
            time_str = f" [dim]{self.step.timestamp.strftime('%H:%M:%S')}[/]"

        # Duration
        duration_str = ""
        if self.step.duration_seconds is not None:
            if self.step.duration_seconds < 60:
                duration_str = f" [dim]({self.step.duration_seconds:.1f}s)[/]"
            else:
                duration_str = f" [dim]({self.step.duration_seconds/60:.1f}m)[/]"

        # Screenshot indicator
        screenshot_str = " [cyan][📷][/]" if self.step.has_screenshot else ""

        # Current indicator
        current_str = " [cyan]← current[/]" if self.step.status == StepStatus.CURRENT else ""

        # Name styling based on status
        if self.step.status == StepStatus.CURRENT:
            name = f"[bold]{self.step.name}[/]"
        elif self.step.status == StepStatus.COMPLETED:
            name = f"[green]{self.step.name}[/]"
        elif self.step.status == StepStatus.FAILED:
            name = f"[red]{self.step.name}[/]"
        else:
            name = f"[dim]{self.step.name}[/]"

        line1 = f"{icon}─ {name}{current_str}"
        line2 = f"{connector}  {time_str}{duration_str}{screenshot_str}"

        return f"{line1}\n{line2}"


class ActionTimeline(Vertical):
    """Timeline widget showing task progression."""

    DEFAULT_CSS = """
    ActionTimeline {
        width: 35;
        border: solid $primary;
        background: $surface;
    }

    ActionTimeline .title {
        dock: top;
        height: 1;
        background: $surface-darken-1;
        padding: 0 1;
        text-style: bold;
        color: $accent;
    }

    ActionTimeline ScrollableContainer {
        height: 1fr;
        padding: 1;
    }
    """

    class StepClicked(Message):
        """Message emitted when a step is clicked."""
        def __init__(self, step: TimelineStep):
            super().__init__()
            self.step = step

    def __init__(self, title: str = "ACTIONS TIMELINE", **kwargs):
        super().__init__(**kwargs)
        self._title = title
        self._steps: list[TimelineStep] = []

    def compose(self):
        """Compose the timeline."""
        yield Static(f"[bold cyan]{self._title}[/]", classes="title")
        with ScrollableContainer():
            for i, step in enumerate(self._steps):
                is_last = i == len(self._steps) - 1
                yield TimelineStepWidget(step, is_last=is_last, id=f"step-{step.step_id}")

    def set_steps(self, steps: list[TimelineStep]) -> None:
        """Set all steps."""
        self._steps = steps
        self.refresh(recompose=True)

    def add_step(self, step: TimelineStep) -> None:
        """Add a new step."""
        self._steps.append(step)
        self.refresh(recompose=True)

    def update_step(self, step_id: str, **updates) -> None:
        """Update a specific step."""
        for step in self._steps:
            if step.step_id == step_id:
                for key, value in updates.items():
                    if hasattr(step, key):
                        setattr(step, key, value)
                break
        self.refresh(recompose=True)

    def set_current_step(self, step_id: str) -> None:
        """Set the current step (marks others as completed or pending)."""
        found_current = False
        for step in self._steps:
            if step.step_id == step_id:
                step.status = StepStatus.CURRENT
                step.timestamp = datetime.now()
                found_current = True
            elif not found_current:
                if step.status != StepStatus.FAILED:
                    step.status = StepStatus.COMPLETED
            else:
                if step.status not in (StepStatus.FAILED, StepStatus.SKIPPED):
                    step.status = StepStatus.PENDING
        self.refresh(recompose=True)

    def complete_step(self, step_id: str, duration: float | None = None) -> None:
        """Mark a step as completed."""
        self.update_step(step_id, status=StepStatus.COMPLETED, duration_seconds=duration)

    def fail_step(self, step_id: str, error: str | None = None) -> None:
        """Mark a step as failed."""
        self.update_step(step_id, status=StepStatus.FAILED, error=error)

    def get_current_step(self) -> TimelineStep | None:
        """Get the current step."""
        for step in self._steps:
            if step.status == StepStatus.CURRENT:
                return step
        return None

    def clear(self) -> None:
        """Clear all steps."""
        self._steps.clear()
        self.refresh(recompose=True)
