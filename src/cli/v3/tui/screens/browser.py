"""Browser Screen - Browser automation monitoring and control."""

import webbrowser

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.timer import Timer
from textual.widgets import Input, Static

from src.cli.v3.tui.widgets.browser_preview import BrowserPreview


class BrowserLogPanel(Static):
    """Panel showing browser action logs."""

    DEFAULT_CSS = """
    BrowserLogPanel {
        height: 10;
        border: solid #888888;
        background: $surface;
        padding: 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._entries = []

    def render(self) -> str:
        title = "[bold cyan]BROWSER LOG[/]\n"
        if not self._entries:
            return title + "[dim]No browser activity[/]"
        return title + "\n".join(self._entries[-8:])

    def add_entry(self, action: str, target: str = "") -> None:
        from datetime import datetime

        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"[dim]{ts}[/] {action}"
        if target:
            entry += f" → {target}"
        self._entries.append(entry)
        if len(self._entries) > 50:
            self._entries.pop(0)
        self.refresh()

    def clear(self) -> None:
        self._entries.clear()
        self.refresh()


class BrowserScreen(Container):
    """Browser automation content (Container for ContentSwitcher)."""

    BINDINGS = [
        Binding("ctrl+o", "open_browser", "^O:Open", show=True),
        Binding("ctrl+t", "focus_url", "^T:URL", show=True, priority=True),
        Binding("ctrl+g", "navigate", "^G:Go", show=True),
        Binding("ctrl+k", "take_control", "^K:Control", show=True),
        Binding("ctrl+s", "screenshot", "^S:Screenshot", show=True),
    ]

    DEFAULT_CSS = """
    BrowserScreen {
        layout: vertical;
        width: 100%;
        height: 100%;
    }

    #browser-header {
        height: 3;
        padding: 0 1;
        border-bottom: solid $primary;
        background: $surface-darken-1;
    }

    #url-bar {
        height: 3;
        padding: 0 1;
        background: $surface-darken-1;
    }

    #url-bar Static {
        width: 8;
        padding: 1 0;
    }

    #url-bar Input {
        width: 1fr;
    }

    #browser-content {
        height: 1fr;
        padding: 1;
    }

    #browser-preview {
        height: 1fr;
    }

    #captcha-banner {
        dock: bottom;
        height: 3;
        background: $warning;
        color: $surface;
        padding: 1;
        text-align: center;
        display: none;
    }

    #captcha-banner.visible {
        display: block;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._browser_active = False
        self._novnc_url = "http://localhost:6080/vnc.html"
        self._captcha_detected = False
        self._refresh_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        """Create the browser screen layout."""
        # Header
        yield Static(id="browser-header")

        # URL bar
        with Horizontal(id="url-bar"):
            yield Static("[bold]URL:[/]")
            yield Input(placeholder="Enter URL and press Ctrl+G to navigate...", id="url-input")

        # Main content
        with Container(id="browser-content"):
            yield BrowserPreview(id="browser-preview")

        # Captcha warning banner
        yield Static(
            "[bold]⚠️ CAPTCHA DETECTED[/] - Press Ctrl+K to take control", id="captcha-banner"
        )

        # Browser log
        yield BrowserLogPanel(id="browser-log")

    def on_mount(self) -> None:
        """Initialize on mount."""
        self._update_header()
        self._refresh_timer = self.set_interval(2.0, self._check_browser_status)
        self._init_demo()

    def on_unmount(self) -> None:
        """Cleanup on unmount."""
        if self._refresh_timer:
            self._refresh_timer.stop()

    def _init_demo(self) -> None:
        """Initialize with demo data."""
        preview = self.query_one("#browser-preview", BrowserPreview)
        preview.set_url("https://example.com")
        preview.set_status("Ready")

        log = self.query_one("#browser-log", BrowserLogPanel)
        log.add_entry("Browser sandbox initialized")
        log.add_entry("noVNC server ready on :6080")

    def _update_header(self) -> None:
        """Update the header display."""
        header = self.query_one("#browser-header", Static)
        status = "● Active" if self._browser_active else "○ Inactive"
        status_color = "green" if self._browser_active else "dim"

        header.update(
            f"[bold cyan]🌐 BROWSER SANDBOX[/]    "
            f"[{status_color}]{status}[/]    "
            f"[dim]noVNC: {self._novnc_url}[/]"
        )

    async def _check_browser_status(self) -> None:
        """Check if browser/noVNC is running."""
        # Check if noVNC port is open
        import socket

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("localhost", 6080))
            self._browser_active = result == 0
            sock.close()
        except Exception:
            self._browser_active = False

        self._update_header()

        preview = self.query_one("#browser-preview", BrowserPreview)
        preview.set_status("Active" if self._browser_active else "Inactive")

    def set_captcha_detected(self, detected: bool) -> None:
        """Set captcha detected state."""
        self._captcha_detected = detected
        banner = self.query_one("#captcha-banner", Static)

        if detected:
            banner.add_class("visible")
            self.app.notify("⚠️ Captcha detected! Press 't' to take control", timeout=5)
        else:
            banner.remove_class("visible")

        preview = self.query_one("#browser-preview", BrowserPreview)
        preview.set_captcha_detected(detected)

    def action_open_browser(self) -> None:
        """Open browser in external window via noVNC."""
        if self._browser_active:
            webbrowser.open(self._novnc_url)
            self.app.notify(f"Opening noVNC: {self._novnc_url}", timeout=2)

            log = self.query_one("#browser-log", BrowserLogPanel)
            log.add_entry("Opened noVNC in browser")
        else:
            self.app.notify("Browser not active. Starting...", timeout=2)
            self._start_browser()

    def _start_browser(self) -> None:
        """Start the browser sandbox."""
        log = self.query_one("#browser-log", BrowserLogPanel)
        log.add_entry("Starting browser sandbox...")

        # TODO: Start via BrowserManager
        # For now, just notify
        self.app.notify("Starting browser sandbox... (not implemented)", timeout=3)

    def action_take_control(self) -> None:
        """Take control of the browser (pause agent, open browser)."""
        self.app.notify("Taking control - agent paused", timeout=2)

        log = self.query_one("#browser-log", BrowserLogPanel)
        log.add_entry("User took control")

        # Pause the agent
        # TODO: Via AgentController

        # Open browser
        self.action_open_browser()

    def action_resume_agent(self) -> None:
        """Resume agent after manual intervention."""
        self.app.notify("Resuming agent...", timeout=2)

        log = self.query_one("#browser-log", BrowserLogPanel)
        log.add_entry("Agent resumed by user")

        # Clear captcha state
        self.set_captcha_detected(False)

        # Resume agent
        # TODO: Via AgentController

    def action_screenshot(self) -> None:
        """Take a screenshot of the browser."""
        self.app.notify("Taking screenshot...", timeout=2)

        log = self.query_one("#browser-log", BrowserLogPanel)
        log.add_entry("Screenshot captured")

        # TODO: Capture via BrowserManager

    def action_go_back(self) -> None:
        """Go back to previous screen."""
        self.app.switch_to_screen("dashboard")

    def action_focus_url(self) -> None:
        """Focus the URL input."""
        url_input = self.query_one("#url-input", Input)
        url_input.focus()

    def action_navigate(self) -> None:
        """Navigate to URL in input."""
        url_input = self.query_one("#url-input", Input)
        url = url_input.value.strip()

        if not url:
            self.app.notify("Enter a URL first", timeout=2)
            return

        if not url.startswith("http"):
            url = "https://" + url

        log = self.query_one("#browser-log", BrowserLogPanel)
        log.add_entry("Navigating", url)

        preview = self.query_one("#browser-preview", BrowserPreview)
        preview.set_url(url)
        preview.set_status("Loading...")

        self.app.notify(f"Navigating to {url}", timeout=2)
        # TODO: Actually navigate via browser automation

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter in URL input."""
        if event.input.id == "url-input":
            self.action_navigate()
