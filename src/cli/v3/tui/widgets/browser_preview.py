"""Browser Preview widget for showing browser state."""

from datetime import datetime
from pathlib import Path

from textual.containers import Center, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static


class BrowserPreview(Vertical):
    """Widget for previewing browser state with screenshot."""

    DEFAULT_CSS = """
    BrowserPreview {
        height: 100%;
        border: solid $primary;
        background: $surface;
    }

    BrowserPreview .title {
        dock: top;
        height: 1;
        background: $surface-darken-1;
        padding: 0 1;
        text-style: bold;
        color: $accent;
    }

    BrowserPreview .preview-area {
        height: 1fr;
        content-align: center middle;
        padding: 2;
    }

    BrowserPreview .screenshot-placeholder {
        border: dashed #888888;
        padding: 3;
        content-align: center middle;
    }

    BrowserPreview .captcha-warning {
        background: $warning;
        color: $surface;
        padding: 1;
        text-style: bold;
        text-align: center;
    }

    BrowserPreview .browser-log {
        dock: bottom;
        height: 6;
        border-top: solid $surface-lighten-1;
        padding: 1;
        overflow-y: auto;
    }

    BrowserPreview .status-bar {
        dock: top;
        height: 2;
        padding: 0 1;
        border-bottom: solid $surface-lighten-1;
    }
    """

    url = reactive("")
    status = reactive("Inactive")
    captcha_detected = reactive(False)
    last_update = reactive("")

    class OpenBrowserRequested(Message):
        """Request to open browser in external window."""

        pass

    class TakeControlRequested(Message):
        """Request to take control of browser."""

        pass

    class ResumeAgentRequested(Message):
        """Request to resume agent after manual intervention."""

        pass

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._screenshot_path: Path | None = None
        self._log_entries: list = []

    def compose(self):
        """Compose the browser preview."""
        yield Static("[bold cyan]🌐 BROWSER SANDBOX[/]", classes="title")

        # Status bar
        yield Static(id="status-info", classes="status-bar")

        # Preview area
        with Center(classes="preview-area"):
            yield Static(id="preview-content", classes="screenshot-placeholder")

        # Captcha warning (hidden by default)
        yield Static(id="captcha-warning", classes="captcha-warning")

        # Browser log
        yield Static(id="browser-log", classes="browser-log")

    def on_mount(self) -> None:
        """Initialize on mount."""
        self._update_display()
        # Hide captcha warning initially
        self.query_one("#captcha-warning").display = False

    def watch_url(self, url: str) -> None:
        """React to URL changes."""
        self._update_display()

    def watch_status(self, status: str) -> None:
        """React to status changes."""
        self._update_display()

    def watch_captcha_detected(self, detected: bool) -> None:
        """React to captcha detection."""
        warning = self.query_one("#captcha-warning")
        warning.display = detected
        if detected:
            warning.update("⚠️ CAPTCHA DETECTED - Press [t] to take control")

    def _update_display(self) -> None:
        """Update all display elements."""
        # Status info
        status_color = (
            "green" if self.status == "Active" else "yellow" if self.status == "Ready" else "dim"
        )
        status_icon = "●" if self.status == "Active" else "○"

        url_display = self.url[:50] + "..." if len(self.url) > 50 else self.url or "No URL"

        status_info = self.query_one("#status-info", Static)
        status_info.update(
            f"[{status_color}]{status_icon}[/] Status: [{status_color}]{self.status}[/]\n"
            f"[dim]URL:[/] {url_display}"
        )

        # Preview content
        preview = self.query_one("#preview-content", Static)
        if self._screenshot_path and self._screenshot_path.exists():
            # In a real implementation, we'd use textual-image here
            preview.update(
                f"[dim]Screenshot available[/]\n\n"
                f"[bold]Refreshed: {self.last_update}[/]\n\n"
                f"[cyan]Press [o] to open in browser[/]"
            )
        else:
            preview.update(
                "[dim]No screenshot available[/]\n\n"
                "[bold]Browser Preview[/]\n\n"
                "[cyan]Press [o] to open noVNC viewer[/]"
            )

        # Browser log
        log = self.query_one("#browser-log", Static)
        if self._log_entries:
            log_text = "\n".join(self._log_entries[-5:])  # Last 5 entries
            log.update(f"[dim]Browser Log:[/]\n{log_text}")
        else:
            log.update("[dim]Browser Log:[/]\n[dim]No activity[/]")

    def set_screenshot(self, path: Path) -> None:
        """Set the screenshot path."""
        self._screenshot_path = path
        self.last_update = datetime.now().strftime("%H:%M:%S")
        self._update_display()

    def add_log_entry(self, action: str, target: str = "") -> None:
        """Add a browser log entry."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[dim]{timestamp}[/] {action}"
        if target:
            entry += f" → {target}"
        self._log_entries.append(entry)

        # Keep last 20 entries
        if len(self._log_entries) > 20:
            self._log_entries.pop(0)

        self._update_display()

    def set_captcha_detected(self, detected: bool) -> None:
        """Set captcha detected state."""
        self.captcha_detected = detected

    def clear_log(self) -> None:
        """Clear browser log."""
        self._log_entries.clear()
        self._update_display()

    def set_url(self, url: str) -> None:
        """Set current URL."""
        self.url = url
        self.add_log_entry("Navigate", url)

    def set_status(self, status: str) -> None:
        """Set browser status."""
        self.status = status
