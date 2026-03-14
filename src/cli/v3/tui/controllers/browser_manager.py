"""Browser Manager - Manages browser sandbox and noVNC."""

import asyncio
import contextlib
import socket
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path


class BrowserState(Enum):
    """Browser sandbox state."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


@dataclass
class BrowserInfo:
    """Browser sandbox information."""

    state: BrowserState
    novnc_url: str
    current_url: str | None = None
    screenshot_path: Path | None = None
    last_screenshot: datetime | None = None
    captcha_detected: bool = False
    error: str | None = None


class BrowserManager:
    """Manager for browser sandbox with noVNC support."""

    def __init__(
        self,
        novnc_host: str = "localhost",
        novnc_port: int = 6080,
        vnc_port: int = 5900,
    ):
        self._novnc_host = novnc_host
        self._novnc_port = novnc_port
        self._vnc_port = vnc_port
        self._state = BrowserState.STOPPED
        self._process: subprocess.Popen | None = None
        self._listeners: list[Callable[[BrowserInfo], None]] = []
        self._current_url: str | None = None
        self._screenshot_dir = Path.home() / ".tawiza" / "screenshots"
        self._screenshot_dir.mkdir(parents=True, exist_ok=True)
        self._captcha_detected = False

    @property
    def novnc_url(self) -> str:
        """Get the noVNC URL."""
        return f"http://{self._novnc_host}:{self._novnc_port}/vnc.html"

    @property
    def state(self) -> BrowserState:
        """Get current state."""
        return self._state

    @property
    def info(self) -> BrowserInfo:
        """Get current browser info."""
        return BrowserInfo(
            state=self._state,
            novnc_url=self.novnc_url,
            current_url=self._current_url,
            screenshot_path=self._get_latest_screenshot(),
            last_screenshot=self._get_screenshot_time(),
            captcha_detected=self._captcha_detected,
        )

    def add_listener(self, callback: Callable[[BrowserInfo], None]) -> None:
        """Add a state change listener."""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[BrowserInfo], None]) -> None:
        """Remove a listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify_listeners(self) -> None:
        """Notify all listeners of state change."""
        info = self.info
        for listener in self._listeners:
            with contextlib.suppress(Exception):
                listener(info)

    def is_running(self) -> bool:
        """Check if browser is running by testing noVNC port."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((self._novnc_host, self._novnc_port))
            sock.close()
            return result == 0
        except Exception:
            return False

    async def start(self) -> bool:
        """Start the browser sandbox."""
        if self._state == BrowserState.RUNNING:
            return True

        self._state = BrowserState.STARTING
        self._notify_listeners()

        try:
            # Check if already running
            if self.is_running():
                self._state = BrowserState.RUNNING
                self._notify_listeners()
                return True

            # Try to start via docker-compose
            # This assumes a browser sandbox docker container is configured
            result = subprocess.run(
                ["docker-compose", "-f", "docker/docker-compose.browser.yml", "up", "-d"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=Path.home() / "Tawiza-V2",
            )

            if result.returncode == 0:
                # Wait for noVNC to be ready
                for _ in range(10):
                    await asyncio.sleep(1)
                    if self.is_running():
                        self._state = BrowserState.RUNNING
                        self._notify_listeners()
                        return True

            self._state = BrowserState.ERROR
            self._notify_listeners()
            return False

        except Exception:
            self._state = BrowserState.ERROR
            self._notify_listeners()
            return False

    async def stop(self) -> bool:
        """Stop the browser sandbox."""
        try:
            subprocess.run(
                ["docker-compose", "-f", "docker/docker-compose.browser.yml", "down"],
                capture_output=True,
                timeout=30,
                cwd=Path.home() / "Tawiza-V2",
            )
            self._state = BrowserState.STOPPED
            self._notify_listeners()
            return True
        except Exception:
            return False

    def set_url(self, url: str) -> None:
        """Set the current URL being browsed."""
        self._current_url = url
        self._notify_listeners()

    async def take_screenshot(self) -> Path | None:
        """Take a screenshot of the browser."""
        if self._state != BrowserState.RUNNING:
            return None

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = self._screenshot_dir / f"browser_{timestamp}.png"

            # This would use playwright or selenium to take screenshot
            # For now, we'll just create a placeholder
            # In real implementation:
            # from playwright.async_api import async_playwright
            # async with async_playwright() as p:
            #     browser = await p.chromium.connect_over_cdp(...)
            #     page = await browser.pages()[0]
            #     await page.screenshot(path=str(screenshot_path))

            return screenshot_path

        except Exception:
            return None

    def _get_latest_screenshot(self) -> Path | None:
        """Get the path to the latest screenshot."""
        screenshots = list(self._screenshot_dir.glob("browser_*.png"))
        if screenshots:
            return max(screenshots, key=lambda p: p.stat().st_mtime)
        return None

    def _get_screenshot_time(self) -> datetime | None:
        """Get the timestamp of the latest screenshot."""
        latest = self._get_latest_screenshot()
        if latest:
            return datetime.fromtimestamp(latest.stat().st_mtime)
        return None

    def set_captcha_detected(self, detected: bool) -> None:
        """Set whether a captcha has been detected."""
        self._captcha_detected = detected
        self._notify_listeners()

    def clear_captcha(self) -> None:
        """Clear the captcha detected flag."""
        self._captcha_detected = False
        self._notify_listeners()


# Singleton instance
_manager: BrowserManager | None = None


def get_browser_manager() -> BrowserManager:
    """Get the global browser manager instance."""
    global _manager
    if _manager is None:
        _manager = BrowserManager()
    return _manager
