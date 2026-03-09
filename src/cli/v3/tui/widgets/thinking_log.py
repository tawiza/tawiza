"""Thinking Log widget for displaying agent thoughts and actions."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import RichLog, Static


class LogEntryType(Enum):
    """Type of log entry."""
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    INFO = "info"
    USER_MESSAGE = "user_message"


@dataclass
class LogEntry:
    """A single log entry."""
    timestamp: datetime
    entry_type: LogEntryType
    content: str
    details: str | None = None


class ThinkingLog(Vertical):
    """Widget for displaying agent thinking and actions in real-time."""

    DEFAULT_CSS = """
    ThinkingLog {
        height: 100%;
        border: solid $secondary;
        background: $surface;
    }

    ThinkingLog .title {
        dock: top;
        height: 1;
        background: $surface-darken-1;
        padding: 0 1;
        text-style: bold;
        color: $accent;
    }

    ThinkingLog RichLog {
        height: 1fr;
        padding: 1;
        scrollbar-gutter: stable;
    }

    ThinkingLog .auto-scroll-indicator {
        dock: bottom;
        height: 1;
        text-align: right;
        padding: 0 1;
        color: $text-muted;
    }
    """

    auto_scroll = reactive(True)

    def __init__(self, title: str = "THINKING / LOGS", **kwargs):
        super().__init__(**kwargs)
        self._title = title
        self._entries: list[LogEntry] = []

    def compose(self):
        """Compose the thinking log."""
        yield Static(f"[bold cyan]{self._title}[/]", classes="title")
        yield RichLog(highlight=True, markup=True, id="log-content")
        yield Static(
            f"[dim][auto-scroll {'✓' if self.auto_scroll else '✗'}][/]",
            classes="auto-scroll-indicator",
            id="auto-scroll-indicator"
        )

    def add_entry(self, entry_type: LogEntryType, content: str, details: str | None = None) -> None:
        """Add a new log entry."""
        entry = LogEntry(
            timestamp=datetime.now(),
            entry_type=entry_type,
            content=content,
            details=details
        )
        self._entries.append(entry)
        self._render_entry(entry)

    def _render_entry(self, entry: LogEntry) -> None:
        """Render a single entry to the log."""
        log = self.query_one("#log-content", RichLog)

        # Format based on type
        time_str = entry.timestamp.strftime("%H:%M:%S")

        if entry.entry_type == LogEntryType.THINKING:
            icon = "🤔"
            color = "yellow"
        elif entry.entry_type == LogEntryType.TOOL_CALL:
            icon = "🔧"
            color = "cyan"
        elif entry.entry_type == LogEntryType.TOOL_RESULT:
            icon = "✅"
            color = "green"
        elif entry.entry_type == LogEntryType.ERROR:
            icon = "❌"
            color = "red"
        elif entry.entry_type == LogEntryType.USER_MESSAGE:
            icon = "👤"
            color = "magenta"
        else:
            icon = "ℹ️"
            color = "blue"

        # Write to log
        log.write(f"[dim]{time_str}[/] {icon} [{color}]{entry.content}[/]")

        if entry.details:
            for line in entry.details.split("\n"):
                log.write(f"   [dim]{line}[/]")

        # Auto-scroll if enabled
        if self.auto_scroll:
            log.scroll_end(animate=False)

    def add_thinking(self, content: str) -> None:
        """Add a thinking entry."""
        self.add_entry(LogEntryType.THINKING, content)

    def add_tool_call(self, tool_name: str, params: str | None = None) -> None:
        """Add a tool call entry."""
        self.add_entry(LogEntryType.TOOL_CALL, f"Calling: {tool_name}", params)

    def add_tool_result(self, result: str) -> None:
        """Add a tool result entry."""
        self.add_entry(LogEntryType.TOOL_RESULT, result)

    def add_error(self, error: str) -> None:
        """Add an error entry."""
        self.add_entry(LogEntryType.ERROR, error)

    def add_user_message(self, message: str) -> None:
        """Add a user message/correction."""
        self.add_entry(LogEntryType.USER_MESSAGE, f"User: {message}")

    def toggle_auto_scroll(self) -> None:
        """Toggle auto-scroll."""
        self.auto_scroll = not self.auto_scroll
        indicator = self.query_one("#auto-scroll-indicator", Static)
        indicator.update(f"[dim][auto-scroll {'✓' if self.auto_scroll else '✗'}][/]")

    def clear(self) -> None:
        """Clear all entries."""
        self._entries.clear()
        log = self.query_one("#log-content", RichLog)
        log.clear()

    def get_entries(self) -> list[LogEntry]:
        """Get all log entries."""
        return self._entries.copy()
