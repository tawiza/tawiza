"""Logs Screen - Real-time system and agent logs."""

from datetime import datetime

from loguru import logger
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.reactive import reactive
from textual.widgets import Select, Static, Switch

from src.cli.v3.tui.services.log_reader import LogEntry, LogLevel, LogReader, get_log_reader


class LogLevelBadge(Static):
    """A colored badge for log level."""

    DEFAULT_CSS = """
    LogLevelBadge {
        width: 8;
        text-align: center;
        padding: 0 1;
    }

    LogLevelBadge.debug {
        background: $surface-lighten-2;
        color: $text-muted;
    }

    LogLevelBadge.info {
        background: $primary;
        color: $surface;
    }

    LogLevelBadge.warning {
        background: $warning;
        color: $surface;
    }

    LogLevelBadge.error {
        background: $error;
        color: $surface;
    }

    LogLevelBadge.critical {
        background: $error;
        color: $surface;
        text-style: bold blink;
    }
    """


class LogViewer(ScrollableContainer):
    """Scrollable log viewer with auto-scroll."""

    DEFAULT_CSS = """
    LogViewer {
        height: 1fr;
        border: solid $primary;
        background: $surface;
        padding: 0 1;
    }

    LogViewer .log-line {
        height: auto;
        padding: 0;
        margin: 0;
    }

    LogViewer .timestamp {
        color: $text-muted;
        width: 12;
    }

    LogViewer .source {
        color: $accent;
        width: 10;
    }
    """

    auto_scroll = reactive(True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._entries: list[LogEntry] = []

    def add_log(self, entry: LogEntry) -> None:
        """Add a log entry."""
        self._entries.append(entry)

        level_colors = {
            LogLevel.DEBUG: "dim",
            LogLevel.INFO: "cyan",
            LogLevel.WARNING: "yellow",
            LogLevel.ERROR: "red",
            LogLevel.CRITICAL: "bold red",
        }

        color = level_colors.get(entry.level, "white")
        time_str = entry.timestamp.strftime("%H:%M:%S")
        level_str = entry.level.value.upper()[:4]

        line = Static(
            f"[dim]{time_str}[/] [{color}]{level_str:4}[/] "
            f"[cyan]{entry.source:8}[/] {entry.message}",
            classes="log-line",
        )
        self.mount(line)

        if self.auto_scroll:
            self.scroll_end(animate=False)

    def clear_logs(self) -> None:
        """Clear all log entries."""
        self._entries.clear()
        self.remove_children()

    def get_entries(
        self, level: LogLevel | None = None, source: str | None = None
    ) -> list[LogEntry]:
        """Get filtered log entries."""
        entries = self._entries

        if level:
            entries = [e for e in entries if e.level == level]

        if source:
            entries = [e for e in entries if e.source == source]

        return entries


class LogsScreen(Container):
    """Logs content (Container for ContentSwitcher)."""

    BINDINGS = [
        Binding("ctrl+l", "clear_logs", "^L:Clear", show=True, priority=True),
        Binding("ctrl+s", "toggle_scroll", "^S:AutoScroll", show=True),
        Binding("ctrl+f", "filter_level", "^F:Filter", show=True),
        Binding("ctrl+e", "export_logs", "^E:Export", show=True),
        Binding("ctrl+p", "pause_logs", "^P:Pause", show=True),
    ]

    DEFAULT_CSS = """
    LogsScreen {
        layout: vertical;
        width: 100%;
        height: 100%;
    }

    #logs-header {
        height: 3;
        padding: 0 1;
        border-bottom: solid $primary;
        background: $surface-darken-1;
    }

    #level-filter {
        width: 20;
        height: 3;
        margin-left: 2;
    }

    #source-filter {
        width: 20;
        height: 3;
        margin-left: 1;
    }

    #logs-controls {
        dock: right;
        width: auto;
        height: 3;
        padding: 0 1;
    }

    #logs-controls Static {
        margin-right: 1;
    }

    #log-stats {
        height: 2;
        padding: 0 1;
        border-top: solid $primary;
        background: $surface-darken-1;
    }
    """

    is_paused = reactive(False)
    auto_scroll = reactive(True)
    filter_level = reactive("all")
    filter_source = reactive("all")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._log_count = {"debug": 0, "info": 0, "warning": 0, "error": 0, "critical": 0}
        self._refresh_timer = None
        self._log_reader: LogReader | None = None

    def compose(self) -> ComposeResult:
        """Create the logs layout."""
        # Header with filters
        with Horizontal(id="logs-header"):
            yield Static("[bold cyan]LOGS[/] - Real-time system logs")
            yield Select(
                [
                    ("All Levels", "all"),
                    ("Debug", "debug"),
                    ("Info", "info"),
                    ("Warning", "warning"),
                    ("Error", "error"),
                    ("Critical", "critical"),
                ],
                value="all",
                id="level-filter",
            )
            yield Select(
                [
                    ("All Sources", "all"),
                    ("System", "system"),
                    ("System", "system"),
                    ("Debug", "debug"),
                    ("Browser", "browser"),
                    ("Integrated", "integrated"),
                    ("API", "api"),
                    ("TUI", "tui"),
                ],
                value="all",
                id="source-filter",
            )
            with Horizontal(id="logs-controls"):
                yield Static("[bold]Auto-scroll[/]")
                yield Switch(value=True, id="auto-scroll-switch")

        # Log viewer
        yield LogViewer(id="log-viewer")

        # Stats bar
        yield Static("", id="log-stats")

    def on_mount(self) -> None:
        """Initialize on mount."""
        # Load real logs from system
        self.run_worker(self._load_real_logs())

    def on_unmount(self) -> None:
        """Stop timer and log watching on unmount."""
        if self._refresh_timer:
            self._refresh_timer.stop()
        if self._log_reader:
            self.run_worker(self._log_reader.stop_watching())

    async def _load_real_logs(self) -> None:
        """Load real logs from system files."""
        viewer = self.query_one("#log-viewer", LogViewer)

        # Get log reader
        self._log_reader = get_log_reader()

        # Add welcome message
        viewer.add_log(
            LogEntry(
                timestamp=datetime.now(),
                level=LogLevel.INFO,
                source="tui",
                message="Loading system logs...",
            )
        )
        self._log_count["info"] += 1

        try:
            # Read initial logs from all sources
            entries = await self._log_reader.read_initial_logs(max_lines=100)

            if entries:
                viewer.clear_logs()
                self._log_count = {"debug": 0, "info": 0, "warning": 0, "error": 0, "critical": 0}

                for entry in entries:
                    # Apply filters
                    if self.filter_level != "all" and entry.level.value != self.filter_level:
                        continue
                    if self.filter_source != "all" and entry.source != self.filter_source:
                        continue

                    viewer.add_log(entry)
                    self._log_count[entry.level.value] += 1

                self.app.notify(f"Loaded {len(entries)} log entries", timeout=2)
            else:
                viewer.add_log(
                    LogEntry(
                        timestamp=datetime.now(),
                        level=LogLevel.WARNING,
                        source="tui",
                        message="No log files found or empty logs",
                    )
                )
                self._log_count["warning"] += 1

        except Exception as e:
            logger.error(f"Failed to load logs: {e}")
            viewer.add_log(
                LogEntry(
                    timestamp=datetime.now(),
                    level=LogLevel.ERROR,
                    source="tui",
                    message=f"Error loading logs: {e}",
                )
            )
            self._log_count["error"] += 1

        self._update_stats()

        # Register callback for new logs
        self._log_reader.on_new_log(self._on_new_log)

        # Start watching for new logs
        await self._log_reader.start_watching()

    def _on_new_log(self, entry: LogEntry) -> None:
        """Handle new log entry from watcher."""
        if self.is_paused:
            return

        # Apply filters
        if self.filter_level != "all" and entry.level.value != self.filter_level:
            return
        if self.filter_source != "all" and entry.source != self.filter_source:
            return

        try:
            viewer = self.query_one("#log-viewer", LogViewer)
            viewer.add_log(entry)
            self._log_count[entry.level.value] += 1
            self._update_stats()
        except Exception:
            pass  # Widget might not be mounted yet

    def _update_stats(self) -> None:
        """Update the stats bar."""
        stats = self.query_one("#log-stats", Static)
        stats.update(
            f"[dim]DEBUG[/] {self._log_count['debug']} | "
            f"[cyan]INFO[/] {self._log_count['info']} | "
            f"[yellow]WARN[/] {self._log_count['warning']} | "
            f"[red]ERROR[/] {self._log_count['error']} | "
            f"[bold red]CRIT[/] {self._log_count['critical']} | "
            f"Total: {sum(self._log_count.values())}"
        )

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle filter selection changes."""
        if event.select.id == "level-filter":
            self.filter_level = event.value
            self.app.notify(f"Filter: {event.value}", timeout=1)
        elif event.select.id == "source-filter":
            self.filter_source = event.value
            self.app.notify(f"Source: {event.value}", timeout=1)

    def on_switch_changed(self, event: Switch.Changed) -> None:
        """Handle switch changes."""
        if event.switch.id == "auto-scroll-switch":
            self.auto_scroll = event.value
            viewer = self.query_one("#log-viewer", LogViewer)
            viewer.auto_scroll = event.value

    def action_clear_logs(self) -> None:
        """Clear all logs."""
        viewer = self.query_one("#log-viewer", LogViewer)
        viewer.clear_logs()
        self._log_count = {"debug": 0, "info": 0, "warning": 0, "error": 0, "critical": 0}
        self._update_stats()
        self.app.notify("Logs cleared", timeout=1)

    def action_toggle_scroll(self) -> None:
        """Toggle auto-scroll."""
        switch = self.query_one("#auto-scroll-switch", Switch)
        switch.value = not switch.value

    def action_filter_level(self) -> None:
        """Cycle through log levels."""
        levels = ["all", "debug", "info", "warning", "error", "critical"]
        current_idx = levels.index(self.filter_level)
        next_idx = (current_idx + 1) % len(levels)
        self.filter_level = levels[next_idx]

        select = self.query_one("#level-filter", Select)
        select.value = self.filter_level

        self.app.notify(f"Filter: {self.filter_level}", timeout=1)

    def action_export_logs(self) -> None:
        """Export logs to file."""
        viewer = self.query_one("#log-viewer", LogViewer)
        entries = viewer._entries

        if not entries:
            self.app.notify("No logs to export", timeout=2)
            return

        try:
            from src.cli.constants import PROJECT_ROOT

            export_path = PROJECT_ROOT / "logs" / "tui_export.log"
            with open(export_path, "w") as f:
                for entry in entries:
                    time_str = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    f.write(
                        f"{time_str} | {entry.level.value.upper():8} | {entry.source:10} | {entry.message}\n"
                    )

            self.app.notify(f"Exported {len(entries)} logs to {export_path}", timeout=3)
        except Exception as e:
            self.app.notify(f"Export failed: {e}", timeout=3)

    def action_pause_logs(self) -> None:
        """Pause/resume log updates."""
        self.is_paused = not self.is_paused
        status = "PAUSED" if self.is_paused else "RESUMED"
        self.app.notify(f"Logs {status}", timeout=1)
