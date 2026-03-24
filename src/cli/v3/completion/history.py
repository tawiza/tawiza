"""Command history tracking and analysis."""

import json
from datetime import datetime
from pathlib import Path


class CommandHistory:
    """Tracks and analyzes CLI command usage."""

    def __init__(self, history_file: Path | None = None):
        self.history_file = history_file or Path.home() / ".tawiza" / "command_history.json"

    def _load(self) -> dict:
        """Load history from file."""
        if self.history_file.exists():
            try:
                return json.loads(self.history_file.read_text())
            except Exception:
                pass
        return {"commands": [], "patterns": {}}

    def _save(self, history: dict) -> None:
        """Save history to file."""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self.history_file.write_text(json.dumps(history, indent=2))

    def record(
        self,
        command: str,
        subcommand: str | None = None,
        args: dict | None = None,
        success: bool = True,
        duration: float | None = None,
        result: dict | None = None,
    ) -> None:
        """Record a command execution.

        Args:
            command: Main command name
            subcommand: Optional subcommand
            args: Command arguments
            success: Whether command succeeded
            duration: Execution duration
            result: Optional result data
        """
        history = self._load()

        entry = {
            "timestamp": datetime.now().isoformat(),
            "command": command,
            "subcommand": subcommand,
            "args": args or {},
            "success": success,
            "duration": duration,
        }

        if result:
            # Store minimal result info
            entry["result_keys"] = list(result.keys()) if isinstance(result, dict) else None

        history["commands"].append(entry)

        # Keep last 1000 entries
        history["commands"] = history["commands"][-1000:]

        # Update patterns
        full_cmd = f"{command}:{subcommand}" if subcommand else command
        if full_cmd not in history["patterns"]:
            history["patterns"][full_cmd] = {
                "count": 0,
                "success_count": 0,
                "total_duration": 0.0,
                "last_used": None,
                "common_args": {},
            }

        pattern = history["patterns"][full_cmd]
        pattern["count"] += 1
        if success:
            pattern["success_count"] += 1
        if duration:
            pattern["total_duration"] += duration
        pattern["last_used"] = entry["timestamp"]

        # Track argument frequencies
        for arg_name, arg_value in (args or {}).items():
            if isinstance(arg_value, (str, int, float, bool)):
                if arg_name not in pattern["common_args"]:
                    pattern["common_args"][arg_name] = {}
                val_key = str(arg_value)
                pattern["common_args"][arg_name][val_key] = (
                    pattern["common_args"][arg_name].get(val_key, 0) + 1
                )

        self._save(history)

    def get_suggestions(
        self,
        command: str,
        arg_name: str,
        limit: int = 5,
    ) -> list[tuple[str, int]]:
        """Get suggested values for an argument.

        Args:
            command: Command name
            arg_name: Argument name
            limit: Max suggestions

        Returns:
            List of (value, count) tuples
        """
        history = self._load()
        pattern = history["patterns"].get(command, {})
        arg_freqs = pattern.get("common_args", {}).get(arg_name, {})

        return sorted(
            arg_freqs.items(),
            key=lambda x: -x[1],
        )[:limit]

    def get_recent(self, limit: int = 10) -> list[dict]:
        """Get recent commands.

        Args:
            limit: Max entries

        Returns:
            List of command entries
        """
        history = self._load()
        return history["commands"][-limit:]

    def get_most_used(self, limit: int = 10) -> list[tuple[str, int]]:
        """Get most used commands.

        Args:
            limit: Max entries

        Returns:
            List of (command, count) tuples
        """
        history = self._load()
        patterns = history.get("patterns", {})

        return sorted(
            [(cmd, p["count"]) for cmd, p in patterns.items()],
            key=lambda x: -x[1],
        )[:limit]

    def get_stats(self) -> dict:
        """Get command statistics.

        Returns:
            Dict with statistics
        """
        history = self._load()
        commands = history.get("commands", [])
        patterns = history.get("patterns", {})

        total_commands = len(commands)
        unique_commands = len(patterns)

        success_count = sum(1 for c in commands if c.get("success", True))
        success_rate = (success_count / total_commands * 100) if total_commands else 0

        durations = [c["duration"] for c in commands if c.get("duration")]
        avg_duration = sum(durations) / len(durations) if durations else 0

        return {
            "total_commands": total_commands,
            "unique_commands": unique_commands,
            "success_rate": round(success_rate, 1),
            "avg_duration_seconds": round(avg_duration, 2),
            "most_used": self.get_most_used(5),
        }


# Global instance
_history = CommandHistory()


def get_history() -> CommandHistory:
    """Get the global history instance."""
    return _history
