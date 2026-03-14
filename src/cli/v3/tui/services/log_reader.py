"""Log Reader Service - Reads and monitors system logs."""

import asyncio
import contextlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from loguru import logger


class LogLevel(Enum):
    """Log severity levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class LogEntry:
    """A parsed log entry."""

    timestamp: datetime
    level: LogLevel
    source: str
    message: str
    raw_line: str = ""


class LogReader:
    """Reads and monitors log files from multiple sources."""

    # Log file sources
    LOG_SOURCES = {
        "tawiza": Path(__file__).resolve().parents[4] / "logs" / "advanced_debug.log",
        "alerts": Path("/var/log/proxmox-alerts/alerts-2025-12.log"),
        "storage": Path("/var/log/proxmox-alerts/storage-alert.log"),
        "syslog": Path("/var/log/syslog"),
    }

    # Patterns for parsing different log formats
    PATTERNS = {
        # Tawiza format: 2025-11-21 12:01:43,832 | INFO | module | message | func:line
        "tawiza": re.compile(
            r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ \| "
            r"(\w+) \| "
            r"([^\|]+) \| "
            r"(.+?) \|"
        ),
        # Proxmox alerts: [Tue Dec  9 09:00:01 AM CET 2025] ALERT: message
        "proxmox": re.compile(r"\[([^\]]+)\] (ALERT|WARNING|ERROR|INFO): (.+)"),
        # Simple format: [LEVEL] message
        "simple": re.compile(r"\[(ALERT|WARNING|ERROR|INFO|DEBUG)\] (.+)"),
        # Syslog format: Dec 11 18:00:01 hostname process[pid]: message
        "syslog": re.compile(r"(\w+ \d+ \d+:\d+:\d+) (\S+) ([^:]+): (.+)"),
    }

    def __init__(self):
        self._callbacks: list[Callable[[LogEntry], None]] = []
        self._file_positions: dict[str, int] = {}
        self._running = False
        self._watch_task: asyncio.Task | None = None

    def on_new_log(self, callback: Callable[[LogEntry], None]) -> None:
        """Register callback for new log entries."""
        self._callbacks.append(callback)

    def _parse_level(self, level_str: str) -> LogLevel:
        """Parse log level string to enum."""
        level_map = {
            "DEBUG": LogLevel.DEBUG,
            "INFO": LogLevel.INFO,
            "WARNING": LogLevel.WARNING,
            "WARN": LogLevel.WARNING,
            "ALERT": LogLevel.WARNING,
            "ERROR": LogLevel.ERROR,
            "CRITICAL": LogLevel.CRITICAL,
            "CRIT": LogLevel.CRITICAL,
        }
        return level_map.get(level_str.upper(), LogLevel.INFO)

    def _extract_source(self, module_path: str) -> str:
        """Extract short source name from module path."""
        parts = module_path.strip().split(".")
        for part in reversed(parts):
            if "agent" in part.lower():
                return part.replace("_agent", "").replace("agent", "")[:10]
            if part in ["debugging", "debugger"]:
                return "debug"
            if part in ["api", "routes"]:
                return "api"
        return parts[-1][:10] if parts else "system"

    def parse_line(self, line: str, source_type: str = "tawiza") -> LogEntry | None:
        """Parse a log line into a LogEntry."""
        line = line.strip()
        if not line:
            return None

        # Try Tawiza format
        match = self.PATTERNS["tawiza"].match(line)
        if match:
            timestamp_str, level, module, message = match.groups()
            try:
                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                timestamp = datetime.now()
            return LogEntry(
                timestamp=timestamp,
                level=self._parse_level(level),
                source=self._extract_source(module),
                message=message.strip(),
                raw_line=line,
            )

        # Try Proxmox format
        match = self.PATTERNS["proxmox"].match(line)
        if match:
            timestamp_str, level, message = match.groups()
            try:
                timestamp = datetime.strptime(
                    timestamp_str.replace("  ", " "), "%a %b %d %I:%M:%S %p %Z %Y"
                )
            except ValueError:
                timestamp = datetime.now()
            return LogEntry(
                timestamp=timestamp,
                level=self._parse_level(level),
                source="proxmox",
                message=message.strip(),
                raw_line=line,
            )

        # Try simple format
        match = self.PATTERNS["simple"].match(line)
        if match:
            level, message = match.groups()
            return LogEntry(
                timestamp=datetime.now(),
                level=self._parse_level(level),
                source="system",
                message=message.strip(),
                raw_line=line,
            )

        # Try syslog format
        match = self.PATTERNS["syslog"].match(line)
        if match:
            timestamp_str, hostname, process, message = match.groups()
            try:
                year = datetime.now().year
                timestamp = datetime.strptime(f"{year} {timestamp_str}", "%Y %b %d %H:%M:%S")
            except ValueError:
                timestamp = datetime.now()
            return LogEntry(
                timestamp=timestamp,
                level=LogLevel.INFO,
                source=process.split("[")[0][:10],
                message=message.strip(),
                raw_line=line,
            )

        # Fallback: unparsed line as info
        return LogEntry(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            source="system",
            message=line[:200],
            raw_line=line,
        )

    async def read_initial_logs(self, max_lines: int = 50) -> list[LogEntry]:
        """Read initial logs from all sources."""
        entries = []

        for source_name, log_path in self.LOG_SOURCES.items():
            if not log_path.exists():
                continue

            try:
                lines = await self._read_tail(log_path, max_lines // len(self.LOG_SOURCES))
                for line in lines:
                    entry = self.parse_line(line, source_name)
                    if entry:
                        entries.append(entry)

                self._file_positions[source_name] = log_path.stat().st_size

            except Exception as e:
                logger.warning(f"Failed to read {source_name} logs: {e}")

        entries.sort(key=lambda e: e.timestamp)
        return entries[-max_lines:]

    async def _read_tail(self, path: Path, n_lines: int = 50) -> list[str]:
        """Read last N lines from a file using asyncio subprocess."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "tail",
                "-n",
                str(n_lines),
                str(path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            return stdout.decode("utf-8", errors="replace").splitlines()
        except Exception:
            try:
                content = path.read_text(errors="replace")
                return content.splitlines()[-n_lines:]
            except Exception:
                return []

    async def start_watching(self) -> None:
        """Start watching log files for new entries."""
        self._running = True
        self._watch_task = asyncio.create_task(self._watch_loop())

    async def stop_watching(self) -> None:
        """Stop watching log files."""
        self._running = False
        if self._watch_task:
            self._watch_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._watch_task

    async def _watch_loop(self) -> None:
        """Watch loop for new log entries."""
        while self._running:
            try:
                for source_name, log_path in self.LOG_SOURCES.items():
                    if not log_path.exists():
                        continue

                    current_size = log_path.stat().st_size
                    last_pos = self._file_positions.get(source_name, 0)

                    if current_size > last_pos:
                        try:
                            with open(log_path, errors="replace") as f:
                                f.seek(last_pos)
                                new_content = f.read()

                            for line in new_content.splitlines():
                                entry = self.parse_line(line, source_name)
                                if entry:
                                    for callback in self._callbacks:
                                        try:
                                            callback(entry)
                                        except Exception as e:
                                            logger.error(f"Log callback error: {e}")

                            self._file_positions[source_name] = current_size

                        except Exception as e:
                            logger.warning(f"Error reading new logs from {source_name}: {e}")

                    elif current_size < last_pos:
                        self._file_positions[source_name] = 0

                await asyncio.sleep(1.0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Watch loop error: {e}")
                await asyncio.sleep(5.0)


_log_reader: LogReader | None = None


def get_log_reader() -> LogReader:
    """Get the singleton log reader instance."""
    global _log_reader
    if _log_reader is None:
        _log_reader = LogReader()
    return _log_reader
