#!/usr/bin/env python3
"""
Application TUI Tawiza-V2
Interface Textual fullscreen avec multiple screens et navigation
"""

from dataclasses import dataclass

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Log,
    ProgressBar,
    Select,
    Static,
    Switch,
    TabbedContent,
    TabPane,
)

# Import our modules
try:
    from src.cli.ui.live_dashboard import AgentStatus, PerformanceMetrics, SystemMetrics
except ImportError:
    # Fallback for testing
    @dataclass
    class SystemMetrics:
        cpu_percent: float = 0.0
        memory_percent: float = 0.0
        memory_used_gb: float = 0.0
        memory_total_gb: float = 0.0
        disk_percent: float = 0.0
        disk_used_gb: float = 0.0
        disk_total_gb: float = 0.0

        @staticmethod
        def collect():
            return SystemMetrics()

    @dataclass
    class PerformanceMetrics:
        throughput: float = 0.0
        latency: float = 0.0
        success_rate: float = 0.0
        cache_hit_rate: float = 0.0
        active_tasks: int = 0
        completed_tasks: int = 0
        failed_tasks: int = 0

    @dataclass
    class AgentStatus:
        name: str = ""
        status: str = ""
        tasks_completed: int = 0
        success_rate: float = 0.0


# ===== CUSTOM WIDGETS =====


class MetricCard(Static):
    """Widget pour afficher une métrique"""

    def __init__(self, title: str, value: str = "0", unit: str = "", color: str = "cyan", **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.metric_value = value
        self.unit = unit
        self.color = color

    def compose(self) -> ComposeResult:
        yield Label(self.title, classes="metric-title")
        yield Label(f"{self.metric_value}{self.unit}", classes="metric-value")

    def update_value(self, value: str, unit: str = ""):
        """Mettre à jour la valeur"""
        self.metric_value = value
        self.unit = unit
        self.refresh()


class StatusIndicator(Static):
    """Indicateur de status avec couleur"""

    status = reactive("idle")

    def __init__(self, initial_status: str = "idle", **kwargs):
        super().__init__(**kwargs)
        self.status = initial_status

    def render(self) -> Text:
        """Render status with color"""
        if self.status == "running":
            return Text("● Running", style="bold green")
        elif self.status == "idle":
            return Text("○ Idle", style="yellow")
        elif self.status == "error":
            return Text("✗ Error", style="bold red")
        elif self.status == "stopped":
            return Text("◌ Stopped", style="dim white")
        else:
            return Text(f"? {self.status}", style="white")


class SystemMonitor(Static):
    """Widget de monitoring système temps réel"""

    cpu_percent = reactive(0.0)
    memory_percent = reactive(0.0)
    disk_percent = reactive(0.0)

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("System Resources", classes="section-title")

            with Horizontal(classes="metrics-row"):
                yield MetricCard("CPU", "0", "%", "cyan", id="cpu-card")
                yield MetricCard("Memory", "0", "%", "yellow", id="mem-card")
                yield MetricCard("Disk", "0", "%", "magenta", id="disk-card")

            with Vertical(classes="progress-container"):
                yield Label("CPU Usage")
                yield ProgressBar(total=100, show_eta=False, id="cpu-progress")

                yield Label("Memory Usage")
                yield ProgressBar(total=100, show_eta=False, id="mem-progress")

                yield Label("Disk Usage")
                yield ProgressBar(total=100, show_eta=False, id="disk-progress")

    def on_mount(self) -> None:
        """Start monitoring when mounted"""
        self.update_metrics()
        self.set_interval(1, self.update_metrics)

    @work(exclusive=True)
    async def update_metrics(self) -> None:
        """Update system metrics"""
        try:
            metrics = SystemMetrics.collect()

            self.cpu_percent = metrics.cpu_percent
            self.memory_percent = metrics.memory_percent
            self.disk_percent = metrics.disk_percent

            # Update cards
            cpu_card = self.query_one("#cpu-card", MetricCard)
            cpu_card.update_value(f"{metrics.cpu_percent:.1f}", "%")

            mem_card = self.query_one("#mem-card", MetricCard)
            mem_card.update_value(f"{metrics.memory_percent:.1f}", "%")

            disk_card = self.query_one("#disk-card", MetricCard)
            disk_card.update_value(f"{metrics.disk_percent:.1f}", "%")

            # Update progress bars
            self.query_one("#cpu-progress", ProgressBar).update(progress=metrics.cpu_percent)
            self.query_one("#mem-progress", ProgressBar).update(progress=metrics.memory_percent)
            self.query_one("#disk-progress", ProgressBar).update(progress=metrics.disk_percent)
        except Exception as e:
            self.log(f"Error updating metrics: {e}")


class PerformanceMonitor(Static):
    """Widget de monitoring de performance"""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Performance Metrics", classes="section-title")

            with Horizontal(classes="metrics-row"):
                yield MetricCard("Throughput", "0", " tasks/s", "green", id="throughput-card")
                yield MetricCard("Latency", "0", " ms", "yellow", id="latency-card")
                yield MetricCard("Success Rate", "0", "%", "cyan", id="success-card")

            with Horizontal(classes="metrics-row"):
                yield MetricCard("Active", "0", " tasks", "yellow", id="active-card")
                yield MetricCard("Completed", "0", " tasks", "green", id="completed-card")
                yield MetricCard("Failed", "0", " tasks", "red", id="failed-card")

    def on_mount(self) -> None:
        """Start monitoring"""
        self.set_interval(2, self.update_performance)

    @work(exclusive=True)
    async def update_performance(self) -> None:
        """Update performance metrics (mock data for now)"""
        import random

        throughput = random.uniform(20, 30)
        latency = random.uniform(5, 15)
        success_rate = random.uniform(95, 99)

        active = random.randint(2, 6)
        completed = random.randint(100, 200)
        failed = random.randint(0, 5)

        self.query_one("#throughput-card", MetricCard).update_value(f"{throughput:.1f}", " tasks/s")
        self.query_one("#latency-card", MetricCard).update_value(f"{latency:.1f}", " ms")
        self.query_one("#success-card", MetricCard).update_value(f"{success_rate:.1f}", "%")

        self.query_one("#active-card", MetricCard).update_value(str(active), " tasks")
        self.query_one("#completed-card", MetricCard).update_value(str(completed), " tasks")
        self.query_one("#failed-card", MetricCard).update_value(str(failed), " tasks")


class AgentsTable(Static):
    """Table des agents avec status"""

    def compose(self) -> ComposeResult:
        yield Label("Active Agents", classes="section-title")
        yield DataTable(id="agents-table")

    def on_mount(self) -> None:
        """Initialize table"""
        table = self.query_one("#agents-table", DataTable)
        table.add_columns("Agent", "Status", "Tasks", "Success Rate")

        # Mock data
        agents = [
            ("ML Engineer", "running", "42", "98.5%"),
            ("Data Analyst", "running", "38", "99.1%"),
            ("Code Reviewer", "idle", "12", "97.5%"),
            ("Optimizer", "running", "15", "96.8%"),
        ]

        for agent in agents:
            table.add_row(*agent)

        self.set_interval(3, self.update_agents)

    @work(exclusive=True)
    async def update_agents(self) -> None:
        """Update agent statuses"""
        import random

        table = self.query_one("#agents-table", DataTable)

        # Update random rows
        for row_key in list(table.rows.keys()):
            if random.random() > 0.7:
                row = table.get_row(row_key)
                tasks = int(row[2]) + random.randint(0, 2)
                success = f"{random.uniform(95, 100):.1f}%"
                table.update_cell(row_key, "Tasks", str(tasks))
                table.update_cell(row_key, "Success Rate", success)


# ===== SCREENS =====


class DashboardScreen(Screen):
    """Écran principal de dashboard"""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("a", "show_agents", "Agents"),
        Binding("s", "show_settings", "Settings"),
        Binding("r", "refresh", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()

        with VerticalScroll(), Container(id="dashboard-container"):
            yield SystemMonitor(id="system-monitor")
            yield PerformanceMonitor(id="performance-monitor")
            yield AgentsTable(id="agents-table")

        yield Footer()

    def action_show_agents(self) -> None:
        """Switch to agents screen"""
        self.app.push_screen("agents")

    def action_show_settings(self) -> None:
        """Switch to settings screen"""
        self.app.push_screen("settings")

    def action_refresh(self) -> None:
        """Refresh all monitors"""
        self.notify("Dashboard refreshed")


class AgentsScreen(Screen):
    """Écran de gestion des agents"""

    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("a", "add_agent", "Add Agent"),
        Binding("d", "delete_agent", "Delete"),
        Binding("r", "restart_agent", "Restart"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()

        with TabbedContent():
            with TabPane("Active Agents"), VerticalScroll():
                yield Label("Active Agents List", classes="section-title")
                yield DataTable(id="active-agents-table")

            with TabPane("Configuration"), VerticalScroll():
                yield Label("Agent Configuration", classes="section-title")

                yield Label("Agent Type:")
                yield Select(
                    [("ML Engineer", "ml"), ("Data Analyst", "data"), ("Optimizer", "opt")],
                    prompt="Select agent type",
                    id="agent-type-select",
                )

                yield Label("Priority:")
                yield Select(
                    [("High", "high"), ("Medium", "medium"), ("Low", "low")],
                    prompt="Select priority",
                    id="priority-select",
                )

                yield Label("Max Retries:")
                yield Input(placeholder="3", id="retries-input")

                with Horizontal():
                    yield Button("Create Agent", variant="primary", id="create-agent-btn")
                    yield Button("Cancel", variant="default", id="cancel-btn")

            with TabPane("Logs"), VerticalScroll():
                yield Label("Agent Logs", classes="section-title")
                yield Log(id="agent-logs")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize agents table"""
        table = self.query_one("#active-agents-table", DataTable)
        table.add_columns("Agent ID", "Type", "Status", "Uptime", "Tasks")

        # Mock data
        agents = [
            ("agent-001", "ML Engineer", "running", "2h 15m", "42"),
            ("agent-002", "Data Analyst", "running", "1h 45m", "38"),
            ("agent-003", "Code Reviewer", "idle", "3h 20m", "12"),
            ("agent-004", "Optimizer", "running", "45m", "15"),
        ]

        for agent in agents:
            table.add_row(*agent)

        # Mock logs
        log = self.query_one("#agent-logs", Log)
        log.write_line("[cyan]System started[/cyan]")
        log.write_line("[green]Agent ML Engineer started[/green]")
        log.write_line("[yellow]Agent Code Reviewer idle[/yellow]")

    def action_back(self) -> None:
        """Go back to dashboard"""
        self.app.pop_screen()

    def action_add_agent(self) -> None:
        """Add new agent"""
        self.notify("Add agent dialog (not implemented yet)")

    def action_delete_agent(self) -> None:
        """Delete selected agent"""
        self.notify("Delete agent (not implemented yet)")

    def action_restart_agent(self) -> None:
        """Restart selected agent"""
        self.notify("Restart agent (not implemented yet)")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "create-agent-btn":
            self.notify("Agent created (mock)")
        elif event.button.id == "cancel-btn":
            self.notify("Cancelled")


class SettingsScreen(Screen):
    """Écran de configuration"""

    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("ctrl+s", "save", "Save"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()

        with TabbedContent():
            with TabPane("General"), VerticalScroll():
                yield Label("General Settings", classes="section-title")

                with Horizontal():
                    yield Label("Theme:")
                    yield Select(
                        [("Sunset", "sunset"), ("Ocean", "ocean"), ("Forest", "forest")],
                        prompt="Select theme",
                        id="theme-select",
                    )

                with Horizontal():
                    yield Label("Auto-refresh:")
                    yield Switch(value=True, id="auto-refresh-switch")

                with Horizontal():
                    yield Label("Notifications:")
                    yield Switch(value=True, id="notifications-switch")

            with TabPane("Performance"), VerticalScroll():
                yield Label("Performance Settings", classes="section-title")

                yield Label("Number of Workers:")
                yield Input(placeholder="4", id="workers-input")

                yield Label("Cache Size (MB):")
                yield Input(placeholder="1000", id="cache-input")

                with Horizontal():
                    yield Label("Enable GPU:")
                    yield Switch(value=False, id="gpu-switch")

            with TabPane("Advanced"), VerticalScroll():
                yield Label("Advanced Settings", classes="section-title")

                yield Label("Log Level:")
                yield Select(
                    [("DEBUG", "debug"), ("INFO", "info"), ("WARNING", "warning")],
                    prompt="Select log level",
                    id="loglevel-select",
                )

                yield Label("Timeout (seconds):")
                yield Input(placeholder="300", id="timeout-input")

        with Horizontal(classes="button-row"):
            yield Button("Save Settings", variant="primary", id="save-btn")
            yield Button("Reset Defaults", variant="default", id="reset-btn")
            yield Button("Cancel", variant="default", id="cancel-btn")

        yield Footer()

    def action_back(self) -> None:
        """Go back"""
        self.app.pop_screen()

    def action_save(self) -> None:
        """Save settings"""
        self.notify("Settings saved", severity="information")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "save-btn":
            self.notify("Settings saved successfully", severity="information")
        elif event.button.id == "reset-btn":
            self.notify("Settings reset to defaults", severity="warning")
        elif event.button.id == "cancel-btn":
            self.action_back()


# ===== MAIN APP =====


class TawizaTUI(App):
    """Application TUI principale Tawiza-V2"""

    CSS = """
    Screen {
        background: $surface;
    }

    #dashboard-container {
        padding: 1;
        height: auto;
    }

    .section-title {
        color: $accent;
        text-style: bold;
        margin-bottom: 1;
    }

    .metrics-row {
        height: auto;
        margin-bottom: 1;
    }

    MetricCard {
        border: solid $primary;
        padding: 1;
        margin: 0 1;
        width: 1fr;
        height: auto;
    }

    .metric-title {
        color: $text-muted;
        text-align: center;
    }

    .metric-value {
        color: $accent;
        text-style: bold;
        text-align: center;
        content-align: center middle;
        height: 3;
    }

    .progress-container {
        padding: 1;
        margin-top: 1;
    }

    ProgressBar {
        margin-bottom: 1;
    }

    DataTable {
        height: auto;
        min-height: 10;
        margin-top: 1;
    }

    .button-row {
        dock: bottom;
        height: auto;
        padding: 1;
    }

    Button {
        margin: 0 1;
    }

    Input {
        margin-bottom: 1;
    }

    Select {
        margin-bottom: 1;
    }

    Label {
        margin-top: 1;
    }
    """

    TITLE = "Tawiza-V2 TUI"
    SUB_TITLE = "Multi-Agent Orchestration Platform"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("d", "show_dashboard", "Dashboard"),
        Binding("a", "show_agents", "Agents"),
        Binding("s", "show_settings", "Settings"),
    ]

    SCREENS = {
        "dashboard": DashboardScreen,
        "agents": AgentsScreen,
        "settings": SettingsScreen,
    }

    def on_mount(self) -> None:
        """Initialize app"""
        self.push_screen("dashboard")

    def action_show_dashboard(self) -> None:
        """Show dashboard"""
        self.switch_screen("dashboard")

    def action_show_agents(self) -> None:
        """Show agents screen"""
        self.push_screen("agents")

    def action_show_settings(self) -> None:
        """Show settings screen"""
        self.push_screen("settings")


# ===== MAIN =====


def main():
    """Run the TUI app"""
    app = TawizaTUI()
    app.run()


if __name__ == "__main__":
    main()
