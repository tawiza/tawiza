"""Task List widget for displaying agent tasks."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from textual.containers import ScrollableContainer, Vertical
from textual.message import Message
from textual.widgets import Static


class TaskStatus(Enum):
    """Task status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


@dataclass
class TaskInfo:
    """Task information dataclass."""
    task_id: str
    agent: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    iterations: int = 0
    tokens_used: int = 0
    model: str = "default"


class TaskListItem(Static):
    """Single task item widget."""

    DEFAULT_CSS = """
    TaskListItem {
        height: 3;
        padding: 0 1;
        border-bottom: solid $surface-lighten-1;
    }

    TaskListItem:hover {
        background: $surface-lighten-1;
    }

    TaskListItem.selected {
        background: $primary-background;
    }

    TaskListItem.running {
        border-left: thick $accent;
    }

    TaskListItem.failed {
        border-left: thick $error;
    }

    TaskListItem.completed {
        border-left: thick $success;
    }

    TaskListItem.pending {
        border-left: thick $warning;
    }

    TaskListItem.paused {
        border-left: thick $secondary;
    }
    """

    def __init__(self, task: TaskInfo, **kwargs):
        super().__init__(**kwargs)
        self.task = task
        self.add_class(task.status.value)

    def render(self) -> str:
        """Render the task item."""
        # Status icon
        status_icons = {
            TaskStatus.PENDING: "[yellow]◌[/]",
            TaskStatus.RUNNING: "[cyan]▶[/]",
            TaskStatus.COMPLETED: "[green]✓[/]",
            TaskStatus.FAILED: "[red]✗[/]",
            TaskStatus.PAUSED: "[yellow]⏸[/]",
            TaskStatus.CANCELLED: "[dim]○[/]",
        }
        icon = status_icons.get(self.task.status, "?")

        # Progress bar for running tasks
        progress_str = ""
        if self.task.status == TaskStatus.RUNNING:
            filled = int(self.task.progress / 10)
            empty = 10 - filled
            progress_str = f" [cyan]{'█' * filled}{'░' * empty}[/] {self.task.progress:.0f}%"

        # Duration
        duration_str = self._get_duration_str()

        # Main line
        desc = self.task.description[:35]
        if len(self.task.description) > 35:
            desc += "..."

        line1 = f"{icon} [bold]{self.task.agent}[/] - {desc}"
        line2 = f"   [dim]{self.task.task_id[:8]}[/]{progress_str}{duration_str}"

        return f"{line1}\n{line2}"

    def _get_duration_str(self) -> str:
        """Get formatted duration string."""
        if not self.task.started_at:
            return ""

        if self.task.completed_at:
            duration = (self.task.completed_at - self.task.started_at).total_seconds()
        else:
            duration = (datetime.now() - self.task.started_at).total_seconds()

        color = "green" if duration < 30 else "yellow" if duration < 120 else "red"

        if duration < 60:
            return f" [{color}]{duration:.0f}s[/]"
        elif duration < 3600:
            return f" [{color}]{duration/60:.1f}m[/]"
        else:
            return f" [{color}]{duration/3600:.1f}h[/]"


class TaskList(Vertical):
    """Task list container widget."""

    DEFAULT_CSS = """
    TaskList {
        height: 100%;
        border: solid $success;
        background: $surface;
    }

    TaskList .title {
        dock: top;
        height: 1;
        background: $surface-darken-1;
        padding: 0 1;
        text-style: bold;
        color: $accent;
    }

    TaskList .empty-message {
        height: 100%;
        content-align: center middle;
        color: $text-muted;
    }

    TaskList ScrollableContainer {
        height: 1fr;
    }
    """

    class TaskSelected(Message):
        """Message emitted when a task is selected."""
        def __init__(self, task: TaskInfo):
            super().__init__()
            self.task = task

    class TaskAction(Message):
        """Message emitted when an action is requested on a task."""
        def __init__(self, task: TaskInfo, action: str):
            super().__init__()
            self.task = task
            self.action = action

    def __init__(
        self,
        title: str = "Active Agents",
        tasks: list[TaskInfo] | None = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.title_text = title
        self._tasks = tasks or []
        self.selected_index = 0

    def compose(self):
        """Compose the task list."""
        yield Static(f"[bold cyan]{self.title_text}[/]", classes="title")

        if not self._tasks:
            yield Static("[dim]No active tasks[/]", classes="empty-message")
        else:
            with ScrollableContainer():
                for i, task in enumerate(self._tasks):
                    item = TaskListItem(task, id=f"task-{task.task_id}")
                    if i == self.selected_index:
                        item.add_class("selected")
                    yield item

    def update_tasks(self, tasks: list[TaskInfo]) -> None:
        """Update the task list with new tasks."""
        self._tasks = tasks
        self.refresh(recompose=True)

    def add_task(self, task: TaskInfo) -> None:
        """Add a new task to the list."""
        self._tasks.insert(0, task)
        self.refresh(recompose=True)

    def remove_task(self, task_id: str) -> None:
        """Remove a task from the list."""
        self._tasks = [t for t in self._tasks if t.task_id != task_id]
        self.refresh(recompose=True)

    def update_task(self, task_id: str, **updates) -> None:
        """Update a specific task's properties."""
        for task in self._tasks:
            if task.task_id == task_id:
                for key, value in updates.items():
                    if hasattr(task, key):
                        setattr(task, key, value)
                break
        self.refresh(recompose=True)

    def get_selected_task(self) -> TaskInfo | None:
        """Get the currently selected task."""
        if 0 <= self.selected_index < len(self._tasks):
            return self._tasks[self.selected_index]
        return None

    def select_next(self) -> None:
        """Select the next task."""
        if self._tasks:
            self.selected_index = (self.selected_index + 1) % len(self._tasks)
            self._update_selection()

    def select_previous(self) -> None:
        """Select the previous task."""
        if self._tasks:
            self.selected_index = (self.selected_index - 1) % len(self._tasks)
            self._update_selection()

    def _update_selection(self) -> None:
        """Update visual selection state."""
        for i, child in enumerate(self.query(TaskListItem)):
            if i == self.selected_index:
                child.add_class("selected")
            else:
                child.remove_class("selected")

        # Post selection message
        if task := self.get_selected_task():
            self.post_message(self.TaskSelected(task))
