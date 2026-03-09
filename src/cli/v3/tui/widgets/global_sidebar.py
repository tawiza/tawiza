"""Global Sidebar Navigation Widget.

A collapsible sidebar that provides navigation across all TUI screens.
Features:
- Icon + label format
- Collapsible with '[' key (6 columns → 2 columns)
- Visual indication of active screen
- Keyboard navigation with Ctrl+1-5
"""

from loguru import logger
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static


class SidebarItem(Static):
    """A single navigation item in the sidebar."""

    DEFAULT_CSS = """
    SidebarItem {
        width: 100%;
        height: 3;
        padding: 0 1;
        content-align: center middle;
        background: transparent;
    }

    SidebarItem:hover {
        background: $surface-lighten-1;
    }

    SidebarItem.active {
        background: $primary;
        color: $surface;
        text-style: bold;
    }

    SidebarItem .icon {
        width: 2;
    }

    SidebarItem .label {
        margin-left: 1;
    }
    """

    class Selected(Message):
        """Message when a sidebar item is selected."""

        def __init__(self, screen_id: str):
            super().__init__()
            self.screen_id = screen_id

    def __init__(
        self,
        icon: str,
        label: str,
        screen_id: str,
        shortcut: str = "",
        **kwargs
    ):
        super().__init__(**kwargs)
        self.icon = icon
        self.label = label
        self.screen_id = screen_id
        self.shortcut = shortcut
        self._collapsed = False

    def compose(self) -> ComposeResult:
        return []

    def on_mount(self) -> None:
        """Set initial content."""
        self._update_display()

    def _update_display(self) -> None:
        """Update display based on collapsed state."""
        if self._collapsed:
            self.update(f"{self.icon}")
        else:
            self.update(f"{self.icon} {self.label}")

    def set_collapsed(self, collapsed: bool) -> None:
        """Set collapsed state."""
        self._collapsed = collapsed
        self._update_display()

    def on_click(self) -> None:
        """Handle click to select this item."""
        self.post_message(self.Selected(self.screen_id))


class GlobalSidebar(Container):
    """Global navigation sidebar with collapsible support.

    The sidebar provides navigation to all main screens:
    - Dashboard (📊)
    - TAJINE (🧠)
    - Agent (🤖)
    - Chat (💬)
    - Config (⚙️)

    Collapse/expand with '[' key.
    """

    DEFAULT_CSS = """
    GlobalSidebar {
        dock: left;
        width: 14;
        height: 100%;
        background: $surface-darken-1;
        border-right: solid $primary;
        padding: 1 0;
    }

    GlobalSidebar.collapsed {
        width: 4;
    }

    GlobalSidebar .sidebar-header {
        width: 100%;
        height: 2;
        content-align: center middle;
        text-style: bold;
        color: $primary;
        padding: 0 1;
    }

    GlobalSidebar .sidebar-divider {
        width: 100%;
        height: 1;
        background: $primary-darken-1;
        margin: 1 0;
    }

    GlobalSidebar .sidebar-footer {
        dock: bottom;
        width: 100%;
        height: 2;
        content-align: center middle;
        color: $text-muted;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("bracketleft", "toggle_collapse", "[ Toggle", show=False),
    ]

    # Navigation items configuration
    NAV_ITEMS = [
        ("📊", "Dash", "dashboard", "^1"),
        ("🧠", "TAJINE", "tajine", "^2"),
        ("🤖", "Agent", "agent_live", "^3"),
        ("💬", "Chat", "chat", "^4"),
        ("⚙️", "Config", "config", "^5"),
    ]

    collapsed = reactive(False)
    active_screen = reactive("dashboard")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._items: dict[str, SidebarItem] = {}

    def compose(self) -> ComposeResult:
        """Create sidebar layout."""
        yield Static("Tawiza", classes="sidebar-header", id="sidebar-title")
        yield Static("", classes="sidebar-divider")

        for icon, label, screen_id, shortcut in self.NAV_ITEMS:
            item = SidebarItem(
                icon=icon,
                label=label,
                screen_id=screen_id,
                shortcut=shortcut,
                id=f"nav-{screen_id}",
            )
            self._items[screen_id] = item
            yield item

        yield Static("", classes="sidebar-divider")
        yield Static("[ ] Collapse", classes="sidebar-footer", id="collapse-hint")

    def on_mount(self) -> None:
        """Initialize sidebar state."""
        self._update_active_item()

    def watch_collapsed(self, collapsed: bool) -> None:
        """React to collapse state change."""
        if collapsed:
            self.add_class("collapsed")
        else:
            self.remove_class("collapsed")

        # Update all items
        for item in self._items.values():
            item.set_collapsed(collapsed)

        # Update header and footer
        try:
            title = self.query_one("#sidebar-title", Static)
            hint = self.query_one("#collapse-hint", Static)
            if collapsed:
                title.update("M")
                hint.update("[")
            else:
                title.update("Tawiza")
                hint.update("[ ] Collapse")
        except Exception:
            pass

        logger.debug(f"Sidebar collapsed: {collapsed}")

    def watch_active_screen(self, screen_id: str) -> None:
        """React to active screen change."""
        self._update_active_item()

    def _update_active_item(self) -> None:
        """Update visual state of active item."""
        for sid, item in self._items.items():
            if sid == self.active_screen:
                item.add_class("active")
            else:
                item.remove_class("active")

    def set_active(self, screen_id: str) -> None:
        """Set the active screen."""
        self.active_screen = screen_id

    def action_toggle_collapse(self) -> None:
        """Toggle collapsed state."""
        self.collapsed = not self.collapsed

    def on_sidebar_item_selected(self, event: SidebarItem.Selected) -> None:
        """Handle sidebar item selection."""
        self.active_screen = event.screen_id
        # Bubble up to app
        self.post_message(event)
