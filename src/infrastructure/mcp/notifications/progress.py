"""Progress notification system for MCP.

Provides real-time progress updates during long-running operations.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum


class ProgressType(Enum):
    """Types of progress notifications."""

    STEP = "step"  # Main step progress
    SOURCE = "source"  # Data source query
    AGENT = "agent"  # Debate agent activity
    BROWSER = "browser"  # Browser navigation
    GEOCODE = "geocode"  # Geocoding operation


@dataclass
class ProgressEvent:
    """Progress event data."""

    type: ProgressType
    progress: float
    total: float
    message: str
    data: dict | None = None


class ProgressNotifier:
    """Manages progress notifications for MCP tools.

    Usage:
        notifier = ProgressNotifier(ctx.report_progress)

        async with notifier.step("Searching sources", total=8) as step:
            for source in sources:
                await step.update(f"Querying {source}")
                results = await query(source)
                step.increment()
    """

    def __init__(self, report_fn: Callable | None = None):
        """Initialize with optional MCP report function.

        Args:
            report_fn: Function to call for progress updates (ctx.report_progress)
        """
        self._report_fn = report_fn
        self._current_progress = 0
        self._total = 100
        self._callbacks: list[Callable] = []

    def add_callback(self, callback: Callable[[ProgressEvent], None]):
        """Add a callback for progress events."""
        self._callbacks.append(callback)

    async def report(self, progress: float, total: float = 100, message: str = ""):
        """Report progress to MCP client."""
        if self._report_fn:
            try:
                self._report_fn(progress, total, message)
            except Exception:
                pass  # Don't fail on notification errors

        # Call registered callbacks
        event = ProgressEvent(
            type=ProgressType.STEP,
            progress=progress,
            total=total,
            message=message,
        )
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception:
                pass

    async def step(self, message: str, progress: float, total: float = 100):
        """Report a step in progress."""
        await self.report(progress, total, f"[Step] {message}")

    async def source(self, source_name: str, status: str, results: int = 0, duration_ms: float = 0):
        """Report data source query progress."""
        msg = f"[Source] {source_name}: {status}"
        if results > 0:
            msg += f" ({results} results, {duration_ms:.0f}ms)"
        await self.report(self._current_progress, self._total, msg)

    async def agent(self, agent_name: str, status: str, confidence: float | None = None):
        """Report debate agent activity."""
        msg = f"[Agent] {agent_name}: {status}"
        if confidence is not None:
            msg += f" (confidence: {confidence:.0f}%)"
        await self.report(self._current_progress, self._total, msg)

    async def browser(self, url: str, action: str):
        """Report browser navigation."""
        await self.report(self._current_progress, self._total, f"[Browser] {action}: {url}")

    async def geocode(self, address: str, status: str):
        """Report geocoding operation."""
        await self.report(self._current_progress, self._total, f"[Geocode] {status}: {address}")

    def set_progress(self, progress: float, total: float = 100):
        """Set current progress values."""
        self._current_progress = progress
        self._total = total


class StepContext:
    """Context manager for tracking step progress."""

    def __init__(self, notifier: ProgressNotifier, name: str, total: int):
        self.notifier = notifier
        self.name = name
        self.total = total
        self.current = 0

    async def __aenter__(self):
        await self.notifier.step(f"Starting: {self.name}", 0, self.total)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            await self.notifier.step(f"Completed: {self.name}", self.total, self.total)

    async def update(self, message: str):
        """Update with a message."""
        await self.notifier.step(f"{self.name}: {message}", self.current, self.total)

    def increment(self, amount: int = 1):
        """Increment progress."""
        self.current = min(self.current + amount, self.total)
        self.notifier.set_progress(self.current, self.total)
