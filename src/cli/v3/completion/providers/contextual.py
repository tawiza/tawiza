"""Contextual completion based on command history."""

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from src.cli.v3.completion.base import CompletionProvider, CompletionResult


class HistoryProvider(CompletionProvider):
    """Provides completions based on command history."""

    def __init__(self, history_file: Path | None = None):
        self.history_file = history_file or Path.home() / ".tawiza" / "command_history.json"

    @property
    def name(self) -> str:
        return "contextual:history"

    @property
    def priority(self) -> int:
        return 50  # Lower than static/dynamic

    def get_completions(self, incomplete: str, context: dict | None = None) -> list[CompletionResult]:
        """Get completions from command history.

        Args:
            incomplete: Partial input
            context: Should contain 'command' and optionally 'arg_name'

        Returns:
            Historical completions sorted by frequency
        """
        if not self.history_file.exists():
            return []

        try:
            history = json.loads(self.history_file.read_text())
            commands = history.get("commands", [])

            if not context:
                return []

            command = context.get("command")
            arg_name = context.get("arg_name")

            if not command:
                return []

            # Find matching historical values
            values = []
            for entry in commands:
                if entry.get("command") == command:
                    args = entry.get("args", {})
                    if arg_name and arg_name in args:
                        values.append(args[arg_name])
                    elif not arg_name:
                        # Return all args
                        values.extend(args.values())

            # Count frequencies
            counter = Counter(v for v in values if isinstance(v, str) and incomplete.lower() in v.lower())

            return [
                CompletionResult(
                    value=value,
                    description=f"Used {count}x",
                    score=min(count / 10, 2.0),  # Cap at 2.0
                    source="history",
                )
                for value, count in counter.most_common(10)
            ]

        except Exception:
            return []

    def record_command(
        self,
        command: str,
        args: dict,
        success: bool = True,
        duration: float | None = None,
    ) -> None:
        """Record a command to history.

        Args:
            command: Command name
            args: Command arguments
            success: Whether command succeeded
            duration: Execution duration in seconds
        """
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

        if self.history_file.exists():
            history = json.loads(self.history_file.read_text())
        else:
            history = {"commands": [], "patterns": {}}

        # Add to commands list
        history["commands"].append({
            "timestamp": datetime.now().isoformat(),
            "command": command,
            "args": args,
            "success": success,
            "duration": duration,
        })

        # Keep last 1000 commands
        history["commands"] = history["commands"][-1000:]

        # Update patterns
        if command not in history["patterns"]:
            history["patterns"][command] = {
                "count": 0,
                "success_count": 0,
                "total_duration": 0,
                "common_args": {},
            }

        pattern = history["patterns"][command]
        pattern["count"] += 1
        if success:
            pattern["success_count"] += 1
        if duration:
            pattern["total_duration"] += duration

        # Track common args
        for arg_name, arg_value in args.items():
            if arg_name not in pattern["common_args"]:
                pattern["common_args"][arg_name] = {}
            if isinstance(arg_value, str):
                if arg_value not in pattern["common_args"][arg_name]:
                    pattern["common_args"][arg_name][arg_value] = 0
                pattern["common_args"][arg_name][arg_value] += 1

        self.history_file.write_text(json.dumps(history, indent=2))


class NextCommandSuggester:
    """Suggests next commands based on workflow patterns."""

    # Common workflows
    WORKFLOWS = {
        "agent-run": ["agent-debug", "agent-run"],
        "train-start": ["train-status", "train-logs"],
        "analyze": ["sources", "agent-run"],
        "status": ["services", "dashboard"],
        "model-pull": ["model-list", "chat"],
    }

    def suggest(self, last_command: str, last_result: dict | None = None) -> list[CompletionResult]:
        """Suggest next commands based on last command.

        Args:
            last_command: The command that was just run
            last_result: Optional result from last command

        Returns:
            Suggested next commands
        """
        suggestions = self.WORKFLOWS.get(last_command, [])

        results = []
        for i, cmd in enumerate(suggestions):
            results.append(CompletionResult(
                value=cmd,
                description="Suggested next step",
                score=2.0 - (i * 0.5),  # Decreasing scores
                source="workflow",
            ))

        # Add contextual suggestions based on result
        if last_result:
            if last_result.get("status") == "failed":
                results.insert(0, CompletionResult(
                    value="agent-debug",
                    description="Debug failed task",
                    score=3.0,
                    source="contextual",
                ))

            if last_result.get("task_id"):
                results.insert(0, CompletionResult(
                    value=f"agent-debug {last_result['task_id'][:8]}",
                    description="View task details",
                    score=2.5,
                    source="contextual",
                ))

        return results
