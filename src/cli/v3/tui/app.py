"""Tawiza TUI v6 - Main Application with ContentSwitcher Layout.

TUI v6 Features:
- Global collapsible sidebar (Ctrl+1-5 navigation)
- Dynamic breadcrumb navigation
- Floating chat modal (Ctrl+C toggle)
- Real data only (no mock data)
- ContentSwitcher for persistent sidebar/breadcrumb
"""

import contextlib
from pathlib import Path

from loguru import logger
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import ContentSwitcher, Footer, Static

from src.cli.v3.tui.services.adaptive_refresh import (
    AdaptiveRefreshManager,
    RefreshPriority,
    init_refresh_manager,
)
from src.cli.v3.tui.services.gpu_metrics import get_gpu_utilization
from src.cli.v3.tui.widgets.breadcrumb import Breadcrumb
from src.cli.v3.tui.widgets.chat_modal import ChatModal
from src.cli.v3.tui.widgets.global_sidebar import GlobalSidebar, SidebarItem

# NOTE: ScreenProxy and ScreenWrapper removed in TUI v6.1
# Screen classes are now Container subclasses, mounted directly into ContentSwitcher.
# This eliminates the complexity of proxying Screen lifecycle methods.


class StatusBar(Static):
    """Bottom status bar with system metrics."""

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $surface-darken-1;
        padding: 0 1;
    }
    """

    gpu_percent = reactive(0.0)
    cpu_percent = reactive(0.0)
    ram_percent = reactive(0.0)
    browser_status = reactive("Ready")

    def render(self) -> str:
        gpu_color = (
            "green" if self.gpu_percent < 50 else "yellow" if self.gpu_percent < 80 else "red"
        )
        cpu_color = (
            "green" if self.cpu_percent < 50 else "yellow" if self.cpu_percent < 80 else "red"
        )
        ram_color = (
            "green" if self.ram_percent < 50 else "yellow" if self.ram_percent < 80 else "red"
        )

        browser_icon = "●" if self.browser_status == "Active" else "○"
        browser_color = "green" if self.browser_status == "Active" else "dim"

        return (
            f"[{gpu_color}]GPU {self.gpu_percent:.0f}%[/] │ "
            f"[{cpu_color}]CPU {self.cpu_percent:.0f}%[/] │ "
            f"[{ram_color}]RAM {self.ram_percent:.0f}%[/] │ "
            f"[{browser_color}]{browser_icon} Browser: {self.browser_status}[/]"
        )


class TawizaApp(App):
    """Tawiza Terminal User Interface v6 - With WebSocket Integration."""

    TITLE = "Tawiza TUI v6"
    CSS_PATH = Path(__file__).parent / "styles" / "app.tcss"

    # Use Textual's built-in themes
    AVAILABLE_THEMES = [
        "dracula",
        "nord",
        "tokyo-night",
        "monokai",
        "gruvbox",
        "catppuccin-mocha",
        "catppuccin-latte",
        "solarized-light",
        "textual-dark",
        "textual-light",
    ]

    BINDINGS = [
        # Primary navigation (Ctrl+1-5) - matches sidebar
        Binding("ctrl+1", "switch_screen('dashboard')", "^1:Dash", show=True, priority=True),
        Binding("ctrl+2", "switch_screen('tajine')", "^2:TAJINE", show=True, priority=True),
        Binding("ctrl+3", "switch_screen('agent_live')", "^3:Agent", show=True, priority=True),
        Binding("ctrl+4", "switch_screen('chat')", "^4:Chat", show=True, priority=True),
        Binding("ctrl+5", "switch_screen('config')", "^5:Config", show=True, priority=True),
        # Secondary screens (F keys)
        Binding("f4", "switch_screen('browser')", "F4:Browse", show=False),
        Binding("f6", "switch_screen('history')", "F6:History", show=False),
        Binding("f7", "switch_screen('logs')", "F7:Logs", show=False),
        Binding("f8", "switch_screen('files')", "F8:Files", show=False),
        # Chat modal toggle
        Binding("ctrl+c", "toggle_chat_modal", "^C:Chat", show=True, priority=True),
        # Sidebar toggle
        Binding("bracketleft", "toggle_sidebar", "[:Sidebar", show=True),
        # Global actions
        Binding("ctrl+q", "quit", "^Q:Quit", show=True, priority=True),
        Binding("f10", "show_help", "F10:Help", show=True),
        Binding("ctrl+r", "refresh", "^R:Refresh", show=True),
        Binding("escape", "close_or_unfocus", "Esc:Retour", show=True),
    ]

    current_screen = reactive("dashboard")

    # Screen factories for lazy loading
    SCREEN_FACTORIES = {
        "dashboard": "src.cli.v3.tui.screens.dashboard:DashboardScreen",
        "tajine": "src.cli.v3.tui.screens.tajine:TAJINEScreen",
        "agent_live": "src.cli.v3.tui.screens.agent_live:AgentLiveScreen",
        "browser": "src.cli.v3.tui.screens.browser:BrowserScreen",
        "chat": "src.cli.v3.tui.screens.chat:ChatScreen",
        "history": "src.cli.v3.tui.screens.history:HistoryScreen",
        "logs": "src.cli.v3.tui.screens.logs:LogsScreen",
        "files": "src.cli.v3.tui.screens.files:FilesScreen",
        "config": "src.cli.v3.tui.screens.config:ConfigScreen",
    }

    def __init__(self):
        super().__init__()
        self._screens_loaded: set = set()  # Track which screens are loaded
        self._refresh_manager: AdaptiveRefreshManager | None = None
        self._metrics_timer: Timer | None = None
        self._idle_check_timer: Timer | None = None
        self._chat_modal_open: bool = False
        self._chat_messages: list = []  # Persist chat between modal opens

    def compose(self) -> ComposeResult:
        """Create the main app layout with persistent sidebar and breadcrumb.

        Layout:
        ┌──────────────────────────────────────────────────────┐
        │ Breadcrumb                                            │
        ├───────────┬──────────────────────────────────────────┤
        │           │                                          │
        │  Sidebar  │   ContentSwitcher (main content area)    │
        │           │                                          │
        ├───────────┴──────────────────────────────────────────┤
        │ StatusBar                                             │
        ├──────────────────────────────────────────────────────┤
        │ Footer                                                │
        └──────────────────────────────────────────────────────┘
        """
        yield Breadcrumb(id="breadcrumb")
        with Horizontal(id="main-layout"):
            yield GlobalSidebar(id="sidebar")
            yield ContentSwitcher(id="content-switcher")
        yield StatusBar(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize app on mount."""
        # Load saved theme preference
        self._load_theme_preference()

        # Initialize adaptive refresh manager
        self._refresh_manager = init_refresh_manager(self)

        # Load initial dashboard into content switcher
        self._mount_screen_content("dashboard")

        # Set ContentSwitcher to show dashboard
        try:
            content_switcher = self.query_one("#content-switcher", ContentSwitcher)
            content_switcher.current = "dashboard"
        except Exception as e:
            logger.error(f"Failed to set initial screen: {e}")

        self._start_adaptive_metrics()

        # Notify refresh manager of initial screen
        if self._refresh_manager:
            self._refresh_manager.set_active_screen("dashboard")

        # Update navigation UI
        self._update_navigation("dashboard")

        # Preload screens in background (non-blocking)
        # This prevents freeze when switching to heavy screens like TAJINE
        self.run_worker(self._preload_screens_async(), exclusive=False)

        logger.info("TUI started with ContentSwitcher layout")

    async def _preload_screens_async(self) -> None:
        """Preload all screens in background to avoid freeze on first switch.

        Uses async mount with thread pool for heavy imports (numpy, httpx, etc.)
        to keep the UI responsive during preloading.
        """
        import asyncio

        # Screens to preload (skip dashboard, already loaded)
        screens_to_preload = ["tajine", "agent_live", "chat", "config"]

        for screen_id in screens_to_preload:
            if screen_id not in self._screens_loaded:
                # Use async mount (imports in thread pool, mount in main thread)
                await self._mount_screen_async(screen_id)
                # Small delay between screens to keep UI responsive
                await asyncio.sleep(0.05)

        logger.info(f"Preloaded {len(screens_to_preload)} screens in background")

    def _load_theme_preference(self) -> None:
        """Load and apply saved theme preference.

        Note: Uses sync I/O which is acceptable during on_mount() since
        Textual's event loop hasn't fully started. For runtime changes,
        use set_theme_by_name() which runs I/O in a thread pool.
        """
        import json

        from src.cli.constants import PROJECT_ROOT

        prefs_file = PROJECT_ROOT / ".tui_preferences.json"
        try:
            if prefs_file.exists():
                with open(prefs_file) as f:
                    prefs = json.load(f)
                    theme_name = prefs.get("theme", "dracula")
                    if theme_name in self.AVAILABLE_THEMES:
                        self.theme = theme_name
                        logger.info(f"Loaded theme: {theme_name}")
        except Exception as e:
            logger.warning(f"Could not load theme preference: {e}")

    def set_theme_by_name(self, theme_name: str) -> None:
        """Set theme and save preference.

        Theme is applied immediately, file I/O runs in background thread
        to avoid blocking the event loop.
        """
        import json

        if theme_name not in self.AVAILABLE_THEMES:
            return

        # Apply theme immediately (sync, no I/O)
        self.theme = theme_name

        # Save preference in background thread to avoid blocking
        def _save_prefs():
            from src.cli.constants import PROJECT_ROOT

            prefs_file = PROJECT_ROOT / ".tui_preferences.json"
            try:
                prefs = {}
                if prefs_file.exists():
                    with open(prefs_file) as f:
                        prefs = json.load(f)
                prefs["theme"] = theme_name
                with open(prefs_file, "w") as f:
                    json.dump(prefs, f, indent=2)
                logger.info(f"Theme set to: {theme_name}")
            except Exception as e:
                logger.warning(f"Could not save theme: {e}")

        # Run I/O in thread pool (non-blocking)
        self.run_worker(_save_prefs, thread=True)

    def _mount_screen_content(self, screen_id: str) -> bool:
        """Mount a screen's content into the ContentSwitcher (sync version).

        TUI v6.1: Screen classes are now Container subclasses, so we can
        mount them directly without needing a ScreenWrapper.

        NOTE: For non-blocking import, use _mount_screen_async() instead.
        This sync version is used only for the initial dashboard load.

        Args:
            screen_id: The screen identifier

        Returns:
            True if mounted successfully, False on error
        """
        if screen_id in self._screens_loaded:
            return True

        factory_path = self.SCREEN_FACTORIES.get(screen_id)
        if not factory_path:
            logger.warning(f"Unknown screen: {screen_id}")
            return False

        try:
            # Parse module:class path
            module_path, class_name = factory_path.rsplit(":", 1)

            # Dynamic import
            import importlib

            module = importlib.import_module(module_path)
            screen_class = getattr(module, class_name)

            # TUI v6.1: Directly instantiate the Container-based screen
            # No wrapper needed since screens are now Container subclasses
            screen_instance = screen_class(id=screen_id, classes="screen-content")

            # Mount directly into ContentSwitcher
            content_switcher = self.query_one("#content-switcher", ContentSwitcher)
            content_switcher.mount(screen_instance)

            self._screens_loaded.add(screen_id)
            logger.debug(f"Mounted screen content: {screen_id} ({len(self._screens_loaded)}/9)")
            return True

        except Exception as e:
            logger.error(f"Failed to mount screen {screen_id}: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return False

    async def _import_screen_class(self, screen_id: str):
        """Import a screen class in a thread pool to avoid blocking.

        Heavy imports (numpy, httpx, matplotlib) can take 100-200ms.
        Running in a thread pool keeps the UI responsive.

        Returns:
            The screen class, or None on error
        """
        import asyncio
        import concurrent.futures

        factory_path = self.SCREEN_FACTORIES.get(screen_id)
        if not factory_path:
            return None

        module_path, class_name = factory_path.rsplit(":", 1)

        def _do_import():
            import importlib

            module = importlib.import_module(module_path)
            return getattr(module, class_name)

        # Run import in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            screen_class = await loop.run_in_executor(pool, _do_import)

        return screen_class

    async def _mount_screen_async(self, screen_id: str) -> bool:
        """Mount a screen asynchronously (non-blocking import).

        Uses thread pool for heavy imports to keep UI responsive.
        """
        if screen_id in self._screens_loaded:
            return True

        try:
            # Import in thread pool (non-blocking)
            screen_class = await self._import_screen_class(screen_id)
            if screen_class is None:
                return False

            # Create instance and mount (must be in main thread)
            screen_instance = screen_class(id=screen_id, classes="screen-content")
            content_switcher = self.query_one("#content-switcher", ContentSwitcher)
            content_switcher.mount(screen_instance)

            self._screens_loaded.add(screen_id)
            logger.debug(f"Async mounted screen: {screen_id} ({len(self._screens_loaded)}/9)")
            return True

        except Exception as e:
            logger.error(f"Failed to async mount screen {screen_id}: {e}")
            return False

    def _ensure_screen_mounted(self, screen_id: str) -> None:
        """Ensure a screen's content is mounted before switching to it."""
        if screen_id not in self._screens_loaded:
            self._mount_screen_content(screen_id)

    def _start_adaptive_metrics(self) -> None:
        """Start adaptive metrics update with idle detection."""
        # Register metrics timer with adaptive refresh
        self._refresh_manager.register_timer(
            name="app_metrics",
            callback=self._update_metrics,
            priority=RefreshPriority.LOW,
            active_interval=2.0,  # 2s when active
            idle_interval=5.0,  # 5s when idle
            background_interval=10.0,  # 10s when in background
        )
        self._refresh_manager.start_timer("app_metrics")

        # Start idle detection timer
        self._idle_check_timer = self.set_interval(5.0, self._check_idle)

        logger.debug("Adaptive metrics refresh started")

    def _check_idle(self) -> None:
        """Check if user is idle and adjust refresh rates."""
        if self._refresh_manager:
            self._refresh_manager.check_idle()

    async def _update_metrics(self) -> None:
        """Update status bar metrics."""
        try:
            import psutil

            status_bar = self.query_one("#status-bar", StatusBar)
            status_bar.cpu_percent = psutil.cpu_percent(interval=0)
            status_bar.ram_percent = psutil.virtual_memory().percent

            # GPU metrics - async call to avoid blocking event loop
            with contextlib.suppress(Exception):
                status_bar.gpu_percent = await get_gpu_utilization()

        except Exception:
            pass

    def on_key(self, event) -> None:
        """Track user activity on key press."""
        if self._refresh_manager:
            self._refresh_manager.record_activity()

    def on_mouse_move(self, event) -> None:
        """Track user activity on mouse move."""
        if self._refresh_manager:
            self._refresh_manager.record_activity()

    def switch_to_screen(self, screen_id: str) -> None:
        """Switch to a specific screen using ContentSwitcher.

        If screen isn't loaded yet, mounts it in background and switches
        when ready to avoid freezing the UI.
        """
        # If screen is already loaded, switch immediately
        if screen_id in self._screens_loaded:
            self._do_switch(screen_id)
            return

        # Screen not loaded - mount in background and switch when ready
        # Update navigation immediately for responsiveness
        self._update_navigation(screen_id)
        self.notify(f"Chargement de {screen_id}...", timeout=1)

        # Use run_worker to mount asynchronously
        self.run_worker(self._mount_and_switch_async(screen_id), exclusive=False)

    async def _mount_and_switch_async(self, screen_id: str) -> None:
        """Mount a screen and switch to it (async to avoid blocking).

        Uses thread pool for heavy imports to keep UI responsive during switch.
        """
        # Mount using async method (imports in thread pool)
        success = await self._mount_screen_async(screen_id)

        if success:
            # Switch in main thread
            self.call_later(self._do_switch, screen_id)
        else:
            self.notify(f"[red]Erreur chargement {screen_id}[/]", timeout=3)

    def _do_switch(self, screen_id: str) -> None:
        """Actually switch to a screen (internal helper)."""
        try:
            content_switcher = self.query_one("#content-switcher", ContentSwitcher)
            content_switcher.current = screen_id
        except Exception as e:
            logger.error(f"Failed to switch to screen {screen_id}: {e}")
            return

        self.current_screen = screen_id
        self._update_navigation(screen_id)

        # Notify refresh manager of screen change
        if self._refresh_manager:
            self._refresh_manager.set_active_screen(screen_id)
            self._refresh_manager.record_activity()

    def _update_navigation(self, screen_id: str) -> None:
        """Update sidebar and breadcrumb for current screen."""
        try:
            # Update sidebar active state
            sidebar = self.query_one("#sidebar", GlobalSidebar)
            sidebar.set_active(screen_id)

            # Update breadcrumb
            breadcrumb = self.query_one("#breadcrumb", Breadcrumb)
            breadcrumb.set_screen(screen_id)
        except Exception as e:
            logger.warning(f"Could not update navigation: {e}")

    def action_switch_screen(self, screen_id: str) -> None:
        """Action to switch screen via keybinding."""
        self.switch_to_screen(screen_id)
        logger.debug(f"Switched to screen: {screen_id}")

    def action_toggle_chat_modal(self) -> None:
        """Toggle the chat modal overlay."""
        if self._chat_modal_open:
            # Modal will close itself via dismiss()
            return

        self._chat_modal_open = True
        modal = ChatModal(messages=self._chat_messages)
        self.push_screen(modal)
        logger.debug("Opened chat modal")

    def on_chat_modal_closed(self, event: ChatModal.Closed) -> None:
        """Handle chat modal close."""
        self._chat_modal_open = False
        logger.debug("Closed chat modal")

    def on_chat_modal_message_sent(self, event: ChatModal.MessageSent) -> None:
        """Handle chat message sent from modal."""
        # TODO: Forward to TAJINE agent for processing
        logger.info(f"Chat message: {event.content[:50]}...")

        # For now, add a placeholder response
        try:
            modal = self.query_one(ChatModal)
            modal.add_response("Je traite votre demande...")
        except Exception:
            pass

    def action_toggle_sidebar(self) -> None:
        """Toggle sidebar collapsed state."""
        try:
            sidebar = self.query_one("#sidebar", GlobalSidebar)
            sidebar.collapsed = not sidebar.collapsed
        except Exception as e:
            logger.warning(f"Could not toggle sidebar: {e}")

    def action_close_or_unfocus(self) -> None:
        """Close modal or unfocus input on Escape."""
        if self._chat_modal_open:
            # Modal handles its own close
            return
        # Unfocus input
        self.screen.focus()

    def on_sidebar_item_selected(self, event: SidebarItem.Selected) -> None:
        """Handle sidebar navigation item click."""
        self.switch_to_screen(event.screen_id)

    def action_show_help(self) -> None:
        """Show help notification."""
        # Note: Use \[ to escape literal brackets in Rich markup
        help_text = """
[bold cyan]Tawiza TUI v6[/bold cyan]

[bold]Navigation (Sidebar):[/bold]
  Ctrl+1 - Dashboard
  Ctrl+2 - TAJINE
  Ctrl+3 - Agent
  Ctrl+4 - Chat
  Ctrl+5 - Config

[bold]Actions:[/bold]
  Ctrl+C - Ouvrir chat modal
  \\[     - Réduire/Étendre sidebar
  Ctrl+R - Rafraîchir
  Ctrl+Q - Quitter
  Esc    - Retour/Fermer

[bold]Autres écrans (F4-F8):[/bold]
  F4 - Browser | F6 - History
  F7 - Logs    | F8 - Files
"""
        self.notify(help_text, title="Aide", timeout=10)

    def action_refresh(self) -> None:
        """Refresh current screen."""
        self.notify("Refreshing...", timeout=1)

    def action_focus_input(self) -> None:
        """Focus the input field if available."""
        try:
            from textual.widgets import Input

            input_widget = self.screen.query_one(Input)
            input_widget.focus()
        except Exception:
            self.notify("Pas de champ de saisie sur cet écran", timeout=2)


def run_tui() -> None:
    """Run the Tawiza TUI application."""
    app = TawizaApp()
    app.run()


if __name__ == "__main__":
    run_tui()
