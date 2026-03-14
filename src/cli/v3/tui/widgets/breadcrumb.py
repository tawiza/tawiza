"""Breadcrumb Navigation Widget.

Dynamic breadcrumb that shows the current navigation context:
- Screen name
- Sub-context (e.g., department selected)
- Detail level (e.g., specific item)

Format: Tawiza v6 │ Screen > Context > Detail
"""

from loguru import logger
from textual.reactive import reactive
from textual.widgets import Static


class Breadcrumb(Static):
    """Dynamic breadcrumb navigation showing current context.

    Examples:
    - Dashboard: "Dashboard"
    - TAJINE: "TAJINE > Départements"
    - TAJINE with selection: "TAJINE > Départements > 75-Paris"
    - Agent: "Agent > mistral:7b > Task #3"
    - Config: "Config > Thème"
    """

    DEFAULT_CSS = """
    Breadcrumb {
        dock: top;
        height: 1;
        width: 100%;
        background: $surface-darken-1;
        color: $text;
        padding: 0 1;
    }

    Breadcrumb .app-title {
        color: $primary;
        text-style: bold;
    }

    Breadcrumb .separator {
        color: $text-muted;
    }

    Breadcrumb .current {
        color: $accent;
        text-style: bold;
    }
    """

    # Screen display names
    SCREEN_NAMES = {
        "dashboard": "Dashboard",
        "tajine": "TAJINE",
        "agent_live": "Agent",
        "browser": "Browser",
        "chat": "Chat",
        "history": "Historique",
        "logs": "Logs",
        "files": "Fichiers",
        "config": "Config",
    }

    screen_name = reactive("dashboard")
    context = reactive("")
    detail = reactive("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._segments: list[str] = []

    def render(self) -> str:
        """Render the breadcrumb string."""
        parts = ["[bold cyan]Tawiza v6[/]", "[dim]│[/]"]

        # Add screen name
        display_name = self.SCREEN_NAMES.get(self.screen_name, self.screen_name)
        parts.append(f"[bold]{display_name}[/]")

        # Add context if present
        if self.context:
            parts.append("[dim]>[/]")
            parts.append(self.context)

        # Add detail if present
        if self.detail:
            parts.append("[dim]>[/]")
            parts.append(f"[bold $accent]{self.detail}[/]")

        return " ".join(parts)

    def set_screen(self, screen_name: str) -> None:
        """Set the current screen, clearing context and detail."""
        self.screen_name = screen_name
        self.context = ""
        self.detail = ""
        logger.debug(f"Breadcrumb screen: {screen_name}")

    def set_context(self, context: str) -> None:
        """Set the context segment."""
        self.context = context
        self.detail = ""
        logger.debug(f"Breadcrumb context: {context}")

    def add_detail(self, detail: str) -> None:
        """Add a detail segment."""
        self.detail = detail
        logger.debug(f"Breadcrumb detail: {detail}")

    def clear_context(self) -> None:
        """Clear context and detail."""
        self.context = ""
        self.detail = ""

    def navigate_up(self) -> bool:
        """Navigate up one level. Returns True if navigation occurred."""
        if self.detail:
            self.detail = ""
            return True
        elif self.context:
            self.context = ""
            return True
        return False

    @property
    def full_path(self) -> str:
        """Get the full breadcrumb path as a string."""
        parts = [self.SCREEN_NAMES.get(self.screen_name, self.screen_name)]
        if self.context:
            parts.append(self.context)
        if self.detail:
            parts.append(self.detail)
        return " > ".join(parts)
