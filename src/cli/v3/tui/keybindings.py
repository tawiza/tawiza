"""Centralized keybindings configuration for Tawiza TUI."""


from textual.binding import Binding

# =============================================================================
# Global Application Keybindings
# =============================================================================

APP_BINDINGS: list[Binding] = [
    # Navigation
    Binding("q", "quit", "Quit", show=True, priority=True),
    Binding("escape", "back", "Back", show=False),
    Binding("?", "show_help", "Help", show=True),
    Binding("h", "show_help", "Help", show=False),

    # Screen switching
    Binding("d", "switch_screen('dashboard')", "Dashboard", show=True),
    Binding("1", "switch_screen('dashboard')", "Dashboard", show=False),
    Binding("a", "switch_screen('agents')", "Agents", show=True),
    Binding("2", "switch_screen('agents')", "Agents", show=False),
    Binding("m", "switch_screen('metrics')", "Metrics", show=True),
    Binding("3", "switch_screen('metrics')", "Metrics", show=False),
    Binding("s", "switch_screen('services')", "Services", show=True),
    Binding("4", "switch_screen('services')", "Services", show=False),
    Binding("l", "switch_screen('logs')", "Logs", show=True),
    Binding("5", "switch_screen('logs')", "Logs", show=False),

    # Actions
    Binding("r", "refresh", "Refresh", show=True),
    Binding("f5", "refresh", "Refresh", show=False),
    Binding("g", "toggle_gpu_details", "GPU Details", show=False),

    # Navigation within screens
    Binding("tab", "focus_next", "Next", show=False),
    Binding("shift+tab", "focus_previous", "Previous", show=False),
    Binding("enter", "select", "Select", show=False),
    Binding("space", "toggle", "Toggle", show=False),
]


# =============================================================================
# Screen-Specific Keybindings
# =============================================================================

DASHBOARD_BINDINGS: list[Binding] = [
    Binding("p", "toggle_pause", "Pause Updates", show=True),
    Binding("e", "expand_panel", "Expand Panel", show=False),
]

AGENTS_BINDINGS: list[Binding] = [
    Binding("n", "new_task", "New Task", show=True),
    Binding("k", "kill_task", "Kill Task", show=True),
    Binding("i", "task_info", "Task Info", show=True),
    Binding("c", "clear_completed", "Clear Done", show=False),
]

METRICS_BINDINGS: list[Binding] = [
    Binding("t", "toggle_timerange", "Time Range", show=True),
    Binding("z", "zoom_in", "Zoom In", show=False),
    Binding("x", "zoom_out", "Zoom Out", show=False),
    Binding("e", "export_metrics", "Export", show=True),
]

SERVICES_BINDINGS: list[Binding] = [
    Binding("o", "open_service", "Open URL", show=True),
    Binding("r", "restart_service", "Restart", show=True),
    Binding("t", "toggle_service", "Toggle", show=False),
]

LOGS_BINDINGS: list[Binding] = [
    Binding("f", "filter_logs", "Filter", show=True),
    Binding("/", "search_logs", "Search", show=True),
    Binding("c", "clear_logs", "Clear", show=True),
    Binding("w", "toggle_wrap", "Wrap", show=False),
    Binding("n", "next_match", "Next Match", show=False),
    Binding("p", "prev_match", "Prev Match", show=False),
]


# =============================================================================
# Keybinding Groups for Help Display
# =============================================================================

KEYBINDING_GROUPS = {
    "Navigation": [
        ("q", "Quit application"),
        ("Esc", "Go back / Close dialog"),
        ("?/h", "Show help"),
        ("Tab", "Focus next element"),
        ("Shift+Tab", "Focus previous element"),
    ],
    "Screens": [
        ("d/1", "Dashboard view"),
        ("a/2", "Agents view"),
        ("m/3", "Metrics view"),
        ("s/4", "Services view"),
        ("l/5", "Logs view"),
    ],
    "Actions": [
        ("r/F5", "Refresh data"),
        ("Enter", "Select / Confirm"),
        ("Space", "Toggle selection"),
    ],
    "Dashboard": [
        ("p", "Pause/Resume updates"),
        ("e", "Expand focused panel"),
    ],
    "Agents": [
        ("n", "Create new task"),
        ("k", "Kill selected task"),
        ("i", "Show task details"),
    ],
    "Metrics": [
        ("t", "Change time range"),
        ("z/x", "Zoom in/out"),
        ("e", "Export metrics"),
    ],
    "Services": [
        ("o", "Open service URL"),
        ("r", "Restart service"),
    ],
    "Logs": [
        ("f", "Filter logs"),
        ("/", "Search in logs"),
        ("c", "Clear log view"),
        ("n/p", "Next/Previous match"),
    ],
}


def get_bindings_for_screen(screen_name: str) -> list[Binding]:
    """Get combined bindings for a specific screen."""
    screen_bindings = {
        "dashboard": DASHBOARD_BINDINGS,
        "agents": AGENTS_BINDINGS,
        "metrics": METRICS_BINDINGS,
        "services": SERVICES_BINDINGS,
        "logs": LOGS_BINDINGS,
    }
    return APP_BINDINGS + screen_bindings.get(screen_name, [])


def format_help_text() -> str:
    """Format keybindings as help text for display."""
    lines = ["[bold cyan]Tawiza TUI Keybindings[/]\n"]

    for group_name, bindings in KEYBINDING_GROUPS.items():
        lines.append(f"\n[bold yellow]{group_name}[/]")
        for key, description in bindings:
            lines.append(f"  [green]{key:12}[/] {description}")

    return "\n".join(lines)
