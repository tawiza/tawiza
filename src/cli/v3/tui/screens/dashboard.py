"""Dashboard Screen - Main overview with metrics, agents, and activity."""

import os
from datetime import datetime

from loguru import logger
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.timer import Timer
from textual.widgets import Input, Static

from src.cli.v3.tui.services.adaptive_refresh import RefreshPriority, get_refresh_manager
from src.cli.v3.tui.services.gpu_metrics import get_gpu_utilization
from src.cli.v3.tui.widgets.metric_gauge import MetricGauge
from src.cli.v3.tui.widgets.service_status import ServiceStatusWidget
from src.cli.v3.tui.widgets.task_list import TaskInfo, TaskList, TaskStatus


class ActivityLog(Static):
    """Simple activity log widget."""

    DEFAULT_CSS = """
    ActivityLog {
        height: 100%;
        border: solid #888888;
        background: $surface;
        padding: 1;
    }

    ActivityLog .title {
        text-style: bold;
        color: $accent;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._entries: list[str] = []

    def render(self) -> str:
        """Render the activity log."""
        title = "[bold cyan]RECENT ACTIVITY[/]\n"
        if not self._entries:
            return title + "[dim]No recent activity[/]"

        entries_text = "\n".join(self._entries[-8:])  # Last 8 entries
        return title + entries_text

    def add_entry(self, message: str) -> None:
        """Add a log entry."""
        timestamp = datetime.now().strftime("%H:%M")
        self._entries.append(f"[dim]{timestamp}[/] {message}")
        if len(self._entries) > 50:
            self._entries.pop(0)
        self.refresh()

    def clear(self) -> None:
        """Clear all entries."""
        self._entries.clear()
        self.refresh()


class DashboardScreen(Container):
    """Main dashboard content (Container for ContentSwitcher compatibility).

    Note: Changed from Screen to Container in TUI v6 to work properly
    with ContentSwitcher layout. All functionality is preserved.
    """

    BINDINGS = [
        Binding("ctrl+a", "agent_details", "^A:Agent", show=True),
        Binding("ctrl+t", "start_task", "^T:Type", show=True, priority=True),
        Binding("ctrl+p", "pause_all", "^P:Pause", show=True),
    ]

    DEFAULT_CSS = """
    DashboardScreen {
        layout: vertical;
        width: 100%;
        height: 100%;
    }

    #metrics-row {
        height: 7;
        layout: horizontal;
        padding: 0 1;
    }

    #metrics-row MetricGauge {
        width: 1fr;
        margin: 0 1 0 0;
    }

    #content-row {
        height: 1fr;
        layout: horizontal;
        padding: 0 1;
    }

    #left-panel {
        width: 25%;
        layout: vertical;
        margin-right: 1;
    }

    #services-panel {
        height: 50%;
        border: solid $primary;
        background: $surface;
        padding: 1;
        margin-bottom: 1;
    }

    #services-title {
        text-style: bold;
        color: $accent;
    }

    #center-panel {
        width: 50%;
        layout: vertical;
    }

    #agents-panel {
        height: 60%;
        margin-bottom: 1;
    }

    #activity-panel {
        height: 40%;
    }

    #right-panel {
        width: 25%;
        margin-left: 1;
    }

    #command-bar {
        dock: bottom;
        height: 4;
        border-top: solid $primary;
        background: $surface-darken-1;
        padding: 0 1;
    }

    #command-bar Static {
        height: 1;
        color: $accent;
    }

    #command-bar Input {
        height: 3;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._refresh_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        """Create the dashboard layout."""
        # Top row: Metrics
        with Horizontal(id="metrics-row"):
            yield MetricGauge("GPU", id="gpu-gauge")
            yield MetricGauge("CPU", id="cpu-gauge")
            yield MetricGauge("RAM", id="ram-gauge")
            yield MetricGauge("DISK", unit="%", id="disk-gauge")

        # Content row
        with Horizontal(id="content-row"):
            # Left panel: Services
            with Vertical(id="left-panel"), Container(id="services-panel"):
                yield Static("[bold cyan]SERVICES[/]", id="services-title")
                yield ServiceStatusWidget(id="services-widget")

            # Center panel: Agents + Activity
            with Vertical(id="center-panel"):
                yield TaskList(title="ACTIVE AGENTS", id="agents-panel")
                yield ActivityLog(id="activity-panel")

        # Bottom: Command input
        with Vertical(id="command-bar"):
            yield Static("[bold]COMMAND INPUT[/] - Ctrl+T to type, Enter to send")
            yield Input(placeholder="Enter a command or task...", id="cmd-input")

    def on_mount(self) -> None:
        """Start updates on mount - adaptive polling + WebSocket events."""
        # Register with adaptive refresh manager
        refresh_manager = get_refresh_manager()
        if refresh_manager._app:
            refresh_manager.register_timer(
                name="dashboard_metrics",
                callback=self._refresh_data,
                priority=RefreshPriority.HIGH,
                active_interval=2.0,   # 2s when dashboard is active
                idle_interval=5.0,     # 5s when idle
                background_interval=30.0,  # 30s when not visible
            )
            refresh_manager.start_timer("dashboard_metrics")
            logger.debug("Dashboard using adaptive refresh")
        else:
            # Fallback to fixed timer if manager not ready
            self._refresh_timer = self.set_interval(2.0, self._refresh_data)

        # Initial data load
        self.run_worker(self._refresh_data())
        self._init_demo_data()

        # Connect to WebSocket for real-time events
        self.run_worker(self._connect_websocket())

    def on_unmount(self) -> None:
        """Stop timer on unmount."""
        if self._refresh_timer:
            self._refresh_timer.stop()
        # Stop adaptive timer
        refresh_manager = get_refresh_manager()
        refresh_manager.stop_timer("dashboard_metrics")

    def _init_demo_data(self) -> None:
        """Initialize with demo data."""
        # Demo services
        services = self.query_one("#services-widget", ServiceStatusWidget)
        services.update_services({
            "Ollama": "checking",
            "Tawiza API": "checking",
            "LLaMA-Factory": "checking",
            "Browser": "ready",
            "Label Studio": "checking",
        })

        # Demo activity
        activity = self.query_one("#activity-panel", ActivityLog)
        activity.add_entry("Dashboard initialized")
        activity.add_entry("Checking services...")

    async def _refresh_data(self) -> None:
        """Refresh all dashboard data."""
        await self._update_metrics()
        await self._update_services()

    async def _update_metrics(self) -> None:
        """Update system metrics."""
        try:
            import psutil

            # CPU
            cpu_gauge = self.query_one("#cpu-gauge", MetricGauge)
            cpu_gauge.update_value(psutil.cpu_percent(interval=0))

            # RAM
            ram_gauge = self.query_one("#ram-gauge", MetricGauge)
            ram_gauge.update_value(psutil.virtual_memory().percent)

            # Disk
            disk_gauge = self.query_one("#disk-gauge", MetricGauge)
            disk_gauge.update_value(psutil.disk_usage("/").percent)

            # GPU (try ROCm) - async call to avoid blocking event loop
            gpu_gauge = self.query_one("#gpu-gauge", MetricGauge)
            try:
                gpu_util = await get_gpu_utilization()
                gpu_gauge.update_value(gpu_util)
            except Exception:
                gpu_gauge.update_value(0)

        except Exception:
            pass

    async def _update_services(self) -> None:
        """Update services status."""
        import socket

        import httpx

        services = {}

        # Check Ollama (VM 300)
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    model_count = len(data.get("models", []))
                    services["Ollama"] = f"online ({model_count} models)"
                else:
                    services["Ollama"] = "error"
        except Exception:
            services["Ollama"] = "offline"

        # Check Tawiza API
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get("http://localhost:8002/health")
                services["Tawiza API"] = "online" if response.status_code == 200 else "error"
        except Exception:
            services["Tawiza API"] = "offline"

        # Check Redis (with password from env if needed)
        try:
            import os

            import redis
            redis_password = os.environ.get("REDIS_PASSWORD", "")
            r = redis.Redis(host="localhost", port=6379, password=redis_password, socket_timeout=1)
            r.ping()
            services["Redis"] = "online"
        except redis.exceptions.AuthenticationError:
            services["Redis"] = "auth failed"
        except Exception:
            services["Redis"] = "offline"

        # Check PostgreSQL
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("localhost", 5432))
            services["PostgreSQL"] = "online" if result == 0 else "offline"
            sock.close()
        except Exception:
            services["PostgreSQL"] = "offline"

        # Check Docker services with port check
        port_services = {
            "LLaMA-Factory": 7860,
            "Label Studio": 8085,
        }

        for name, port in port_services.items():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(("localhost", port))
                services[name] = "online" if result == 0 else "offline"
                sock.close()
            except Exception:
                services[name] = "offline"

        # Update widget
        widget = self.query_one("#services-widget", ServiceStatusWidget)
        widget.update_services(services)

        # Update activity log
        activity = self.query_one("#activity-panel", ActivityLog)
        online_count = sum(1 for s in services.values() if "online" in s)
        activity.add_entry(f"Services: {online_count}/{len(services)} online")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle command submission - sends to WebSocket or Ollama."""
        if event.input.id == "cmd-input":
            command = event.value.strip()
            if command:
                activity = self.query_one("#activity-panel", ActivityLog)
                activity.add_entry(f"Command: {command[:40]}...")
                event.input.value = ""
                self.app.notify(f"Processing: {command[:50]}...", timeout=3)

                # Send command via WebSocket or create task
                self.run_worker(self._send_command(command))

    async def _send_command(self, command: str) -> None:
        """Send command to create an agent task."""
        from src.cli.v3.tui.services.websocket_client import get_ws_client

        try:
            client = get_ws_client()

            # Try to connect if not connected
            if not client.is_connected:
                connected = await client.connect()
                if not connected:
                    # Fallback: use direct Ollama
                    self.app.notify("Using direct Ollama mode", timeout=2)
                    await self._execute_direct_ollama(command)
                    return

            # Create task via WebSocket
            success = await client.create_task(
                agent="general",
                prompt=command,
                context={}
            )

            if success:
                activity = self.query_one("#activity-panel", ActivityLog)
                activity.add_entry("Task sent to agent server")
                # Switch to agent live to see progress
                self.app.notify("Task created. Press Ctrl+A for agent details.", timeout=3)
            else:
                self.app.notify("Failed to create task", timeout=2)

        except Exception as e:
            self.app.notify(f"Error: {str(e)[:50]}", timeout=3)
            # Fallback to direct Ollama
            await self._execute_direct_ollama(command)

    async def _execute_direct_ollama(self, command: str) -> None:
        """Execute command directly via Ollama."""
        import httpx

        activity = self.query_one("#activity-panel", ActivityLog)

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')}/api/chat",
                    json={
                        "model": "qwen3.5:27b",
                        "messages": [
                            {"role": "system", "content": "You are a helpful assistant. Be concise."},
                            {"role": "user", "content": command}
                        ],
                        "stream": False
                    }
                )
                result = response.json()
                answer = result.get("message", {}).get("content", "No response")

                # Show first 100 chars in activity log
                activity.add_entry(f"AI: {answer[:100]}...")
                self.app.notify("Response received. See Chat for full response.", timeout=3)

        except Exception as e:
            activity.add_entry(f"Error: {str(e)[:50]}")
            self.app.notify(f"Ollama error: {str(e)[:50]}", timeout=3)

    def action_agent_details(self) -> None:
        """Switch to agent details view."""
        self.app.switch_to_screen("agent_live")

    def action_start_task(self) -> None:
        """Focus command input to start a new task."""
        cmd_input = self.query_one("#cmd-input", Input)
        cmd_input.focus()

    def action_pause_all(self) -> None:
        """Pause all running agents."""
        self.app.notify("Pausing all agents...", timeout=2)
        # TODO: Implement via AgentController

    async def _connect_websocket(self) -> None:
        """Connect to WebSocket for real-time events."""
        from src.cli.v3.tui.services.websocket_client import get_ws_client

        try:
            client = get_ws_client()

            # Register handlers for task events
            client.on_message("task.started", self._on_task_started)
            client.on_message("task.progress", self._on_task_progress)
            client.on_message("task.completed", self._on_task_completed)
            client.on_message("task.error", self._on_task_error)

            # Try to connect (non-blocking)
            if await client.connect():
                activity = self.query_one("#activity-panel", ActivityLog)
                activity.add_entry("[green]Connected to Tawiza API[/]")
                logger.info("Dashboard connected to WebSocket")
            else:
                logger.debug("WebSocket not available, using polling mode")

        except Exception as e:
            logger.warning(f"WebSocket connection failed: {e}")

    async def _on_task_started(self, data: dict) -> None:
        """Handle task started event."""
        task_id = data.get("task_id", "unknown")
        agent = data.get("agent", "general")

        activity = self.query_one("#activity-panel", ActivityLog)
        activity.add_entry(f"[cyan]Task started:[/] {task_id[:8]}... ({agent})")

        # Add to task list
        task_list = self.query_one("#agents-panel", TaskList)
        task_list.add_task(TaskInfo(
            id=task_id,
            name=data.get("prompt", "Task")[:30],
            agent=agent,
            status=TaskStatus.IN_PROGRESS,
        ))

    async def _on_task_progress(self, data: dict) -> None:
        """Handle task progress event."""
        task_id = data.get("task_id", "")
        data.get("step", 0)
        data.get("total_steps", 1)
        message = data.get("message", "")

        if message:
            activity = self.query_one("#activity-panel", ActivityLog)
            activity.add_entry(f"[dim]{task_id[:8]}:[/] {message}")

    async def _on_task_completed(self, data: dict) -> None:
        """Handle task completed event."""
        task_id = data.get("task_id", "unknown")
        duration = data.get("duration_seconds", 0)

        activity = self.query_one("#activity-panel", ActivityLog)
        activity.add_entry(f"[green]Task completed:[/] {task_id[:8]}... ({duration:.1f}s)")

        # Update task status
        task_list = self.query_one("#agents-panel", TaskList)
        task_list.update_task(task_id, TaskStatus.COMPLETED)

    async def _on_task_error(self, data: dict) -> None:
        """Handle task error event."""
        task_id = data.get("task_id", "unknown")
        error = data.get("error", "Unknown error")

        activity = self.query_one("#activity-panel", ActivityLog)
        activity.add_entry(f"[red]Task error:[/] {error[:50]}")

        # Update task status
        task_list = self.query_one("#agents-panel", TaskList)
        task_list.update_task(task_id, TaskStatus.FAILED)

    def action_refresh(self) -> None:
        """Manual refresh."""
        # Use run_worker to properly schedule the async coroutine
        self.run_worker(self._refresh_data())
        self.app.notify("Refreshed", timeout=1)
