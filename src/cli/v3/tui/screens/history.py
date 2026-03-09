"""History Screen - View past agent sessions and conversations."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from loguru import logger
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import DataTable, Input, Static

from src.cli.v3.tui.services.session_recorder import get_session_recorder


@dataclass
class SessionRecord:
    """A historical agent session."""
    session_id: str
    agent: str
    task: str
    status: str  # completed, failed, cancelled
    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float = 0.0
    tokens_used: int = 0
    iterations: int = 0
    result_summary: str = ""


class SessionDetail(Static):
    """Detailed view of a session."""

    DEFAULT_CSS = """
    SessionDetail {
        height: auto;
        padding: 1;
        border: solid $primary;
        background: $surface;
        margin: 1;
    }

    SessionDetail .header {
        text-style: bold;
        color: $accent;
    }

    SessionDetail .field {
        margin-left: 2;
    }

    SessionDetail .success {
        color: $success;
    }

    SessionDetail .error {
        color: $error;
    }
    """

    def __init__(self, session: SessionRecord | None = None, **kwargs):
        super().__init__(**kwargs)
        self.session = session

    def render(self) -> str:
        if not self.session:
            return "[dim]Select a session to view details[/]"

        s = self.session
        duration = f"{s.duration_seconds:.1f}s" if s.duration_seconds else "N/A"
        status_color = "success" if s.status == "completed" else "error"

        return f"""[bold cyan]Session Details[/]

[bold]ID:[/] {s.session_id}
[bold]Agent:[/] {s.agent}
[bold]Task:[/] {s.task[:80]}{'...' if len(s.task) > 80 else ''}
[bold]Status:[/] [{status_color}]{s.status.upper()}[/]
[bold]Started:[/] {s.started_at.strftime('%Y-%m-%d %H:%M:%S')}
[bold]Duration:[/] {duration}
[bold]Iterations:[/] {s.iterations}
[bold]Tokens:[/] {s.tokens_used:,}

[bold]Result Summary:[/]
{s.result_summary or '[dim]No summary available[/]'}"""


class HistoryScreen(Container):
    """History content (Container for ContentSwitcher)."""

    BINDINGS = [
        Binding("ctrl+f", "focus_search", "^F:Search", show=True, priority=True),
        Binding("ctrl+r", "refresh", "^R:Refresh", show=True),
        Binding("ctrl+d", "delete_selected", "^D:Delete", show=True),
        Binding("ctrl+e", "export", "^E:Export", show=True),
        Binding("enter", "view_details", "Enter:View", show=True),
    ]

    DEFAULT_CSS = """
    HistoryScreen {
        layout: vertical;
        width: 100%;
        height: 100%;
    }

    #history-header {
        height: 3;
        padding: 0 1;
        border-bottom: solid $primary;
        background: $surface-darken-1;
    }

    #history-content {
        height: 1fr;
    }

    #session-list {
        width: 60%;
        border-right: solid $primary;
    }

    #session-detail {
        width: 40%;
        padding: 1;
    }

    #search-input {
        width: 40;
        margin-left: 2;
    }

    #filter-stats {
        dock: right;
        width: auto;
        padding: 0 2;
    }

    DataTable {
        height: 100%;
    }
    """

    search_query = reactive("")
    selected_session = reactive(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._sessions: list[SessionRecord] = []
        self._filtered_sessions: list[SessionRecord] = []
        self._recorder = get_session_recorder()

    def compose(self) -> ComposeResult:
        """Create the history layout."""
        # Header
        with Horizontal(id="history-header"):
            yield Static("[bold cyan]HISTORY[/] - Past agent sessions")
            yield Input(
                placeholder="Search sessions...",
                id="search-input"
            )
            yield Static("", id="filter-stats")

        # Content: list + detail
        with Horizontal(id="history-content"):
            with Vertical(id="session-list"):
                yield DataTable(id="sessions-table")

            with Vertical(id="session-detail"):
                yield SessionDetail(id="detail-view")

    def on_mount(self) -> None:
        """Initialize on mount."""
        self._setup_table()
        self._load_real_sessions()
        self._refresh_table()

    def _setup_table(self) -> None:
        """Setup the data table columns."""
        table = self.query_one("#sessions-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(
            "ID", "Agent", "Task", "Status", "Date", "Duration"
        )

    def _load_real_sessions(self) -> None:
        """Load sessions from the replay engine storage."""
        self._sessions = []

        try:
            # Get sessions from the recorder
            sessions_data = self._recorder.list_sessions(limit=50)

            for data in sessions_data:
                # Convert from replay engine format to SessionRecord
                started_at = datetime.fromisoformat(data.get("started_at", datetime.now().isoformat()))
                completed_at = None
                if data.get("completed_at"):
                    completed_at = datetime.fromisoformat(data["completed_at"])

                duration = 0.0
                if completed_at:
                    duration = (completed_at - started_at).total_seconds()

                self._sessions.append(SessionRecord(
                    session_id=data.get("session_id", "unknown"),
                    agent=data.get("agent_name", "general"),
                    task=data.get("task_description", "No description"),
                    status=data.get("final_status", "unknown"),
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_seconds=duration,
                    tokens_used=data.get("tokens_used", 0),
                    iterations=len(data.get("actions", [])),
                    result_summary=self._extract_summary(data)
                ))

            if not self._sessions:
                self.app.notify("No saved sessions found", timeout=2)

        except Exception as e:
            logger.error(f"Failed to load sessions: {e}")
            self.app.notify(f"Error loading sessions: {e}", timeout=3)

        self._filtered_sessions = self._sessions.copy()

    def _extract_summary(self, data: dict) -> str:
        """Extract a summary from session data."""
        actions = data.get("actions", [])
        if not actions:
            return "No actions recorded"

        # Get last few actions for summary
        last_actions = actions[-3:]
        summaries = []
        for action in last_actions:
            content = action.get("content", "")
            if content:
                summaries.append(content[:100])

        return " | ".join(summaries) if summaries else "Session completed"

    def _refresh_table(self) -> None:
        """Refresh the sessions table."""
        table = self.query_one("#sessions-table", DataTable)
        table.clear()

        for session in self._filtered_sessions:
            status_style = {
                "completed": "[green]",
                "failed": "[red]",
                "cancelled": "[yellow]",
            }.get(session.status, "")

            duration = f"{session.duration_seconds / 60:.1f}m" if session.duration_seconds > 60 else f"{session.duration_seconds:.0f}s"

            table.add_row(
                session.session_id,
                session.agent,
                session.task[:30] + "..." if len(session.task) > 30 else session.task,
                f"{status_style}{session.status}[/]",
                session.started_at.strftime("%m/%d %H:%M"),
                duration,
                key=session.session_id
            )

        # Update stats
        stats = self.query_one("#filter-stats", Static)
        completed = sum(1 for s in self._filtered_sessions if s.status == "completed")
        failed = sum(1 for s in self._filtered_sessions if s.status == "failed")
        stats.update(f"[green]{completed}[/] ok | [red]{failed}[/] err | {len(self._filtered_sessions)} total")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection."""
        session_id = event.row_key.value
        session = next((s for s in self._sessions if s.session_id == session_id), None)

        if session:
            self.selected_session = session
            detail = self.query_one("#detail-view", SessionDetail)
            detail.session = session
            detail.refresh()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        if event.input.id == "search-input":
            self.search_query = event.value.lower()
            self._filter_sessions()

    def _filter_sessions(self) -> None:
        """Filter sessions based on search query."""
        if not self.search_query:
            self._filtered_sessions = self._sessions.copy()
        else:
            self._filtered_sessions = [
                s for s in self._sessions
                if self.search_query in s.session_id.lower()
                or self.search_query in s.agent.lower()
                or self.search_query in s.task.lower()
                or self.search_query in s.status.lower()
            ]
        self._refresh_table()

    def action_focus_search(self) -> None:
        """Focus the search input."""
        self.query_one("#search-input", Input).focus()

    def action_refresh(self) -> None:
        """Refresh session list."""
        self._load_real_sessions()
        self._filter_sessions()
        self.app.notify("Sessions refreshed", timeout=1)

    def action_delete_selected(self) -> None:
        """Delete selected session."""
        if self.selected_session:
            # Delete from recorder storage
            try:
                self._recorder.delete_session(self.selected_session.session_id)
            except Exception as e:
                logger.warning(f"Could not delete from storage: {e}")

            self._sessions = [s for s in self._sessions if s.session_id != self.selected_session.session_id]
            self._filter_sessions()
            self.selected_session = None
            detail = self.query_one("#detail-view", SessionDetail)
            detail.session = None
            detail.refresh()
            self.app.notify("Session deleted", timeout=1)

    def action_export(self) -> None:
        """Export sessions to JSON file."""
        if not self._filtered_sessions:
            self.app.notify("No sessions to export", timeout=2)
            return

        try:
            from src.cli.constants import PROJECT_ROOT
            export_path = PROJECT_ROOT / "logs" / "sessions_export.json"

            export_data = []
            for s in self._filtered_sessions:
                export_data.append({
                    "session_id": s.session_id,
                    "agent": s.agent,
                    "task": s.task,
                    "status": s.status,
                    "started_at": s.started_at.isoformat(),
                    "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                    "duration_seconds": s.duration_seconds,
                    "tokens_used": s.tokens_used,
                    "iterations": s.iterations,
                    "result_summary": s.result_summary,
                })

            with open(export_path, "w") as f:
                json.dump(export_data, f, indent=2)

            self.app.notify(f"Exported {len(export_data)} sessions to {export_path}", timeout=3)

        except Exception as e:
            self.app.notify(f"Export failed: {e}", timeout=3)

    def action_view_details(self) -> None:
        """View detailed session info."""
        if self.selected_session:
            self.app.notify(f"Viewing session {self.selected_session.session_id}", timeout=1)
