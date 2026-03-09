"""
UI Components - Interactive CLI elements

Provides reusable UI components:
- Panel: Boxed content with borders
- Progress: Progress bars with statistics
- Spinner: Loading animations
"""


from rich.console import Console
from rich.panel import Panel as RichPanel
from rich.progress import (
    BarColumn,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.progress import (
    Progress as RichProgress,
)

from .theme import get_theme


class Panel:
    """
    Panel component for boxed content

    Examples:
        >>> panel = Panel(theme="cyberpunk")
        >>> panel.show("Important message", title="Notice")
    """

    def __init__(self, theme: str = "cyberpunk"):
        self.theme = get_theme(theme)
        self.console = Console(theme=self.theme.to_rich_theme())

    def show(
        self,
        content: str,
        *,
        title: str | None = None,
        subtitle: str | None = None,
        border_style: str | None = None,
        expand: bool = True,
    ) -> None:
        """Display content in a panel"""
        panel = RichPanel(
            content,
            title=title,
            subtitle=subtitle,
            border_style=border_style or self.theme.primary,
            expand=expand,
        )
        self.console.print(panel)


class Progress:
    """
    Progress bar component with statistics

    Examples:
        >>> progress = Progress(theme="ocean")
        >>> task = progress.add_task("Processing", total=100)
        >>> for i in range(100):
        ...     progress.update(task, advance=1)
    """

    def __init__(
        self,
        theme: str = "cyberpunk",
        show_time_remaining: bool = True,
        show_time_elapsed: bool = False,
    ):
        self.theme = get_theme(theme)
        self.console = Console(theme=self.theme.to_rich_theme())

        # Build progress columns
        columns = [
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(complete_style=self.theme.success),
            TaskProgressColumn(),
        ]

        if show_time_remaining:
            columns.append(TimeRemainingColumn())

        if show_time_elapsed:
            columns.append(TimeElapsedColumn())

        self.progress = RichProgress(*columns, console=self.console)

    def __enter__(self):
        self.progress.__enter__()
        return self

    def __exit__(self, *args):
        return self.progress.__exit__(*args)

    def add_task(
        self,
        description: str,
        total: float | None = None,
        **kwargs,
    ):
        """Add a progress task"""
        return self.progress.add_task(description, total=total, **kwargs)

    def update(self, task_id, **kwargs):
        """Update a progress task"""
        return self.progress.update(task_id, **kwargs)


class Spinner:
    """
    Spinner component for loading states

    Examples:
        >>> with Spinner("Loading..."):
        ...     time.sleep(2)
    """

    def __init__(
        self,
        text: str = "Loading...",
        theme: str = "cyberpunk",
        spinner: str = "dots",
    ):
        self.text = text
        self.theme = get_theme(theme)
        self.console = Console(theme=self.theme.to_rich_theme())
        self.spinner = spinner

    def __enter__(self):
        self.console.status(self.text, spinner=self.spinner).__enter__()
        return self

    def __exit__(self, *args):
        self.console.status(self.text, spinner=self.spinner).__exit__(*args)
