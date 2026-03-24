"""Watcher daemon for automatic polling of data sources.

Runs in the background and polls BODACC, BOAMP, GDELT for new items
matching the configured watchlist.
"""

import asyncio
import contextlib
import logging
import signal
from pathlib import Path

from loguru import logger

from ..dashboard import DashboardDB
from .pollers import BasePoller, BoampPoller, BodaccPoller, GdeltPoller
from .storage import WatcherStorage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


class WatcherDaemon:
    """Background daemon for polling data sources.

    Polls configured sources at regular intervals and saves alerts
    to the dashboard database.
    """

    # Polling intervals in seconds
    INTERVALS = {
        "bodacc": 6 * 3600,  # Every 6 hours
        "boamp": 6 * 3600,  # Every 6 hours
        "gdelt": 2 * 3600,  # Every 2 hours
    }

    # Check interval (how often to check if polling is needed)
    CHECK_INTERVAL = 300  # 5 minutes

    def __init__(self, db_path: Path | None = None):
        """Initialize the daemon.

        Args:
            db_path: Path to dashboard database (default: ~/.tawiza/dashboard.db)
        """
        self.db = DashboardDB(db_path) if db_path else DashboardDB()
        self.storage = WatcherStorage(self.db)
        self.running = False
        self._task: asyncio.Task | None = None

        # Initialize pollers
        self.pollers: dict[str, BasePoller] = {
            "bodacc": BodaccPoller(),
            "boamp": BoampPoller(),
            "gdelt": GdeltPoller(),
        }

    async def start(self):
        """Start the daemon."""
        if self.running:
            logger.warning("Daemon already running")
            return

        self.running = True
        logger.info("Starting watcher daemon...")

        # Ensure default watchlist exists
        await self.storage.async_ensure_default_watchlist()

        # Start the main loop
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Watcher daemon started")

    async def stop(self):
        """Stop the daemon."""
        if not self.running:
            return

        self.running = False
        logger.info("Stopping watcher daemon...")

        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

        await self.db.async_close()
        logger.info("Watcher daemon stopped")

    async def _run_loop(self):
        """Main polling loop."""
        while self.running:
            try:
                await self._check_and_poll()
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")

            # Wait before next check
            await asyncio.sleep(self.CHECK_INTERVAL)

    async def _check_and_poll(self):
        """Check which sources need polling and poll them."""
        for source, interval in self.INTERVALS.items():
            try:
                should_poll = await self.storage.async_should_poll(source, interval)
                if should_poll:
                    await self._poll_source(source)
            except Exception as e:
                logger.error(f"Error checking {source}: {e}")

    async def _poll_source(self, source: str):
        """Poll a specific source.

        Args:
            source: Source to poll (bodacc, boamp, gdelt)
        """
        logger.info(f"Polling {source}...")

        poller = self.pollers.get(source)
        if not poller:
            logger.error(f"Unknown source: {source}")
            return

        # Get keywords for this source
        keywords = await self.storage.async_get_keywords_for_source(source)
        logger.info(f"Keywords for {source}: {keywords}")

        # Poll the source
        alerts, error = await poller.safe_poll(keywords)

        if error:
            logger.error(f"Error polling {source}: {error}")
            await self.storage.async_record_poll(
                source,
                self.INTERVALS[source],
                error=error,
            )
            return

        # Save new alerts (skip existing ones)
        saved_count = 0
        for alert in alerts:
            # Check if alert already exists
            exists = await self.storage.async_alert_exists(
                source,
                alert.title,
                alert.url,
            )
            if not exists:
                await self.storage.async_save_alert(alert)
                saved_count += 1

        logger.info(f"Saved {saved_count} new alerts from {source}")

        # Record poll status
        await self.storage.async_record_poll(source, self.INTERVALS[source])

    async def force_poll(self, source: str | None = None):
        """Force an immediate poll.

        Args:
            source: Source to poll, or None for all sources
        """
        if source:
            await self._poll_source(source)
        else:
            for src in self.pollers:
                await self._poll_source(src)

    def get_status(self) -> dict:
        """Get daemon status."""
        poll_status = self.db.get_poll_status()
        next_polls = self.storage.get_next_poll_times()

        return {
            "running": self.running,
            "sources": {
                src: {
                    "last_poll": poll_status.get(src, {}).get("last_poll"),
                    "next_poll": next_polls.get(src, "unknown"),
                    "polls_count": poll_status.get(src, {}).get("polls_count", 0),
                    "last_error": poll_status.get(src, {}).get("last_error"),
                }
                for src in self.INTERVALS
            },
        }


# Standalone daemon runner
async def run_daemon():
    """Run the daemon as a standalone process."""
    daemon = WatcherDaemon()

    # Handle shutdown signals
    asyncio.get_event_loop()

    def shutdown(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        asyncio.create_task(daemon.stop())

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    await daemon.start()

    # Keep running until stopped
    while daemon.running:
        await asyncio.sleep(1)


def main():
    """Entry point for CLI."""
    asyncio.run(run_daemon())


if __name__ == "__main__":
    main()
