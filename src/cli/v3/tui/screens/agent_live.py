"""Agent Live Screen - Real-time agent monitoring and control."""

from typing import Any

from loguru import logger
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.timer import Timer
from textual.widgets import Input, Static

from src.cli.v3.tui.services.websocket_client import TUIWebSocketClient, get_ws_client
from src.cli.v3.tui.widgets.action_timeline import ActionTimeline, StepStatus
from src.cli.v3.tui.widgets.task_list import TaskInfo
from src.cli.v3.tui.widgets.thinking_log import LogEntryType, ThinkingLog


class AgentHeader(Static):
    """Header showing current agent info."""

    DEFAULT_CSS = """
    AgentHeader {
        height: 3;
        padding: 0 1;
        border-bottom: solid $primary;
        background: $surface-darken-1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.agent_name = "No Agent"
        self.task_description = "No task"
        self.status = "Idle"
        self.model = "default"

    def render(self) -> str:
        """Render agent header."""
        status_color = {
            "Running": "cyan",
            "Paused": "yellow",
            "Completed": "green",
            "Failed": "red",
            "Idle": "dim",
        }.get(self.status, "dim")

        status_icon = {
            "Running": "▶",
            "Paused": "⏸",
            "Completed": "✓",
            "Failed": "✗",
            "Idle": "○",
        }.get(self.status, "○")

        return (
            f"[bold]AGENT:[/] {self.agent_name}    "
            f"[{status_color}]{status_icon} {self.status}[/]\n"
            f"[bold]Task:[/] {self.task_description[:50]}    "
            f"[bold]Model:[/] {self.model}"
        )

    def set_agent(self, name: str, task: str, status: str, model: str = "default") -> None:
        """Update agent info."""
        self.agent_name = name
        self.task_description = task
        self.status = status
        self.model = model
        self.refresh()


class CorrectionInput(Vertical):
    """Input for sending corrections to the agent."""

    DEFAULT_CSS = """
    CorrectionInput {
        dock: bottom;
        height: 5;
        border-top: solid $accent;
        background: $surface-darken-1;
        padding: 0 1;
    }

    CorrectionInput .label {
        height: 1;
        color: $accent;
    }

    CorrectionInput Input {
        height: 3;
        background: $surface;
        border: solid $primary;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def compose(self):
        yield Static("[bold]💬 CORRECTION / MESSAGE TO AGENT[/]", classes="label")
        yield Input(
            placeholder="Send a correction or guidance to the agent...", id="correction-field"
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle correction submission."""
        message = event.value.strip()
        if message:
            event.input.value = ""
            # Find parent AgentLiveScreen container and call handle_correction
            try:
                parent = self.ancestors_with_self[AgentLiveScreen]
                parent.handle_correction(message)
            except Exception:
                # Fallback: search by query
                pass


class AgentLiveScreen(Container):
    """Agent monitoring content (Container for ContentSwitcher)."""

    BINDINGS = [
        Binding("ctrl+p", "toggle_pause", "^P:Pause", show=True),
        Binding("ctrl+s", "stop_agent", "^S:Stop", show=True),
        Binding("ctrl+f", "fork_session", "^F:Fork", show=True),
        Binding("ctrl+m", "change_model", "^M:Model", show=True),
        Binding("ctrl+b", "open_browser", "^B:Browser", show=True),
        Binding("left", "timeline_back", show=False),
        Binding("right", "timeline_forward", show=False),
        Binding("ctrl+t", "focus_input", "^T:Type", show=True, priority=True),
    ]

    DEFAULT_CSS = """
    AgentLiveScreen {
        layout: vertical;
        width: 100%;
        height: 100%;
    }

    #content-row {
        height: 1fr;
        layout: horizontal;
        padding: 0 1;
    }

    #thinking-panel {
        width: 65%;
        margin-right: 1;
    }

    #timeline-panel {
        width: 35%;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._current_task: TaskInfo | None = None
        self._current_task_id: str | None = None
        self._is_paused = False
        self._refresh_timer: Timer | None = None
        self._ws_client: TUIWebSocketClient | None = None
        self._ws_connected = False

    def compose(self) -> ComposeResult:
        """Create the agent live layout."""
        yield AgentHeader(id="agent-header")

        with Horizontal(id="content-row"):
            yield ThinkingLog(id="thinking-panel")
            yield ActionTimeline(id="timeline-panel")

        yield CorrectionInput(id="correction-input")

    def on_mount(self) -> None:
        """Initialize on mount."""
        self._refresh_timer = self.set_interval(1.0, self._update_display)
        # Connect to WebSocket for real-time updates
        self.run_worker(self._connect_websocket())

    def on_unmount(self) -> None:
        """Cleanup on unmount."""
        if self._refresh_timer:
            self._refresh_timer.stop()

    async def _connect_websocket(self) -> None:
        """Connect to WebSocket and register handlers."""
        try:
            self._ws_client = get_ws_client()

            # Register handlers for agent events
            self._ws_client.on_message("agent.thinking", self._on_agent_thinking)
            self._ws_client.on_message("agent.tool_call", self._on_agent_tool_call)
            self._ws_client.on_message("agent.tool_result", self._on_agent_tool_result)
            self._ws_client.on_message("agent.error", self._on_agent_error)
            self._ws_client.on_message("agent.step", self._on_agent_step)
            self._ws_client.on_message("agent.status", self._on_agent_status)
            self._ws_client.on_message("task.update", self._on_task_update)

            if await self._ws_client.connect():
                self._ws_connected = True
                self.app.notify("Connected to agent server", timeout=2)
                self._show_waiting_state()
            else:
                self._ws_connected = False
                self._show_offline_state()

        except Exception as e:
            logger.warning(f"WebSocket not available: {e}")
            self._ws_connected = False
            self._show_offline_state()

    def _show_waiting_state(self) -> None:
        """Show waiting for agent state."""
        header = self.query_one("#agent-header", AgentHeader)
        header.set_agent(
            name="No Active Agent", task="Waiting for task...", status="Idle", model="default"
        )

        thinking = self.query_one("#thinking-panel", ThinkingLog)
        thinking.add_entry(LogEntryType.INFO, "Connected to server. Waiting for agent activity...")

    def _show_offline_state(self) -> None:
        """Show offline state with instructions."""
        header = self.query_one("#agent-header", AgentHeader)
        header.set_agent(
            name="Offline Mode", task="Agent server not connected", status="Idle", model="N/A"
        )

        thinking = self.query_one("#thinking-panel", ThinkingLog)
        thinking.add_entry(
            LogEntryType.INFO,
            "Agent server not connected. Start the server or use the Chat screen for direct Ollama access.",
        )
        thinking.add_entry(
            LogEntryType.INFO, "To start the agent server: python -m src.interfaces.api.main"
        )

    async def _on_agent_thinking(self, data: dict[str, Any]) -> None:
        """Handle agent thinking event."""
        thinking = self.query_one("#thinking-panel", ThinkingLog)
        content = data.get("content", "")
        thinking.add_thinking(content)

    async def _on_agent_tool_call(self, data: dict[str, Any]) -> None:
        """Handle agent tool call event."""
        thinking = self.query_one("#thinking-panel", ThinkingLog)
        tool_name = data.get("tool", "unknown")
        params = data.get("params", "")
        thinking.add_tool_call(tool_name, str(params))

    async def _on_agent_tool_result(self, data: dict[str, Any]) -> None:
        """Handle agent tool result event."""
        thinking = self.query_one("#thinking-panel", ThinkingLog)
        result = data.get("result", "")
        success = data.get("success", True)
        thinking.add_tool_result(result, success)

    async def _on_agent_error(self, data: dict[str, Any]) -> None:
        """Handle agent error event."""
        thinking = self.query_one("#thinking-panel", ThinkingLog)
        error = data.get("error", "Unknown error")
        thinking.add_entry(LogEntryType.ERROR, error)

    async def _on_agent_step(self, data: dict[str, Any]) -> None:
        """Handle agent step update."""
        timeline = self.query_one("#timeline-panel", ActionTimeline)
        step_id = data.get("step_id", "")
        step_name = data.get("name", "Step")
        status_str = data.get("status", "pending")

        status_map = {
            "completed": StepStatus.COMPLETED,
            "current": StepStatus.CURRENT,
            "pending": StepStatus.PENDING,
            "failed": StepStatus.FAILED,
        }
        status = status_map.get(status_str, StepStatus.PENDING)

        timeline.update_step(step_id, step_name, status)

    async def _on_agent_status(self, data: dict[str, Any]) -> None:
        """Handle agent status change."""
        header = self.query_one("#agent-header", AgentHeader)
        header.set_agent(
            name=data.get("agent_name", "Agent"),
            task=data.get("task", ""),
            status=data.get("status", "Running"),
            model=data.get("model", "default"),
        )
        self._current_task_id = data.get("task_id")

    async def _on_task_update(self, data: dict[str, Any]) -> None:
        """Handle task update event."""
        task_id = data.get("task_id", "")
        status = data.get("status", "")

        if status == "completed":
            thinking = self.query_one("#thinking-panel", ThinkingLog)
            thinking.add_entry(LogEntryType.INFO, f"Task {task_id} completed")
            header = self.query_one("#agent-header", AgentHeader)
            header.status = "Completed"
            header.refresh()
        elif status == "failed":
            thinking = self.query_one("#thinking-panel", ThinkingLog)
            thinking.add_entry(LogEntryType.ERROR, f"Task {task_id} failed")
            header = self.query_one("#agent-header", AgentHeader)
            header.status = "Failed"
            header.refresh()

    async def _update_display(self) -> None:
        """Periodic display update."""
        # In real implementation, this would poll the agent status
        pass

    def set_task(self, task: TaskInfo) -> None:
        """Set the current task to monitor."""
        self._current_task = task
        header = self.query_one("#agent-header", AgentHeader)
        header.set_agent(
            name=task.agent,
            task=task.description,
            status=task.status.value.capitalize(),
            model=task.model,
        )

    def handle_correction(self, message: str) -> None:
        """Handle a correction message from the user."""
        thinking = self.query_one("#thinking-panel", ThinkingLog)
        thinking.add_user_message(message)

        if self._ws_connected and self._ws_client and self._current_task_id:
            # Send correction via WebSocket
            self.run_worker(self._send_correction(message))
        else:
            self.app.notify("No active task to correct", timeout=2)

    async def _send_correction(self, message: str) -> None:
        """Send correction via WebSocket."""
        if self._ws_client and self._current_task_id:
            success = await self._ws_client.send_correction(self._current_task_id, message)
            if success:
                self.app.notify("Correction sent", timeout=2)
            else:
                self.app.notify("Failed to send correction", timeout=2)

    def action_toggle_pause(self) -> None:
        """Toggle pause/resume."""
        self._is_paused = not self._is_paused
        header = self.query_one("#agent-header", AgentHeader)

        if self._is_paused:
            header.status = "Paused"
            self.app.notify("Agent paused", timeout=2)
            if self._ws_client and self._current_task_id:
                self.run_worker(self._ws_client.pause_task(self._current_task_id))
        else:
            header.status = "Running"
            self.app.notify("Agent resumed", timeout=2)
            if self._ws_client and self._current_task_id:
                self.run_worker(self._ws_client.resume_task(self._current_task_id))

        header.refresh()

        thinking = self.query_one("#thinking-panel", ThinkingLog)
        thinking.add_entry(
            LogEntryType.INFO, "Paused by user" if self._is_paused else "Resumed by user"
        )

    def action_stop_agent(self) -> None:
        """Stop the current agent."""
        header = self.query_one("#agent-header", AgentHeader)
        header.status = "Stopped"
        header.refresh()

        thinking = self.query_one("#thinking-panel", ThinkingLog)
        thinking.add_entry(LogEntryType.ERROR, "Agent stopped by user")

        if self._ws_client and self._current_task_id:
            self.run_worker(self._ws_client.cancel_task(self._current_task_id))

        self.app.notify("Agent stopped", timeout=2)

    def action_fork_session(self) -> None:
        """Fork the current session."""
        self.app.notify("Forking session... (not implemented)", timeout=2)
        thinking = self.query_one("#thinking-panel", ThinkingLog)
        thinking.add_entry(LogEntryType.INFO, "Session forked")
        # TODO: Implement session forking

    def action_change_model(self) -> None:
        """Change the model mid-task."""
        self.app.notify("Model selection... (not implemented)", timeout=2)
        # TODO: Show model selection dialog

    def action_open_browser(self) -> None:
        """Open browser view."""
        self.app.switch_to_screen("browser")

    def action_timeline_back(self) -> None:
        """Navigate timeline backward."""
        self.query_one("#timeline-panel", ActionTimeline)
        # TODO: Navigate to previous step

    def action_timeline_forward(self) -> None:
        """Navigate timeline forward."""
        self.query_one("#timeline-panel", ActionTimeline)
        # TODO: Navigate to next step

    def action_go_back(self) -> None:
        """Go back to dashboard."""
        self.app.switch_to_screen("dashboard")

    def action_focus_input(self) -> None:
        """Focus the correction input field."""
        try:
            input_widget = self.query_one("#correction-field", Input)
            input_widget.focus()
        except Exception:
            pass
